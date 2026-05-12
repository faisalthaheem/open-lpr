"""
Image processing service for LPR application.

This service handles the core image processing workflow, including
API integration, coordinate scaling, and file operations.
"""

import logging
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional

from django.conf import settings

from ..models import UploadedImage, ProcessingLog
from .qwen_client import (
    get_qwen_client, 
    DETECTION_PROMPT, 
    OCR_PROMPT,
    parse_detection_response, 
    parse_ocr_response
)
from .image_processor import ImageProcessor
from .bbox_visualizer import visualize_lpr_on_image, create_side_by_side_comparison

logger = logging.getLogger(__name__)


class ImageProcessingService:
    """Service for handling image processing workflow."""
    
    @staticmethod
    def process_uploaded_image(uploaded_image: UploadedImage, save_image: bool = True) -> Dict[str, Any]:
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
        logger.info(f"DEBUG: process_uploaded_image called with save_image={save_image}")
        
        try:
            # Update status to processing
            uploaded_image.processing_status = 'processing'
            uploaded_image.save()
            logger.info(f"DEBUG: Status updated to processing")
            
            # Log API call start
            ProcessingLog.objects.create(
                uploaded_image=uploaded_image,
                status='api_call',
                message='Starting Phase 1: License plate detection'
            )
            
            start_time = time.time()
            
            # Get original image path
            image_path = uploaded_image.original_image.path
            
            # Get original image dimensions for coordinate scaling
            original_image_info = ImageProcessor.get_image_info(image_path)
            if not original_image_info:
                return {'success': False, 'error': 'Failed to get original image info'}
            
            original_h = original_image_info['height']
            original_w = original_image_info['width']
            
            # ========== PHASE 1: License Plate Detection ==========
            logger.info(f"PHASE 1: Detecting license plates on downscaled image")
            
            # Downscale image for detection (size derived from plate height requirements)
            downscaled_path = ImageProcessor.downscale_for_detection(
                image_path,
                min_plate_height=settings.MIN_PLATE_HEIGHT,
                plate_height_fraction=settings.PLATE_HEIGHT_FRACTION,
            )
            if not downscaled_path:
                return {'success': False, 'error': 'Failed to downscale image for detection'}
            
            # Get downscaled image dimensions
            downscaled_info = ImageProcessor.get_image_info(downscaled_path)
            if not downscaled_info:
                return {'success': False, 'error': 'Failed to get downscaled image info'}
            downscaled_h = downscaled_info['height']
            downscaled_w = downscaled_info['width']
            
            # Encode downscaled image to base64
            base64_downscaled = ImageProcessor.encode_image_to_base64(downscaled_path)
            if not base64_downscaled:
                return {'success': False, 'error': 'Failed to encode downscaled image'}
            
            # Call API with detection-only prompt
            client = get_qwen_client()
            detection_prompt = DETECTION_PROMPT.replace('[actual filename of the image]', uploaded_image.filename)
            detection_response = client.analyze_image(base64_downscaled, detection_prompt)
            
            if not detection_response:
                return {'success': False, 'error': 'Phase 1 API call failed'}
            
            # Parse detection response and scale coordinates to original image
            detection_data = parse_detection_response(detection_response, original_h, original_w, downscaled_h, downscaled_w)
            if not detection_data:
                return {'success': False, 'error': 'Failed to parse Phase 1 response'}
            
            # Extract detections
            detections = detection_data.get('detections', [])
            if not detections:
                logger.info(f"No license plates detected in image")
                detections = []
            
            logger.info(f"Phase 1 complete: Detected {len(detections)} license plate(s)")
            
            # Clean up downscaled image
            if downscaled_path != image_path and os.path.exists(downscaled_path):
                os.remove(downscaled_path)
            
            # ========== PHASE 2: OCR on Cropped Plates ==========
            logger.info(f"PHASE 2: Performing OCR on detected license plates")
            
            crop_paths = []
            crop_offsets = []
            
            # Crop each detected plate with 10% padding
            for idx, detection in enumerate(detections):
                if 'plate' not in detection or 'coordinates' not in detection['plate']:
                    continue
                
                coords = detection['plate']['coordinates']
                x1 = int(coords['x1'])
                y1 = int(coords['y1'])
                x2 = int(coords['x2'])
                y2 = int(coords['y2'])
                
                # Crop region with 10% padding
                crop_result = ImageProcessor.crop_region(image_path, x1, y1, x2, y2, padding_pct=0.1)
                if crop_result:
                    crop_path, crop_offset_x, crop_offset_y = crop_result
                    crop_paths.append(crop_path)
                    crop_offsets.append((crop_offset_x, crop_offset_y))
                    logger.info(f"Cropped plate {idx + 1}: {crop_path} at offset ({crop_offset_x}, {crop_offset_y})")
            
            # Perform batch OCR on all cropped plates
            ocr_results = []
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
                
                # Batch OCR call
                ocr_responses = client.analyze_images_batch(base64_crops, OCR_PROMPT)
                
                if ocr_responses:
                    # Parse each OCR response and scale coordinates to original image
                    for idx, (ocr_response, (crop_offset_x, crop_offset_y)) in enumerate(zip(ocr_responses, crop_offsets)):
                        if not ocr_response or not crop_paths[idx]:
                            # Failed OCR for this crop, add empty OCR data
                            detections[idx]['ocr'] = []
                            continue
                        
                        # Get crop dimensions
                        crop_info = ImageProcessor.get_image_info(crop_paths[idx])
                        if not crop_info:
                            logger.error(f"Failed to get crop info: {crop_paths[idx]}")
                            detections[idx]['ocr'] = []
                            continue
                        
                        crop_h = crop_info['height']
                        crop_w = crop_info['width']
                        
                        # Parse OCR response and scale coordinates
                        ocr_data = parse_ocr_response(ocr_response, crop_h, crop_w, crop_offset_x, crop_offset_y)
                        if ocr_data:
                            # Check if text was detected
                            text = ocr_data.get('text', '')
                            confidence = ocr_data.get('confidence', 0)
                            
                            if text and confidence > 0:
                                detections[idx]['ocr'] = [{
                                    'text': text,
                                    'confidence': confidence,
                                    'coordinates': ocr_data.get('coordinates', {})
                                }]
                                logger.info(f"OCR result {idx + 1}: '{text}' (confidence: {confidence:.2f})")
                            else:
                                detections[idx]['ocr'] = []
                                logger.info(f"OCR result {idx + 1}: No text detected")
                        else:
                            detections[idx]['ocr'] = []
                            logger.error(f"Failed to parse OCR response {idx + 1}")
                
                # Clean up crop files
                for crop_path in crop_paths:
                    if os.path.exists(crop_path):
                        os.remove(crop_path)
            
            logger.info(f"Phase 2 complete: OCR processed for {len(detections)} plate(s)")
            
            # ========== PHASE 3: Merge and Visualize ==========
            logger.info(f"PHASE 3: Merging results and visualizing")
            
            # Create merged response in expected format
            merged_response = {
                'filename': uploaded_image.filename,
                'detections': detections
            }
            
            # Conditionally visualize and save processed images
            output_path = None
            comparison_path = None
            
            if save_image:
                # Visualize results
                output_filename = f"processed_{uploaded_image.filename}"
                output_path = os.path.join(
                    os.path.dirname(str(uploaded_image.original_image.path)),
                    output_filename
                )
                
                success = visualize_lpr_on_image(image_path, merged_response, output_path)
                
                if not success:
                    return {'success': False, 'error': 'Failed to create visualization'}
                
                # Create side-by-side comparison
                comparison_filename = f"comparison_{uploaded_image.filename}"
                comparison_path = os.path.join(
                    os.path.dirname(str(uploaded_image.original_image.path)),
                    comparison_filename
                )
                
                create_side_by_side_comparison(image_path, output_path, comparison_path)
            
            # Update database record
            uploaded_image.api_response = merged_response  # type: ignore[arg-type]
            uploaded_image.processing_status = 'completed'
            uploaded_image.processing_timestamp = datetime.now()
            
            # Only save processed image path if we actually saved image
            if save_image and output_path:
                output_path_str = str(output_path)
                uploaded_image.processed_image.name = output_path_str.replace(str(settings.MEDIA_ROOT) + '/', '')
            
            logger.info(f"DEBUG: About to save record, save_image={save_image}")
            uploaded_image.save()
            logger.info(f"DEBUG: Record saved, checking cleanup condition")
            
            # Handle cleanup for canary requests
            result = ImageProcessingService._handle_canary_cleanup(
                uploaded_image, save_image, comparison_path
            )
            if result:
                return result
            
            logger.info(f"DEBUG: Not cleaning up because save_image={save_image}")
            
            # Log success
            duration = (time.time() - start_time) * 1000
            ProcessingLog.objects.create(
                uploaded_image=uploaded_image,
                status='success',
                message=f'Processing completed successfully',
                duration_ms=int(duration)
            )
            
            processing_duration = time.time() - processing_start_time
            
            return {
                'success': True, 
                'processed_image_path': output_path,
                'processing_duration': processing_duration
            }
            
        except Exception as e:
            logger.error(f"Error in process_uploaded_image: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Update status to failed
            uploaded_image.processing_status = 'failed'
            uploaded_image.error_message = str(e)
            uploaded_image.save()
            
            # Log error
            ProcessingLog.objects.create(
                uploaded_image=uploaded_image,
                status='error',
                message=f'Processing failed: {str(e)}'
            )
            
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _handle_canary_cleanup(uploaded_image: UploadedImage, save_image: bool, comparison_path: Optional[str]) -> Optional[Dict[str, Any]]:
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
        logger.info(f"DEBUG: save_image={save_image}, about to check cleanup condition")
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
                logger.warning(f"Original image file not found: {uploaded_image.original_image.path if uploaded_image.original_image else 'None'}")
            
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
            
            return {'success': True, 'message': 'Canary image processed and cleaned up'}
        
        return None
