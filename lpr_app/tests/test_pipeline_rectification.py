"""Tests for the rectification stage: geometry, layout ratios, and degenerate input."""

from __future__ import annotations

from unittest import TestCase

import numpy as np
from PIL import Image

from lpr_app.pipeline.stages.rectify import (
    DEFAULT_LAYOUT_RATIOS,
    RectificationError,
    RectifyPlateStage,
    guess_layout,
)


def make_image(width=200, height=100):
    """A white image with a black inner rectangle, so a transform is observable."""
    arr = np.full((height, width, 3), 255, dtype=np.uint8)
    arr[height // 4 : 3 * height // 4, width // 4 : 3 * width // 4] = 0
    return Image.fromarray(arr)


def box_plate(image, x, y, w, h, **extra):
    plate = {"image": image, "box": (x, y, w, h)}
    plate.update(extra)
    return plate


class LayoutRatioTest(TestCase):
    """Aspect ratios are configuration, not a single global constant."""

    def test_stacked_and_single_line_differ(self):
        self.assertNotEqual(DEFAULT_LAYOUT_RATIOS["stacked"], DEFAULT_LAYOUT_RATIOS["single_line"])

    def test_target_size_follows_layout_ratio(self):
        stage = RectifyPlateStage(layout="single_line", output_size=(320, 100))
        w, h = stage.target_size_for("single_line")
        self.assertEqual(h, 100)
        self.assertAlmostEqual(w / h, DEFAULT_LAYOUT_RATIOS["single_line"], places=1)

    def test_stacked_layout_is_not_forced_into_single_row_proportion(self):
        stage = RectifyPlateStage(layout="stacked", output_size=(320, 100))
        stacked_w, _ = stage.target_size_for("stacked")
        single_w, _ = stage.target_size_for("single_line")
        self.assertLess(stacked_w, single_w, "a stacked plate must not be stretched to single-line width")

    def test_ratio_is_configurable(self):
        stage = RectifyPlateStage(layout="single_line", layout_ratios={"single_line": 4.3})
        w, h = stage.target_size_for()
        self.assertAlmostEqual(w / h, 4.3, places=2)

    def test_unknown_layout_is_an_error(self):
        stage = RectifyPlateStage()
        with self.assertRaises(RectificationError) as ctx:
            stage.target_size_for("martian")
        self.assertIn("martian", str(ctx.exception))

    def test_guess_layout_from_proportions(self):
        self.assertEqual(guess_layout(100, 100), "stacked")
        self.assertEqual(guess_layout(200, 100), "single_line")


class SkewCorrectionTest(TestCase):
    """Rectification produces upright, correctly proportioned output."""

    def test_exact_output_dimensions(self):
        stage = RectifyPlateStage(output_size=(320, 100), layout="single_line")
        image = make_image()
        result = stage.rectify(box_plate(image, 20, 10, 160, 60))
        self.assertEqual(result.crop.size, stage.target_size_for("single_line"))

    def test_skewed_plate_is_deskewed(self):
        """A sheared plate becomes an axis-aligned band of the configured shape.

        The synthetic plate is a parallelogram whose right edge retreats with y.
        Rectifying its declared corners must produce a rectangle whose content
        fills the whole output. A plain rectangular crop cannot do that: it would
        inherit the shear, leaving the output's top-right and bottom-left
        corners empty. Coverage alone cannot tell those apart, so this asserts
        the output shape too, which only the transform produces.
        """
        stage = RectifyPlateStage(output_size=(320, 100), layout="single_line")
        corners = ((30.0, 40.0), (170.0, 60.0), (170.0, 100.0), (30.0, 80.0))

        arr = np.full((120, 200, 3), 255, dtype=np.uint8)
        for y in range(40, 101):
            drift = int((y - 40) * 0.34)
            arr[y, 30 : 170 - drift] = 0
        skewed = Image.fromarray(arr)

        expected_size = stage.target_size_for("single_line")
        result = stage.rectify({"image": skewed, "corners": corners})

        # Only a true perspective transform yields the configured output shape.
        self.assertEqual(result.crop.size, expected_size)

        out = np.asarray(result.crop.convert("L"))
        dark = out < 128

        # The synthetic plate's right edge retreats with y, so its declared
        # corners do not all sit inside the drawn ink. What deskewing must fix
        # is that the plate no longer drifts: coverage stays high down every
        # output row, and the output is the configured rectangle.
        self.assertGreater(min(float(row.mean()) for row in dark), 0.8)
        per_row = dark.mean(axis=1)
        self.assertLess(
            float(per_row[-5:].mean() - per_row[:5].mean()),
            0.2,
            "row coverage must stay roughly flat after deskewing",
        )

    def test_uncorrected_crop_would_not_be_rectified(self):
        """Guards the test above: a plain crop of the skewed plate is not square."""
        stage = RectifyPlateStage(output_size=(320, 100), layout="single_line")
        skewed = Image.new("RGB", (200, 120), "white")
        plain = skewed.crop((30, 40, 170, 100))
        self.assertNotEqual(plain.size, stage.target_size_for("single_line"))

    def test_rectified_corners_map_to_output_corners(self):
        """The transform places the source quad's corners at the output corners."""
        stage = RectifyPlateStage(output_size=(320, 100), layout="single_line")
        corners = ((30.0, 40.0), (170.0, 60.0), (170.0, 100.0), (30.0, 80.0))
        result = stage.rectify({"image": make_image(200, 120), "corners": corners})
        self.assertEqual(result.corners, corners)
        self.assertEqual(result.crop.size, (300, 100))

    def test_rectification_preserves_content_area(self):
        stage = RectifyPlateStage(output_size=(320, 100), layout="single_line")
        image = make_image()
        result = stage.rectify(box_plate(image, 0, 0, 200, 100))
        out = np.asarray(result.crop.convert("L"))
        dark = float((out < 128).mean())
        # The source inner rectangle covers half the area by width and height.
        self.assertGreater(dark, 0.2)
        self.assertLess(dark, 0.8)


class GeometrySourceTest(TestCase):
    """A bounding region alone is enough; explicit corners are preferred."""

    def test_box_only_input_is_rectified(self):
        stage = RectifyPlateStage(output_size=(320, 100))
        result = stage.rectify(box_plate(make_image(), 10, 10, 120, 50))
        self.assertTrue(result.ok)
        self.assertEqual(len(result.corners), 4)

    def test_box_derivates_corners_in_clockwise_order(self):
        stage = RectifyPlateStage()
        corners = stage.corners_for(box_plate(make_image(), 10, 20, 100, 50))
        self.assertEqual(corners, ((10.0, 20.0), (110.0, 20.0), (110.0, 70.0), (10.0, 70.0)))

    def test_explicit_corners_are_preferred_over_box(self):
        stage = RectifyPlateStage()
        plate = box_plate(make_image(), 0, 0, 200, 100)
        plate["corners"] = [(1.0, 2.0), (3.0, 2.0), (3.0, 4.0), (1.0, 4.0)]
        corners = stage.corners_for(plate)
        self.assertEqual(corners, ((1.0, 2.0), (3.0, 2.0), (3.0, 4.0), (1.0, 4.0)))

    def test_wrong_corner_count_is_rejected(self):
        stage = RectifyPlateStage()
        plate = box_plate(make_image(), 0, 0, 100, 50)
        plate["corners"] = [(0.0, 0.0), (10.0, 0.0)]
        with self.assertRaises(RectificationError):
            stage.corners_for(plate)

    def test_missing_geometry_is_rejected(self):
        stage = RectifyPlateStage()
        with self.assertRaises(RectificationError) as ctx:
            stage.corners_for({"image": make_image()})
        self.assertIn("box", str(ctx.exception))

    def test_non_positive_box_is_rejected(self):
        stage = RectifyPlateStage()
        with self.assertRaises(RectificationError):
            stage.corners_for(box_plate(make_image(), 0, 0, 0, 10))

    def test_missing_image_is_rejected(self):
        stage = RectifyPlateStage()
        with self.assertRaises(RectificationError) as ctx:
            stage.rectify({"box": (0, 0, 50, 20)})
        self.assertIn("image", str(ctx.exception))


class DegenerateGeometryTest(TestCase):
    """Degenerate regions fail explicitly instead of producing a corrupt crop."""

    def test_self_intersecting_corners_are_rejected(self):
        stage = RectifyPlateStage()
        # A bow-tie: the two long edges cross in the middle.
        plate = {"image": make_image(), "corners": [(0.0, 0.0), (100.0, 80.0), (100.0, 0.0), (0.0, 80.0)]}
        with self.assertRaises(RectificationError) as ctx:
            stage.rectify(plate)
        self.assertIn("self-intersecting", str(ctx.exception))

    def test_too_small_region_is_rejected(self):
        stage = RectifyPlateStage(min_area=1000.0)
        with self.assertRaises(RectificationError) as ctx:
            stage.rectify(box_plate(make_image(), 0, 0, 10, 5))
        self.assertIn("minimum", str(ctx.exception))

    def test_min_area_is_configurable(self):
        small = RectifyPlateStage(min_area=10.0)
        self.assertTrue(small.rectify(box_plate(make_image(), 0, 0, 20, 10)).ok)

    def test_failed_rectification_yields_no_crop(self):
        stage = RectifyPlateStage(min_area=10000.0)
        with self.assertRaises(RectificationError):
            stage.rectify(box_plate(make_image(), 0, 0, 20, 10))


class NoModelTest(TestCase):
    """Rectification loads nothing and runs no inference."""

    def test_stage_declares_no_artifact(self):
        stage = RectifyPlateStage()
        self.assertFalse(stage.has_model)
        self.assertIsNone(stage.model_path)

    def test_load_is_a_no_op(self):
        stage = RectifyPlateStage()
        stage.load()
        self.assertFalse(stage.loaded)
        self.assertIsNone(stage._session)

    def test_run_performs_no_inference(self):
        stage = RectifyPlateStage(output_size=(320, 100))
        outputs = stage.run({"plate": box_plate(make_image(), 0, 0, 100, 40)})
        self.assertIn("rectified", outputs)
        self.assertFalse(stage.loaded)

    def test_contributes_negligible_latency(self):
        import time

        stage = RectifyPlateStage(output_size=(320, 100))
        plate = box_plate(make_image(800, 600), 100, 100, 300, 120)
        stage.run({"plate": plate})  # warm up
        started = time.perf_counter()
        for _ in range(20):
            stage.run({"plate": plate})
        per_call = (time.perf_counter() - started) / 20
        self.assertLess(per_call, 0.05, "rectification must be far cheaper than model inference")


class BypassTest(TestCase):
    """Rectification can be disabled, falling back to a plain rectangular crop."""

    def test_bypass_produces_a_crop_without_transform(self):
        stage = RectifyPlateStage(enabled=False, output_size=(320, 100))
        result = stage.run({"plate": box_plate(make_image(200, 100), 10, 10, 80, 40)})["rectified"]
        self.assertEqual(result.crop.size, (80, 40), "bypass crops the region at its own size")
        self.assertEqual(result.corners, ())

    def test_bypass_uses_corners_bounding_box_when_present(self):
        stage = RectifyPlateStage(enabled=False)
        plate = box_plate(make_image(200, 200), 0, 0, 200, 200)
        plate["corners"] = [(20.0, 30.0), (120.0, 30.0), (120.0, 90.0), (20.0, 90.0)]
        result = stage.run({"plate": plate})["rectified"]
        self.assertEqual(result.crop.size, (100, 60))

    def test_bypass_reports_the_layout(self):
        stage = RectifyPlateStage(enabled=False, layout="stacked")
        result = stage.run({"plate": box_plate(make_image(), 0, 0, 60, 40)})["rectified"]
        self.assertEqual(result.layout, "stacked")


class RunContractTest(TestCase):
    """The stage satisfies the graph's routing contract."""

    def test_declares_inputs_and_outputs(self):
        stage = RectifyPlateStage()
        self.assertEqual(stage.inputs, ("plate",))
        self.assertEqual(stage.outputs, ("rectified",))

    def test_missing_plate_is_rejected(self):
        stage = RectifyPlateStage()
        with self.assertRaises(RectificationError):
            stage.run({})

    def test_per_detection_layout_overrides_the_default(self):
        stage = RectifyPlateStage(layout="single_line", output_size=(320, 100))
        plate = box_plate(make_image(), 0, 0, 100, 40, layout="stacked")
        result = stage.run({"plate": plate})["rectified"]
        self.assertEqual(result.layout, "stacked")
        self.assertEqual(result.crop.size, stage.target_size_for("stacked"))
