"""
Validation logic for LPR detection and OCR results.

Provides sanity checks to filter out false positives from the vision model,
including bounding box geometry validation and OCR text validation.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DetectionValidator:
    """
    Validates LPR detection and OCR results to filter false positives.

    The vision model occasionally returns hallucinated detections (e.g.,
    identifying a blank hood as a license plate at high confidence). This
    validator applies geometric and textual sanity checks that the model
    itself does not enforce.
    """

    DEFAULT_MIN_CONFIDENCE = 0.5
    DEFAULT_MIN_BOX_AREA_FRACTION = 0.001
    DEFAULT_MAX_BOX_AREA_FRACTION = 0.5
    DEFAULT_MIN_PLATE_ASPECT = 1.5
    DEFAULT_MAX_PLATE_ASPECT = 10.0

    def __init__(
        self,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        min_box_area_fraction: float = DEFAULT_MIN_BOX_AREA_FRACTION,
        max_box_area_fraction: float = DEFAULT_MAX_BOX_AREA_FRACTION,
        min_plate_aspect: float = DEFAULT_MIN_PLATE_ASPECT,
        max_plate_aspect: float = DEFAULT_MAX_PLATE_ASPECT,
    ):
        self.min_confidence = min_confidence
        self.min_box_area_fraction = min_box_area_fraction
        self.max_box_area_fraction = max_box_area_fraction
        self.min_plate_aspect = min_plate_aspect
        self.max_plate_aspect = max_plate_aspect

    def validate_plate_detection(
        self,
        detection: dict[str, Any],
        image_height: int,
        image_width: int,
    ) -> tuple[bool, str | None]:
        """
        Validate a single plate detection.

        Args:
            detection: Detection dict with 'plate' key containing confidence
                and coordinates.
            image_height: Height of the source image in pixels.
            image_width: Width of the source image in pixels.

        Returns:
            Tuple of (is_valid, reason_if_invalid).
        """
        if not isinstance(detection, dict):
            return False, "detection is not a dict"

        plate = detection.get("plate")
        if not isinstance(plate, dict):
            return False, "missing or invalid 'plate' field"

        confidence = plate.get("confidence", 0)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            return False, f"non-numeric confidence: {confidence}"

        if confidence < self.min_confidence:
            return False, f"confidence {confidence:.2f} below threshold {self.min_confidence}"

        coords = plate.get("coordinates")
        if not isinstance(coords, dict):
            return False, "missing or invalid 'coordinates'"

        is_valid, reason = self.validate_bounding_box(
            coords,
            image_height=image_height,
            image_width=image_width,
            min_aspect=self.min_plate_aspect,
            max_aspect=self.max_plate_aspect,
        )
        if not is_valid:
            return False, reason

        return True, None

    def validate_bounding_box(
        self,
        coords: dict[str, Any],
        image_height: int,
        image_width: int,
        min_aspect: float | None = None,
        max_aspect: float | None = None,
    ) -> tuple[bool, str | None]:
        """
        Validate bounding box geometry.

        Checks that:
          - All four coordinate keys exist and are numeric
          - x1 < x2 and y1 < y2 (non-degenerate)
          - Box is within image bounds
          - Box area is within reasonable fraction of image area
          - Box aspect ratio (w/h) is within reasonable range for a plate

        Args:
            coords: Dict with x1, y1, x2, y2 keys.
            image_height: Source image height in pixels.
            image_width: Source image width in pixels.
            min_aspect: Minimum allowed width/height ratio. None to skip.
            max_aspect: Maximum allowed width/height ratio. None to skip.

        Returns:
            Tuple of (is_valid, reason_if_invalid).
        """
        try:
            x1 = int(coords["x1"])
            y1 = int(coords["y1"])
            x2 = int(coords["x2"])
            y2 = int(coords["y2"])
        except (KeyError, TypeError, ValueError):
            return False, "missing or non-numeric coordinates"

        box_w = x2 - x1
        box_h = y2 - y1

        if box_w <= 0 or box_h <= 0:
            return False, f"degenerate box ({box_w}x{box_h})"

        if x1 < 0 or y1 < 0 or x2 > image_width or y2 > image_height:
            return False, (f"box ({x1},{y1})-({x2},{y2}) outside image " f"({image_width}x{image_height})")

        image_area = image_width * image_height
        box_area = box_w * box_h
        area_fraction = box_area / image_area if image_area else 0

        if area_fraction < self.min_box_area_fraction:
            return False, (f"box area {area_fraction:.4f} below minimum " f"{self.min_box_area_fraction}")

        if area_fraction > self.max_box_area_fraction:
            return False, (f"box area {area_fraction:.4f} exceeds maximum " f"{self.max_box_area_fraction}")

        aspect = box_w / box_h if box_h else float("inf")
        if min_aspect is not None and aspect < min_aspect:
            return False, f"aspect ratio {aspect:.2f} below minimum {min_aspect}"
        if max_aspect is not None and aspect > max_aspect:
            return False, f"aspect ratio {aspect:.2f} exceeds maximum {max_aspect}"

        return True, None

    @staticmethod
    def validate_ocr_text(text: str | None) -> tuple[bool, str | None]:
        """
        Validate OCR text content.

        Args:
            text: OCR text string to validate.

        Returns:
            Tuple of (is_valid, reason_if_invalid).
        """
        if text is None:
            return False, "missing OCR text"

        if not isinstance(text, str):
            return False, "OCR text is not a string"

        stripped = text.strip()
        if not stripped:
            return False, "empty OCR text"

        if len(stripped) < 2:
            return False, f"OCR text too short: {stripped!r}"

        if len(stripped) > 20:
            return False, f"OCR text too long ({len(stripped)} chars): {stripped!r}"

        alnum_count = sum(1 for c in stripped if c.isalnum())
        if alnum_count == 0:
            return False, f"OCR text contains no alphanumeric characters: {stripped!r}"

        return True, None

    def filter_detections(
        self,
        detections: list[dict[str, Any]],
        image_height: int,
        image_width: int,
    ) -> list[dict[str, Any]]:
        """
        Filter a list of detections, keeping only valid ones.

        Args:
            detections: List of detection dicts.
            image_height: Source image height in pixels.
            image_width: Source image width in pixels.

        Returns:
            Filtered list of valid detections.
        """
        filtered = []
        for idx, detection in enumerate(detections):
            is_valid, reason = self.validate_plate_detection(detection, image_height, image_width)
            if is_valid:
                filtered.append(detection)
            else:
                logger.info(f"Filtered detection {idx}: {reason}")
        return filtered

    @staticmethod
    def is_meaningful_ocr_text(text: str | None) -> bool:
        """
        Quick check whether OCR text looks like a real plate string.

        Args:
            text: OCR text string.

        Returns:
            True if text appears to be a meaningful plate string.
        """
        if not text or not isinstance(text, str):
            return False

        stripped = text.strip()
        if len(stripped) < 2 or len(stripped) > 20:
            return False

        alnum_count = sum(1 for c in stripped if c.isalnum())
        return alnum_count >= 2
