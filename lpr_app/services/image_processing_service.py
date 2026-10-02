"""
Image processing service for LPR application.

This service handles the core image processing workflow, including
API integration, coordinate scaling, and file operations.
"""

import logging
import os
import time
from typing import Any

from django.conf import settings
from django.utils import timezone

from ..models import ProcessingLog, UploadedImage
from .bbox_visualizer import create_side_by_side_comparison, visualize_lpr_on_image
from .detection_validator import DetectionValidator
from .image_processor import ImageProcessor
from .qwen_client import DETECTION_PROMPT, OCR_PROMPT, get_qwen_client, parse_detection_response, parse_ocr_response

logger = logging.getLogger(__name__)


def _local_backend():
    """The process-wide local pipeline backend, built on first use.

    Kept module-level rather than per-request because ONNX session construction
    is the dominant cost of a local request; rebuilding it per image would make
    measured latency meaningless.
    """
    global _LOCAL_BACKEND
    if _LOCAL_BACKEND is None:
        from ..pipeline.local_backend import build_local_backend_from_settings

        _LOCAL_BACKEND = build_local_backend_from_settings()
        logger.info("Local pipeline backend initialised (provider=%s)", settings.PIPELINE_PROVIDER)
    return _LOCAL_BACKEND


_LOCAL_BACKEND = None


def reset_local_backend() -> None:
    """Drop the cached backend. Used by tests and after a settings change."""
    global _LOCAL_BACKEND
    _LOCAL_BACKEND = None


class LLMPipelineError(Exception):
    """The LLM backend could not complete detection.

    Distinct from "no plates found". The caller must fail the image rather than
    report an empty result, because an unprocessed image and an image with no
    plates are different answers and only one of them is true.
    """


