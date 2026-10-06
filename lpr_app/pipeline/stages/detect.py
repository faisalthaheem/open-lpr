"""Local ONNX plate detector.

Reads an image, produces one detection per plate. The output shape matches what
``image_processing_service.py`` already populates from the LLM backend, so
callers and the API do not branch on which backend ran.

Coordinate handling is explicit rather than implicit: the detector sees a
letterboxed resize for speed, and every returned coordinate is mapped back into
the original image's coordinate space and clamped to its bounds.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image

from ..runtime.onnx import run_session
from .base import Stage, StageError

logger = logging.getLogger(__name__)

# YOLOX letterboxes to a fixed input with per-side padding rather than stretching,
# so a plate's proportions survive the resize. Coordinates are scaled back by
# removing the padding and dividing by the scale factor.
DEFAULT_INPUT_SIZE = (640, 640)


@dataclass
class Detection:
    """One detected plate in original-image coordinates."""

    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    corners: list[tuple[float, float]] | None = None
    layout: str | None = None

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)

    def box(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)

    def to_dict(self) -> dict[str, Any]:
        """The shape the API already consumes."""
        payload: dict[str, Any] = {
            "confidence": round(float(self.confidence), 4),
            "coordinates": {
                "x1": int(round(self.x1)),
                "y1": int(round(self.y1)),
                "x2": int(round(self.x2)),
                "y2": int(round(self.y2)),
            },
        }
        if self.corners:
            payload["corners"] = [[round(x, 2), round(y, 2)] for x, y in self.corners]
        return payload


@dataclass
class DetectionResult:
    """Detections for one image, plus the mapping used to reach them."""

    detections: list[Detection] = field(default_factory=list)
    input_size: tuple[int, int] = DEFAULT_INPUT_SIZE
    scale: float = 1.0
    pad: tuple[float, float] = (0.0, 0.0)

    def to_dict(self) -> list[dict[str, Any]]:
        return [d.to_dict() for d in self.detections]


def letterbox(image: Image.Image, size: tuple[int, int]) -> tuple[np.ndarray, float, tuple[float, float]]:
    """Resize preserving aspect ratio and pad to ``size``.

    Returns the CHW float array the detector expects, the scale factor, and the
    (pad_x, pad_y) applied, which together invert the transform.
    """
    target_w, target_h = size
    src_w, src_h = image.size
    if src_w <= 0 or src_h <= 0:
        raise StageError(f"cannot letterbox a {src_w}x{src_h} image")

    scale = min(target_w / src_w, target_h / src_h)
    new_w = max(1, int(round(src_w * scale)))
    new_h = max(1, int(round(src_h * scale)))

    resized = image.resize((new_w, new_h), Image.BILINEAR)
    canvas = Image.new("RGB", (target_w, target_h), (114, 114, 114))
    pad_x = (target_w - new_w) / 2.0
    pad_y = (target_h - new_h) / 2.0
    canvas.paste(resized, (int(round(pad_x)), int(round(pad_y))))

    arr = np.asarray(canvas, dtype=np.float32)
    # YOLOX ONNX exports take raw 0-255 pixels, not values normalised to 0-1.
    arr = np.transpose(arr, (2, 0, 1))[np.newaxis, ...]
    return np.ascontiguousarray(arr), scale, (pad_x, pad_y)


def scale_box(
    box: tuple[float, float, float, float],
    scale: float,
    pad: tuple[float, float],
    image_size: tuple[int, int],
) -> tuple[float, float, float, float]:
    """Map a box from letterboxed space back to the original image, clamped."""
    pad_x, pad_y = pad
    x1 = (box[0] - pad_x) / scale
    y1 = (box[1] - pad_y) / scale
    x2 = (box[2] - pad_x) / scale
    y2 = (box[3] - pad_y) / scale

    img_w, img_h = image_size
    return (
        min(max(0.0, x1), float(img_w)),
        min(max(0.0, y1), float(img_h)),
        min(max(0.0, x2), float(img_w)),
        min(max(0.0, y2), float(img_h)),
    )


def box_iou(a: Detection, b: Detection) -> float:
    """Intersection over union of two axis-aligned boxes."""
    ix1, iy1 = max(a.x1, b.x1), max(a.y1, b.y1)
    ix2, iy2 = min(a.x2, b.x2), min(a.y2, b.y2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


def guess_layout(detection: Detection, stacked_threshold: float = 2.0) -> str:
    """Classify a detection's layout from its aspect ratio.

    The corpus is bimodal: roughly 45% of plates are stacked two-line (ratio well
    under 2.0) and a large minority are single-line US/EU plates between 2.6 and
    3.4. Recognition branches on this, so it is decided here where the geometry
    is known.
    """
    if detection.height <= 0:
        return "single_line"
    ratio = detection.width / detection.height
    if not math.isfinite(ratio):
        return "single_line"
    return "stacked" if ratio < stacked_threshold else "single_line"


def decode_yolox(
    predictions: np.ndarray,
    scale: float,
    pad: tuple[float, float],
    image_size: tuple[int, int],
    *,
    input_size: tuple[int, int] = DEFAULT_INPUT_SIZE,
    conf_threshold: float = 0.3,
    nms_iou: float = 0.45,
    layout_threshold: float = 2.0,
) -> list[Detection]:
    """Decode raw YOLOX output into detections in original-image coordinates.

    ``predictions`` is ``(1, num_anchors, 5 + num_classes)`` with rows laid out as
    ``cx, cy, w, h, obj_conf, class_scores...`` in letterboxed input space.
    """
    if predictions.ndim == 3:
        predictions = predictions[0]
    if predictions.ndim != 2:
        raise StageError(f"expected a 2D prediction array, got shape {predictions.shape}")

    input_w, input_h = input_size
    strides = (8, 16, 32)

    # Each level contributes its own anchor count: the output is level-major,
    # with a (H/stride * W/stride) block per stride. Deriving a single block size
    # by dividing the total would be wrong, since the levels differ (6400/1600/400
    # at 640px), so compute each block from its own grid.
    grid_counts = [(input_h // s) * (input_w // s) for s in strides]
    expected_total = sum(grid_counts)
    if predictions.shape[0] != expected_total:
        raise StageError(
            f"prediction count {predictions.shape[0]} does not match the anchor total "
            f"{expected_total} for input size {input_size}"
        )

    candidates: list[Detection] = []
    offset = 0
    for block in grid_counts:
        chunk = predictions[offset : offset + block]
        offset += block

        cls_scores = chunk[:, 5:]
        class_ids = np.argmax(cls_scores, axis=1)
        class_scores = cls_scores[np.arange(len(cls_scores)), class_ids]
        obj_conf = chunk[:, 4]
        scores = obj_conf * class_scores

        keep = scores >= conf_threshold
        if not keep.any():
            continue

        indices = np.nonzero(keep)[0]
        for index in indices:
            cx, cy, w, h = (float(v) for v in chunk[index, :4])
            # The ONNX export already exponentiates width and height, so these
            # arrive as linear pixels. Applying exp() again would be a double
            # decode and inflates every box to an absurd size that clamps to the
            # whole image.
            #
            # cx/cy also arrive as absolute centre coordinates in the exported
            # tensor, so no grid reconstruction is needed here.
            x1 = cx - w / 2
            y1 = cy - h / 2
            x2 = cx + w / 2
            y2 = cy + h / 2
            ox1, oy1, ox2, oy2 = scale_box((x1, y1, x2, y2), scale, pad, image_size)
            if ox2 - ox1 <= 0 or oy2 - oy1 <= 0:
                continue
            candidates.append(
                Detection(
                    x1=ox1,
                    y1=oy1,
                    x2=ox2,
                    y2=oy2,
                    confidence=float(scores[index]),
                )
            )

    return suppress_duplicates(
        candidates,
        iou_threshold=nms_iou,
        layout_threshold=layout_threshold,
    )


def suppress_duplicates(
    detections: list[Detection],
    *,
    iou_threshold: float = 0.45,
    layout_threshold: float = 2.0,
) -> list[Detection]:
    """Collapse substantially overlapping detections, keeping the most confident.

    A stacked two-line plate is one detection covering both rows, so suppression
    runs on the whole plate rather than per row.
    """
    ordered = sorted(detections, key=lambda d: d.confidence, reverse=True)
    kept: list[Detection] = []
    for candidate in ordered:
        if any(box_iou(candidate, existing) > iou_threshold for existing in kept):
            continue
        candidate.layout = guess_layout(candidate, stacked_threshold=layout_threshold)
        kept.append(candidate)
    return kept


class PlateDetectionStage(Stage):
    """Detect license plates with a local ONNX model."""

    name = "detect_plate"
    inputs = ("image",)
    outputs = ("detections",)

    #: YOLOX exports produce a single decoded output tensor.
    ONNX_OUTPUTS = ("output",)

    def __init__(
        self,
        context=None,
        *,
        model_path: str | None = None,
        input_size: tuple[int, int] = DEFAULT_INPUT_SIZE,
        conf_threshold: float = 0.3,
        nms_iou: float = 0.45,
        layout_threshold: float = 2.0,
    ) -> None:
        super().__init__(context)
        self.model_path = model_path
        self.input_size = tuple(input_size)
        self.conf_threshold = float(conf_threshold)
        self.nms_iou = float(nms_iou)
        self.layout_threshold = float(layout_threshold)

    def run(self, data: dict[str, Any]) -> dict[str, Any]:
        image = data.get("image")
        if image is None:
            raise StageError("detect_plate received no image")

        # Load on demand so the stage is usable directly, not only through the
        # graph runner, which is what the benchmark and tests do.
        if self._session is None:
            self.load()

        tensor, scale, pad = letterbox(image, self.input_size)
        feed = {self._session.input_names[0]: tensor}

        outputs = run_session(self._session, feed, self.ONNX_OUTPUTS, stage_name=self.name)
        raw = next(iter(outputs.values()))

        detections = decode_yolox(
            np.asarray(raw),
            scale,
            pad,
            image.size,
            input_size=self.input_size,
            conf_threshold=self.conf_threshold,
            nms_iou=self.nms_iou,
            layout_threshold=self.layout_threshold,
        )
        return {"detections": detections}
