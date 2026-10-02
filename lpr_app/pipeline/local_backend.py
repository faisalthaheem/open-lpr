"""The local ONNX backend: the default detection and recognition path.

`image_processing_service.py` runs a three-phase procedure that asks a
vision-language model to detect plates and then to read them. This module runs
the same two jobs with local ONNX models, selected by ``PIPELINE_BACKEND``.

It is the default because it is the only path that fits the project's sub-500ms
latency budget: ~60ms per image on CPU against the LLM backend's ~3600ms. The
rollback is one configuration change, ``PIPELINE_BACKEND=llm``.

**What is and is not known about its accuracy.** On the annotated corpus it
detects more reliably than the LLM backend (recall 1.000 vs 0.375) and reads more
plates (0.95 vs 0.375 of detections). Its *text accuracy is unmeasured*, because
the corpus annotates plate boxes with no transcription labels, so there is no
ground truth to score a read against -- and it demonstrably misreads some plates
it does find (``QG.260`` becomes ``0G260``). Higher coverage is not higher
accuracy. The measured numbers are recorded in
``openspec/changes/measure-local-backend-accuracy/COMPARISON.md``.

**The output contract is the whole point.** Both backends return the same
detections collection -- a list of ``{"plate": {...}, "ocr": [...]}`` entries with
the same keys, so the API, the visualizer, the metrics, and the model layer never
branch on which backend ran. A backend-specific key or a different confidence
type would be invisible until it broke a consumer, which is exactly the coupling
this design is avoiding.

One difference is deliberate and visible rather than hidden: the local detector
returns the plate confidence it measured, while the LLM path also passes every
detection through ``DetectionValidator``'s geometric checks. Those same checks
run here, on the same thresholds, so a caller cannot tell the backends apart by
what survives filtering.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

from ..services.detection_validator import DetectionValidator
from .stages.detect import Detection, PlateDetectionStage
from .stages.ocr import PlateOCRStage, RecognitionResult
from .stages.rectify import RectificationError, RectifyPlateStage

logger = logging.getLogger(__name__)

LLM_BACKEND = "llm"
LOCAL_BACKEND = "local"
KNOWN_BACKENDS = (LLM_BACKEND, LOCAL_BACKEND)

#: Used when no backend is named. Matches ``PIPELINE_BACKEND``'s default; the two
#: must agree, or a deployment that omits the setting would resolve differently
#: depending on which one asked.
DEFAULT_BACKEND = LOCAL_BACKEND


class LocalBackendError(Exception):
    """The local backend could not be constructed or run."""


@dataclass
class StageTiming:
    """One stage's measured cost and whether it met its budget."""

    name: str
    status: str
    duration: float = 0.0
    budget: float | None = None
    reason: str = ""

    @property
    def within_budget(self) -> bool | None:
        """None when no budget applies, so 'unmeasured' is not 'over budget'."""
        if self.budget is None:
            return None
        return self.duration <= self.budget


@dataclass
class LocalPipelineResult:
    """What the local backend produced, plus what it cost."""

    detections: list[dict[str, Any]] = field(default_factory=list)
    timings: dict[str, StageTiming] = field(default_factory=dict)
    duration: float = 0.0

    def within_budget(self, budget: float | None) -> bool | None:
        if budget is None:
            return None
        return self.duration <= budget


def resolve_backend(name: str | None) -> str:
    """Validate a backend name, falling back to the default backend.

    An unknown value is a configuration error rather than something to guess at:
    silently falling back would hide a typo behind a working backend, which is
    worse here than usual because the two backends differ in cost per request by
    two orders of magnitude.
    """
    candidate = (name or DEFAULT_BACKEND).strip().lower()
    if candidate not in KNOWN_BACKENDS:
        raise LocalBackendError(f"unknown PIPELINE_BACKEND {name!r}; known backends: {list(KNOWN_BACKENDS)}")
    return candidate