class ImageProcessingService:
    """Service for handling image processing workflow."""

    @staticmethod
    def process_uploaded_image(uploaded_image: UploadedImage, save_image: bool = True) -> dict[str, Any]:
        """
        Process an uploaded image through the three-phase LPR pipeline.

        Phase 1: Downscale to 256x256 → detect license plates only
        Phase 2: Crop detected plates → batch OCR
        Phase 3: Merge results → visualize on original image

        Args:
            uploaded_image: UploadedImage instance
            save_image: Whether to save processed images (default: True)

        Returns:
            Dictionary with processing result
        """
        processing_start_time = time.time()

        try:
            # Update status to processing
            uploaded_image.processing_status = "processing"
            uploaded_image.save()

            # Update the "started" log with queue time (upload → processing start)
            started_log = ProcessingLog.objects.filter(uploaded_image=uploaded_image, status="started").first()
            if started_log and not started_log.duration_ms:
                queue_ms = int((time.time() - uploaded_image.upload_timestamp.timestamp()) * 1000)
                started_log.duration_ms = queue_ms
                started_log.save(update_fields=["duration_ms"])

            # Log API call start
            api_call_log = ProcessingLog.objects.create(
                uploaded_image=uploaded_image, status="api_call", message="Starting Phase 1: License plate detection"
            )

            start_time = time.time()

            # Get original image path
            image_path = uploaded_image.original_image.path

            # Get original image dimensions for coordinate scaling
            original_image_info = ImageProcessor.get_image_info(image_path)
            if not original_image_info:
                return {"success": False, "error": "Failed to get original image info"}

            original_h = original_image_info["height"]
            original_w = original_image_info["width"]

            # ========== PHASE 1: License Plate Detection ==========
            logger.info("PHASE 1: Detecting license plates on downscaled image")

            if settings.PIPELINE_BACKEND == "local":
                # Local detection and recognition in one pass. It returns the
                # same detections collection the LLM path builds below, so
                # nothing downstream of here knows which backend ran.
                logger.info("Using the local ONNX pipeline backend")
                detections, phase_summary = ImageProcessingService._run_local_pipeline(image_path, start_time)
            else:
                try:
                    detections, phase_summary = ImageProcessingService._run_llm_pipeline(
                        uploaded_image, image_path, original_h, original_w, start_time, api_call_log
                    )
                except LLMPipelineError as exc:
                    # Same wording the inlined code returned, so a failure response
                    # is unchanged by the backend switch.
                    return {"success": False, "error": str(exc)}
            logger.info(phase_summary)

            # ========== PHASE 3: Merge and Visualize ==========
            logger.info("PHASE 3: Merging results and visualizing")

            # Create merged response in expected format
            merged_response = {"filename": uploaded_image.filename, "detections": detections}

            # Conditionally visualize and save processed images
            output_path = None
            comparison_path = None

            if save_image:
                # Visualize results
                on_disk_basename = os.path.basename(uploaded_image.original_image.name)
                output_filename = f"processed_{on_disk_basename}"
                output_path = os.path.join(os.path.dirname(str(uploaded_image.original_image.path)), output_filename)

                success = visualize_lpr_on_image(image_path, merged_response, output_path)

                if not success:
                    return {"success": False, "error": "Failed to create visualization"}

                # Create side-by-side comparison
                comparison_filename = f"comparison_{on_disk_basename}"
                comparison_path = os.path.join(
                    os.path.dirname(str(uploaded_image.original_image.path)), comparison_filename
                )

                create_side_by_side_comparison(image_path, output_path, comparison_path)

            # Update database record
            uploaded_image.api_response = merged_response  # type: ignore[arg-type]
            uploaded_image.processing_status = "completed"
            uploaded_image.processing_timestamp = timezone.now()

            # Only save processed image path if we actually saved image
            if save_image and output_path:
                output_path_str = str(output_path)
                uploaded_image.processed_image.name = output_path_str.replace(str(settings.MEDIA_ROOT) + "/", "")

            uploaded_image.save()

            # Handle cleanup for canary requests
            result = ImageProcessingService._handle_canary_cleanup(uploaded_image, save_image, comparison_path)
            if result:
                return result

            # Log success
            duration = (time.time() - start_time) * 1000
            ProcessingLog.objects.create(
                uploaded_image=uploaded_image,
                status="success",
                message="Processing completed successfully",
                duration_ms=int(duration),
            )

            processing_duration = time.time() - processing_start_time

            return {"success": True, "processed_image_path": output_path, "processing_duration": processing_duration}

        except Exception as e:
            logger.exception(
                "Unhandled exception in process_uploaded_image: %s",
                e,
            )

            # Update status to failed
            uploaded_image.processing_status = "failed"
            uploaded_image.error_message = str(e)
            uploaded_image.save()

            # Log error
            ProcessingLog.objects.create(
                uploaded_image=uploaded_image, status="error", message=f"Processing failed: {str(e)}"
            )

            return {"success": False, "error": str(e)}

    @staticmethod
    def _run_local_pipeline(image_path: str, start_time: float) -> tuple[list[dict[str, Any]], str]:
        """Detect and read plates with the local ONNX backend.

        Extracted from ``process_uploaded_image`` rather than inlined so the
        backend choice is a single branch in the caller and both paths end at the
        same place: a detections collection of the same shape.
        """
        from PIL import Image

        from ..pipeline.local_backend import LocalBackendError

        try:
            with Image.open(image_path) as opened:
                image = opened.convert("RGB")
        except OSError as exc:
            raise LocalBackendError(f"could not open {image_path}: {exc}") from exc

        result = _local_backend().run(image)

        # Per-stage timings go to Prometheus with the outcome attached, so a
        # regression is attributable to a stage rather than to "the pipeline".
        from ..utils.metrics_helpers import MetricsHelper

        for timing in result.timings.values():
            MetricsHelper.record_pipeline_stage_duration(timing.name, timing.status, timing.duration)
            if timing.within_budget is False:
                logger.warning(
                    "Stage %s took %.3fs, over its %.3fs budget",
                    timing.name,
                    timing.duration,
                    timing.budget or 0.0,
                )
        MetricsHelper.record_pipeline_duration("ok" if result.detections else "empty", result.duration)
        if result.within_budget(settings.PIPELINE_LATENCY_BUDGET_SECONDS) is False:
            logger.warning(
                "Local pipeline took %.3fs, over the %.3fs end-to-end budget",
                result.duration,
                settings.PIPELINE_LATENCY_BUDGET_SECONDS,
            )

        summary = f"Local pipeline complete: {len(result.detections)} plate(s) " f"in {result.duration * 1000:.0f}ms"
        return result.detections, summary

    @staticmethod
    def _run_llm_pipeline(
        uploaded_image: UploadedImage,
        image_path: str,
        original_h: int,
        original_w: int,
        start_time: float,
        api_call_log: ProcessingLog,
    ) -> tuple[list[dict[str, Any]], str]:
        """Detect then OCR through the Qwen3-VL API.

        The body is the code that was inlined here before the backend switch,
        unchanged: same prompts, same downscale, same fixed-pixel crop padding,
        same parsing and validation. Extracting it into a method is the only edit,
        so the LLM path's behaviour is untouched by the local backend existing.
        """
        # Downscale image for detection (size derived from plate height requirements)
        downscaled_path = ImageProcessor.downscale_for_detection(
            image_path,
            min_plate_height=settings.MIN_PLATE_HEIGHT,
            plate_height_fraction=settings.PLATE_HEIGHT_FRACTION,
        )
        if not downscaled_path:
            raise LLMPipelineError("Failed to downscale image for detection")

        # Get downscaled image dimensions
        downscaled_info = ImageProcessor.get_image_info(downscaled_path)
        if not downscaled_info:
            raise LLMPipelineError("Failed to get downscaled image info")
        downscaled_h = downscaled_info["height"]
        downscaled_w = downscaled_info["width"]

        try:
            # Encode downscaled image to base64
            base64_downscaled = ImageProcessor.encode_image_to_base64(downscaled_path)
            if not base64_downscaled:
                raise LLMPipelineError("Failed to encode downscaled image")

            # Call API with detection-only prompt
            client = get_qwen_client()
            detection_prompt = DETECTION_PROMPT.replace("[actual filename of the image]", uploaded_image.filename)
            detection_response = client.analyze_image(base64_downscaled, detection_prompt)

            if not detection_response:
                raise LLMPipelineError("Phase 1 API call failed")

            # Parse detection response and scale coordinates to original image
            detection_data = parse_detection_response(
                detection_response, original_h, original_w, downscaled_h, downscaled_w
            )
            if not detection_data:
                raise LLMPipelineError("Failed to parse Phase 1 response")

            # Extract detections
            detections = detection_data.get("detections", [])
            if not detections:
                logger.info("No license plates detected in image")
                detections = []

            validator = DetectionValidator(
                min_confidence=settings.DETECTION_MIN_CONFIDENCE,
                min_box_area_fraction=settings.DETECTION_MIN_BOX_AREA_FRACTION,
                max_box_area_fraction=settings.DETECTION_MAX_BOX_AREA_FRACTION,
                min_plate_aspect=settings.DETECTION_MIN_PLATE_ASPECT,
                max_plate_aspect=settings.DETECTION_MAX_PLATE_ASPECT,
            )
            detections = validator.filter_detections(detections, original_h, original_w)
            if not detections:
                logger.info("No valid license plates after sanity checks")

            logger.info(f"Phase 1 complete: Detected {len(detections)} license plate(s)")

            # ========== PHASE 2: OCR on Cropped Plates ==========
            logger.info("PHASE 2: Performing OCR on detected license plates")

            crop_paths = []
            crop_offsets = []

            # Crop each detected plate with configured pixel padding
            ocr_padding_px = settings.OCR_CROP_PADDING_PX
            for idx, detection in enumerate(detections):
                if "plate" not in detection or "coordinates" not in detection["plate"]:
                    continue

                coords = detection["plate"]["coordinates"]
                x1 = int(coords["x1"])
                y1 = int(coords["y1"])
                x2 = int(coords["x2"])
                y2 = int(coords["y2"])

                crop_result = ImageProcessor.crop_region(image_path, x1, y1, x2, y2, padding_px=ocr_padding_px)
                if crop_result:
                    crop_path, crop_offset_x, crop_offset_y = crop_result
                    crop_paths.append(crop_path)
                    crop_offsets.append((crop_offset_x, crop_offset_y))
                    logger.info(f"Cropped plate {idx + 1}: {crop_path} at offset ({crop_offset_x}, {crop_offset_y})")

            # Perform batch OCR on all cropped plates
            if crop_paths:
                # Encode all crops to base64
                base64_crops = []
                for crop_path in crop_paths:
                    base64_crop = ImageProcessor.encode_image_to_base64(crop_path)
                    if base64_crop:
                        base64_crops.append(base64_crop)
                    else:
                        base64_crops.append(None)
                        logger.error(f"Failed to encode crop: {crop_path}")

                # Batch OCR call. Each position is independent: a failure yields None
                # in that slot only, and the remaining plates are still processed.
                ocr_responses = client.analyze_images_batch(base64_crops, OCR_PROMPT)

                if len(ocr_responses) == len(crop_paths):
                    # Parse each OCR response and scale coordinates to original image
                    pairs = zip(ocr_responses, crop_offsets, strict=False)
                    for idx, (ocr_response, (crop_offset_x, crop_offset_y)) in enumerate(pairs):
                        if not ocr_response or not crop_paths[idx]:
                            # Failed OCR for this crop, add empty OCR data
                            detections[idx]["ocr"] = []
                            continue

                        # Get crop dimensions
                        crop_info = ImageProcessor.get_image_info(crop_paths[idx])
                        if not crop_info:
                            logger.error(f"Failed to get crop info: {crop_paths[idx]}")
                            detections[idx]["ocr"] = []
                            continue

                        crop_h = crop_info["height"]
                        crop_w = crop_info["width"]

                        # Parse OCR response and scale coordinates
                        ocr_data = parse_ocr_response(ocr_response, crop_h, crop_w, crop_offset_x, crop_offset_y)
                        if ocr_data:
                            # Check if text was detected
                            text = ocr_data.get("text", "")
                            confidence = ocr_data.get("confidence", 0)

                            if text and confidence > 0:
                                is_meaningful, reason = DetectionValidator.validate_ocr_text(text)
                                if is_meaningful:
                                    detections[idx]["ocr"] = [
                                        {
                                            "text": text,
                                            "confidence": confidence,
                                            "coordinates": ocr_data.get("coordinates", {}),
                                        }
                                    ]
                                    logger.info(f"OCR result {idx + 1}: '{text}' (confidence: {confidence:.2f})")
                                else:
                                    detections[idx]["ocr"] = []
                                    logger.info(f"OCR result {idx + 1}: text rejected ({reason})")
                            else:
                                detections[idx]["ocr"] = []
                                logger.info(f"OCR result {idx + 1}: No text detected")
                        else:
                            detections[idx]["ocr"] = []
                            logger.error(f"Failed to parse OCR response {idx + 1}")

                # Clean up crop files
                for crop_path in crop_paths:
                    if os.path.exists(crop_path):
                        os.remove(crop_path)

            logger.info(f"Phase 2 complete: OCR processed for {len(detections)} plate(s)")
            summary = f"LLM pipeline complete: {len(detections)} plate(s) detected"
        finally:
            api_call_log.duration_ms = int((time.time() - start_time) * 1000)
            api_call_log.save(update_fields=["duration_ms"])

            # Clean up downscaled image
            if downscaled_path != image_path and os.path.exists(downscaled_path):
                os.remove(downscaled_path)

        return detections, summary

    @staticmethod
    def _handle_canary_cleanup(
        uploaded_image: UploadedImage, save_image: bool, comparison_path: str | None
    ) -> dict[str, Any] | None:
        """
        Handle cleanup for canary requests.

        Args:
            uploaded_image: The uploaded image instance
            save_image: Whether images should be saved
            comparison_path: Path to comparison image

        Returns:
            Result dictionary if cleanup was performed, None otherwise
        """
        # For canary requests with save_image=False, clean up completely
        if not save_image:
            logger.info(f"Cleaning up canary image {uploaded_image.id} ({uploaded_image.filename})")

            # Delete original image file
            if uploaded_image.original_image and os.path.exists(uploaded_image.original_image.path):
                try:
                    os.remove(uploaded_image.original_image.path)
                    logger.info(f"Deleted original image: {uploaded_image.original_image.path}")
                except Exception as e:
                    logger.error(f"Failed to delete original image: {e}")
            else:
                logger.warning(
                    f"Original image file not found: "
                    f"{uploaded_image.original_image.path if uploaded_image.original_image else 'None'}"
                )

            # Delete comparison image if it exists
            if comparison_path and os.path.exists(comparison_path):
                try:
                    os.remove(comparison_path)
                    logger.info(f"Deleted comparison image: {comparison_path}")
                except Exception as e:
                    logger.error(f"Failed to delete comparison image: {e}")

            # Delete database record
            try:
                image_id = uploaded_image.id  # Save ID for logging after deletion
                uploaded_image.delete()
                logger.info(f"Deleted database record for canary image {image_id}")
            except Exception as e:
                logger.error(f"Failed to delete database record: {e}")

            return {"success": True, "message": "Canary image processed and cleaned up"}

        return None
