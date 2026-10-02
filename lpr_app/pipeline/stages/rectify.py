"""Classical perspective correction of a detected plate region.

This stage performs no model inference. Its whole purpose is to hand the
recognizer a clean, deskewed plate at a fixed shape so that OCR accuracy does
not depend on the detector having produced a perfect quadrilateral.

The corpus supplies only axis-aligned boxes, so a bounding region is the
minimum viable input: corners are derived from it unless a detector provides
explicit corner geometry, which is preferred when present.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

from .base import Stage, StageError

logger = logging.getLogger(__name__)

# Layouts differ in proportion. The annotated corpus is bimodal: roughly 45% of
# plates are stacked two-line (ratio well under 2.0) and a large minority are
# single-line US/EU plates between 2.6 and 3.4. A single global ratio would
# squeeze one group or waste resolution on the other, so ratios are
# configuration and a layout is declared per region.
DEFAULT_LAYOUT_RATIOS = {
    "stacked": 1.6,
    "single_line": 3.0,
}

DEFAULT_OUTPUT_SIZE = (320, 100)


@dataclass
class RectificationResult:
    """Outcome of rectifying one detection."""

    crop: Any  # PIL.Image
    corners: tuple[tuple[float, float], ...]
    layout: str
    ok: bool = True
    reason: str = ""


class RectificationError(StageError):
    """The plate region could not be rectified."""


def _signed_area(points: list[tuple[float, float]]) -> float:
    """Twice the signed area of a polygon given as a point list."""
    total = 0.0
    for i, (x0, y0) in enumerate(points):
        x1, y1 = points[(i + 1) % len(points)]
        total += x0 * y1 - x1 * y0
    return total / 2.0


def _is_simple_quadrilateral(points: list[tuple[float, float]]) -> bool:
    """Whether the four points form a simple (non self-intersecting) polygon.

    Consecutive edges are tested for proper intersection. Points are expected in
    top-left, top-right, bottom-right, bottom-left order.
    """
    n = len(points)
    for i in range(n):
        a1, a2 = points[i], points[(i + 1) % n]
        for j in range(i + 1, n):
            # Skip edges that share an endpoint; adjacent edges always touch.
            if j == i or (j + 1) % n == i or (i + 1) % n == j:
                continue
            b1, b2 = points[j], points[(j + 1) % n]
            if _segments_properly_intersect(a1, a2, b1, b2):
                return False
    return True


def _cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _segments_properly_intersect(
    a1: tuple[float, float], a2: tuple[float, float], b1: tuple[float, float], b2: tuple[float, float]
) -> bool:
    d1 = _cross(b1, b2, a1)
    d2 = _cross(b1, b2, a2)
    d3 = _cross(a1, a2, b1)
    d4 = _cross(a1, a2, b2)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


class RectifyPlateStage(Stage):
    """Map a detected plate region to a deskewed, fixed-shape crop."""

    name = "rectify_plate"
    inputs = ("plate",)
    outputs = ("rectified",)

    def __init__(
        self,
        context=None,
        *,
        output_size: tuple[int, int] = DEFAULT_OUTPUT_SIZE,
        layout: str = "single_line",
        layout_ratios: dict[str, float] | None = None,
        min_area: float = 64.0,
        enabled: bool = True,
    ) -> None:
        super().__init__(context)
        self.output_size = tuple(output_size)
        self.layout = layout
        self.layout_ratios = dict(layout_ratios or DEFAULT_LAYOUT_RATIOS)
        self.min_area = float(min_area)
        self.enabled = enabled

    @property
    def has_model(self) -> bool:
        # Rectification is classical: it loads nothing and runs no inference.
        return False

    def aspect_ratio_for(self, layout: str | None = None) -> float:
        key = layout or self.layout
        try:
            return float(self.layout_ratios[key])
        except KeyError as exc:
            raise RectificationError(
                f"unknown plate layout {key!r}; configured layouts: {sorted(self.layout_ratios)}"
            ) from exc

    def target_size_for(self, layout: str | None = None) -> tuple[int, int]:
        """Output dimensions honouring the layout's aspect ratio and configured height."""
        _, height = self.output_size
        ratio = self.aspect_ratio_for(layout)
        return max(1, int(round(height * ratio))), height

    def run(self, data: dict[str, Any]) -> dict[str, Any]:
        plate = data.get("plate")
        if plate is None:
            raise RectificationError("rectify_plate received no plate region")

        if not self.enabled:
            return {"rectified": self._bypass(plate)}

        result = self.rectify(plate)
        return {"rectified": result}

    # -- geometry ----------------------------------------------------------

    def corners_for(self, plate: dict[str, Any]) -> tuple[tuple[float, float], ...]:
        """Explicit corner geometry when present, else the bounding region's corners."""
        explicit = plate.get("corners")
        if explicit:
            points = [(float(x), float(y)) for x, y in explicit]
            if len(points) != 4:
                raise RectificationError(f"expected 4 corners, got {len(points)}")
            return tuple(points)

        box = plate.get("box")
        if not box:
            raise RectificationError("plate region has neither 'corners' nor 'box'")
        x, y, w, h = (float(v) for v in box)
        if w <= 0 or h <= 0:
            raise RectificationError(f"plate box has non-positive size: {box}")
        # Clockwise from top-left, matching the corner order rectification expects.
        return ((x, y), (x + w, y), (x + w, y + h), (x, y + h))

    def rectify(self, plate: dict[str, Any]) -> RectificationResult:
        """Rectify one plate region, raising ``RectificationError`` when degenerate."""
        corners = self.corners_for(plate)
        layout = plate.get("layout") or self.layout

        if not _is_simple_quadrilateral(list(corners)):
            raise RectificationError(f"self-intersecting corner geometry: {corners}")

        area = abs(_signed_area(list(corners)))
        if area < self.min_area:
            raise RectificationError(f"plate area {area:.1f}px below minimum {self.min_area:.1f}px")

        image = plate.get("image")
        if image is None:
            raise RectificationError("plate region carries no image to crop")

        width, height = self.target_size_for(layout)
        crop = self._perspective_crop(image, corners, (width, height))
        return RectificationResult(crop=crop, corners=corners, layout=layout)

    def _perspective_crop(self, image: Any, corners: tuple[tuple[float, float], ...], size: tuple[int, int]) -> Any:
        """Map the quadrilateral onto a rectangle using Pillow's perspective map.

        Pillow is already a runtime dependency, so this avoids pulling in OpenCV
        purely for a 3x3 homography.
        """
        from PIL import Image

        width, height = size
        source = corners
        destination = [(0.0, 0.0), (float(width), 0.0), (float(width), float(height)), (0.0, float(height))]

        # Pillow expects the inverse map (destination -> source), so solve the
        # homography from destination quads to source quads.
        try:
            coeffs = _find_coeffs(destination, source, (width, height))
        except (ZeroDivisionError, ValueError) as exc:
            raise RectificationError(f"degenerate corner geometry: {exc}") from exc

        return image.transform(size, Image.PERSPECTIVE, coeffs, resample=Image.BICUBIC)

    def _bypass(self, plate: dict[str, Any]) -> RectificationResult:
        """Crop from the bounding region with no transform at all."""
        image = plate.get("image")
        if image is None:
            raise RectificationError("plate region carries no image to crop")

        if plate.get("corners"):
            corners = self.corners_for(plate)
            xs = [p[0] for p in corners]
            ys = [p[1] for p in corners]
            box = (min(xs), min(ys), max(xs), max(ys))
        else:
            x, y, w, h = (float(v) for v in plate["box"])
            box = (x, y, x + w, y + h)

        crop = image.crop(tuple(int(round(v)) for v in box))
        return RectificationResult(crop=crop, corners=(), layout=plate.get("layout") or self.layout)


def _find_coeffs(
    src: list[tuple[float, float]], dst: list[tuple[float, float]], shape: tuple[int, int]
) -> tuple[float, ...]:
    """Solve the 8-coefficient perspective transform mapping src onto dst.

    Returns coefficients in the order Pillow's ``PERSPECTIVE`` transform expects.
    """
    matrix = []
    for (x, y), (u, v) in zip(src, dst, strict=True):
        matrix.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        matrix.append([0, 0, 0, x, y, 1, -v * x, -v * y])

    import numpy as np

    a = np.array(matrix, dtype=np.float64)
    b = np.array(dst, dtype=np.float64).reshape(8)
    try:
        coeffs = np.linalg.solve(a, b)
    except np.linalg.LinAlgError as exc:
        raise ValueError("corner geometry is degenerate; transform is singular") from exc
    return tuple(float(c) for c in coeffs)


def guess_layout(width: float, height: float, stacked_threshold: float = 2.0) -> str:
    """Classify a plate's layout from its region aspect ratio."""
    if height <= 0 or not math.isfinite(height):
        return "single_line"
    return "stacked" if (width / height) < stacked_threshold else "single_line"