def plate_crop_for(image: Image.Image, detection: Detection, padding_px: int, rectify) -> Any:
    """Crop one plate, rectifying when enabled and padding when not.

    The two paths are not interchangeable. A rectified crop already has its
    boundary established by the perspective transform, so expanding it would push
    vehicle bodywork into the recognizer's input. A bypassed crop has no such
    boundary, so the same fixed-pixel padding the LLM path applies is what keeps
    the plate's edge characters inside the crop.
    """
    if rectify:
        # RectifyPlateStage takes a box as (x, y, width, height); Detection.box()
        # is (x1, y1, x2, y2). Converting is not optional: passing the corner pair
        # straight through yields a region spanning from the plate's origin to its
        # far corner as an offset, which rectifies a mostly-car crop.
        x1, y1, x2, y2 = detection.box()
        box = (x1, y1, x2 - x1, y2 - y1)
        return rectify.rectify({"image": image, "box": box, "layout": detection.layout}).crop

    width, height = image.size
    x1, y1, x2, y2 = detection.box()
    x1 = int(max(0, x1 - padding_px))
    y1 = int(max(0, y1 - padding_px))
    x2 = int(min(width, x2 + padding_px))
    y2 = int(min(height, y2 + padding_px))
    return image.crop((x1, y1, x2, y2))


def record_text(
    detections: list[dict[str, Any]],
    index: int,
    result: RecognitionResult,
) -> dict[str, Any]:
    """Attach validated recognized text to one detection, or discard it.

    The recognized text goes through the same ``DetectionValidator.validate_ocr_text``
    the LLM backend uses, so "implausible" means the same thing on both paths. A
    rejected read leaves ``ocr`` as an empty list rather than being dropped from
    the detections collection: the plate was genuinely detected, and hiding it
    would make the detector's recall unreadable.

    The text's coordinates are the plate's own box. The recognizer emits characters,
    not word geometry, so claiming a tighter box would be fabrication; the plate
    region is the honest extent of the text.
    """
    detection = detections[index]
    text = result.text
    if not text or result.confidence <= 0:
        detection["ocr"] = []
        return detection

    is_valid, reason = DetectionValidator.validate_ocr_text(text)
    if not is_valid:
        logger.info("plate %d: recognized text rejected (%s)", index + 1, reason)
        detection["ocr"] = []
        return detection

    detection["ocr"] = [
        {
            "text": text,
            "confidence": round(float(result.confidence), 4),
            "coordinates": dict(detection["plate"]["coordinates"]),
        }
    ]
    logger.info("plate %d: read '%s' (confidence %.2f)", index + 1, text, result.confidence)
    return detection


class LocalPlateBackend:
    """Runs detection and recognition locally, in that order.

    Constructed once and reused, because loading an ONNX session per image would
    dominate the latency it is trying to stay under. Stage instances hold their
    sessions, so a second image costs inference alone.
    """

    def __init__(
        self,
        *,
        detector_model: str | None = None,
        detector_input_size: tuple[int, int] = (640, 640),
        detector_conf_threshold: float = 0.3,
        detector_nms_iou: float = 0.45,
        layout_threshold: float = 2.0,
        ocr_model: str | None = None,
        ocr_dict: str | None = None,
        ocr_batch_size: int = 8,
        ocr_charset_profile: str = "alphanumeric",
        ocr_split_stacked: bool = False,
        rectify_enabled: bool = True,
        rectify_output_size: tuple[int, int] = (320, 100),
        rectify_min_area: float = 64.0,
        provider: str = "cpu",
        crop_padding_px: int = 25,
        validator: DetectionValidator | None = None,
        stage_budgets: dict[str, float] | None = None,
    ) -> None:
        self.detector = PlateDetectionStage(
            model_path=detector_model,
            input_size=detector_input_size,
            conf_threshold=detector_conf_threshold,
            nms_iou=detector_nms_iou,
            layout_threshold=layout_threshold,
        )
        self.rectifier = RectifyPlateStage(
            output_size=rectify_output_size,
            min_area=rectify_min_area,
            enabled=rectify_enabled,
        )
        self.recogniser = PlateOCRStage(
            model_path=ocr_model,
            dict_path=ocr_dict,
            batch_size=ocr_batch_size,
            split_stacked=ocr_split_stacked,
        )
        self.validator = validator or DetectionValidator()
        self.crop_padding_px = int(crop_padding_px)
        self.stage_budgets = dict(stage_budgets or {})

        for stage in (self.detector, self.recogniser):
            stage.context.provider = provider

    def warm_up(self) -> None:
        """Load both models up front, so first-request latency is not an outlier."""
        self.detector.load()
        self.recogniser.load()

    def run(self, image: Image.Image) -> LocalPipelineResult:
        """Detect and read every plate in one image."""
        started = time.perf_counter()
        result = LocalPipelineResult()

        detection_started = time.perf_counter()
        detections = self.detector.run({"image": image})["detections"]
        result.timings[self.detector.name] = StageTiming(
            name=self.detector.name,
            status="ok",
            duration=time.perf_counter() - detection_started,
            budget=self.stage_budgets.get(self.detector.name),
        )

        # The same geometric sanity checks the LLM path applies, on the same
        # thresholds, so the two backends discard the same detections. Validated
        # one at a time rather than through filter_detections so each surviving
        # detection stays paired with the Detection it came from.
        survivors: list[Detection] = []
        for detection in detections:
            payload = {"plate": detection.to_dict()}
            is_valid, reason = self.validator.validate_plate_detection(payload, image.height, image.width)
            if is_valid:
                survivors.append(detection)
                result.detections.append(payload)
            else:
                logger.info("Filtered detection at %s: %s", detection.box(), reason)

        crops: list[tuple[Image.Image, str | None]] = []
        for detection in survivors:
            try:
                crops.append((plate_crop_for(image, detection, self.crop_padding_px, self.rectifier), detection.layout))
            except (RectificationError, OSError, ValueError) as exc:
                # A plate that cannot be cropped is still a detected plate; it
                # just carries no text. Dropping it would misreport recall.
                logger.info("plate at %s could not be cropped: %s", detection.box(), exc)
                crops.append(None)  # type: ignore[arg-type]

        readable = [crop for crop in crops if crop is not None]
        ocr_started = time.perf_counter()
        reads: list[RecognitionResult] = self.recogniser.read_plates(readable)
        ocr_duration = time.perf_counter() - ocr_started
        result.timings[self.recogniser.name] = StageTiming(
            name=self.recogniser.name,
            status="ok" if reads else "skipped",
            duration=ocr_duration,
            budget=self.stage_budgets.get(self.recogniser.name),
            reason="" if reads else "no readable plate crops",
        )

        cursor = 0
        for index in range(len(result.detections)):
            if crops[index] is None:
                result.detections[index]["ocr"] = []
                continue
            record_text(result.detections, index, reads[cursor])
            cursor += 1

        result.duration = time.perf_counter() - started
        return result


def build_local_backend_from_settings() -> LocalPlateBackend:
    """Construct the backend from Django settings.

    Model paths are resolved relative to ``PIPELINE_MODEL_DIR`` so a deployment
    can mount artifacts anywhere.

    The artifacts are required, not optional: this is the default backend, so a
    missing one means the application cannot process images at all. That failure
    is raised as a ``StageError`` naming the resolved path at load time rather
    than swallowed, because the alternative -- processing images and returning no
    plates -- is indistinguishable from a working service that found nothing.
    """
    from django.conf import settings

    def resolve(filename: str | None) -> str | None:
        if not filename:
            return None
        return os.path.join(settings.PIPELINE_MODEL_DIR, filename)

    return LocalPlateBackend(
        detector_model=resolve(settings.PIPELINE_DETECTOR_MODEL),
        detector_input_size=tuple(settings.PIPELINE_DETECTOR_INPUT_SIZE),  # type: ignore[arg-type]
        detector_conf_threshold=settings.PIPELINE_DETECTOR_CONF_THRESHOLD,
        detector_nms_iou=settings.PIPELINE_DETECTOR_NMS_IOU,
        layout_threshold=settings.PIPELINE_LAYOUT_THRESHOLD,
        ocr_model=resolve(settings.PIPELINE_OCR_MODEL),
        ocr_dict=resolve(settings.PIPELINE_OCR_DICT),
        ocr_batch_size=settings.PIPELINE_OCR_BATCH_SIZE,
        ocr_charset_profile=settings.PIPELINE_OCR_CHARSET_PROFILE,
        ocr_split_stacked=settings.PIPELINE_OCR_SPLIT_STACKED,
        rectify_enabled=settings.PIPELINE_RECTIFY_ENABLED,
        provider=settings.PIPELINE_PROVIDER,
        crop_padding_px=settings.OCR_CROP_PADDING_PX,
        validator=DetectionValidator(
            min_confidence=settings.DETECTION_MIN_CONFIDENCE,
            min_box_area_fraction=settings.DETECTION_MIN_BOX_AREA_FRACTION,
            max_box_area_fraction=settings.DETECTION_MAX_BOX_AREA_FRACTION,
            min_plate_aspect=settings.DETECTION_MIN_PLATE_ASPECT,
            max_plate_aspect=settings.DETECTION_MAX_PLATE_ASPECT,
        ),
        stage_budgets=settings.PIPELINE_STAGE_BUDGETS,
    )
