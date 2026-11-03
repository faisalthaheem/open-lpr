"""Tests for the local detection stage: coordinate mapping, filtering, layout."""

from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

import numpy as np
from PIL import Image

from lpr_app.pipeline.stages.detect import (
    Detection,
    PlateDetectionStage,
    box_iou,
    decode_yolox,
    guess_layout,
    letterbox,
    scale_box,
    suppress_duplicates,
)


def make_image(width=640, height=480):
    return Image.new("RGB", (width, height), (30, 30, 30))


def make_predictions(boxes, input_size=(640, 640), num_classes=1, conf=0.9):
    """Build a YOLOX-shaped prediction array.

    Each entry is (cx, cy, w, h, obj_conf, class_score, ...) in letterboxed
    input space, placed on the stride-8 level. Width and height are linear
    pixels: the ONNX export applies exp() internally, so the exported tensor is
    already decoded and the stage must not exponentiate a second time.

    The layout is level-major with the anchor counts of strides 8, 16, 32, which
    is what a real YOLOX export produces.
    """
    input_w, input_h = input_size
    strides = (8, 16, 32)
    grids = [(input_w // s) * (input_h // s) for s in strides]
    total = sum(grids)
    arr = np.zeros((1, total, 5 + num_classes), dtype=np.float32)

    grid_w = input_w // 8
    for cx, cy, w, h, *rest in boxes:
        score = rest[0] if rest else conf
        gx, gy = int(round(cx / 8)), int(round(cy / 8))
        arr[0, gx + gy * grid_w, 0] = cx
        arr[0, gx + gy * grid_w, 1] = cy
        arr[0, gx + gy * grid_w, 2] = w
        arr[0, gx + gy * grid_w, 3] = h
        arr[0, gx + gy * grid_w, 4] = 1.0
        arr[0, gx + gy * grid_w, 5] = score
    return arr


class LetterboxTest(TestCase):
    """Aspect ratio is preserved so coordinates do not distort the plate."""

    def test_output_shape_is_chw_float(self):
        tensor, _, _ = letterbox(make_image(), (640, 640))
        self.assertEqual(tensor.shape, (1, 3, 640, 640))
        self.assertEqual(tensor.dtype, np.float32)

    def test_aspect_ratio_is_preserved_by_letterboxing(self):
        # A 1000x250 image letterboxed to 640x640 must scale by the same factor
        # on both axes, so 4:1 stays 4:1.
        _, scale, _ = letterbox(make_image(1000, 250), (640, 640))
        self.assertAlmostEqual(scale, 640 / 1000, places=6)

    def test_padding_is_centred(self):
        _, _, (pad_x, pad_y) = letterbox(make_image(1000, 250), (640, 640))
        self.assertGreater(pad_y, 0, "a wide image is padded vertically")
        self.assertAlmostEqual(pad_x, 0.0, places=6)

    def test_tall_image_is_padded_horizontally(self):
        _, _, (pad_x, _) = letterbox(make_image(250, 1000), (640, 640))
        self.assertGreater(pad_x, 0)

    def test_exact_aspect_needs_no_padding(self):
        _, scale, (pad_x, pad_y) = letterbox(make_image(640, 640), (640, 640))
        self.assertEqual((pad_x, pad_y), (0.0, 0.0))
        self.assertEqual(scale, 1.0)

    def test_degenerate_image_is_rejected(self):
        from lpr_app.pipeline.stages.base import StageError

        with self.assertRaises(StageError):
            letterbox(Image.new("RGB", (0, 10)), (640, 640))


class CoordinateMappingTest(TestCase):
    """Coordinates returned are in the original image's space and clamped."""

    def test_box_maps_back_to_original_space(self):
        # A box spanning the full letterboxed input, on an image padded vertically.
        scale, pad = 0.64, (0.0, 224.0)
        box = scale_box((0.0, 224.0, 640.0, 416.0), scale, pad, (1000, 250))
        self.assertAlmostEqual(box[0], 0.0, places=3)
        self.assertAlmostEqual(box[1], 0.0, places=3)
        self.assertAlmostEqual(box[2], 1000.0, places=3)
        self.assertAlmostEqual(box[3], 250.0, places=3)

    def test_coordinates_are_clamped_to_image_bounds(self):
        box = scale_box((-500.0, -500.0, 5000.0, 5000.0), 1.0, (0.0, 0.0), (640, 480))
        self.assertEqual(box, (0.0, 0.0, 640.0, 480.0))

    def test_round_trip_through_letterbox(self):
        image = make_image(1000, 250)
        _, scale, pad = letterbox(image, (640, 640))
        original = (100.0, 50.0, 300.0, 150.0)
        # Forward: original -> letterboxed.
        px, py = pad
        forward = (
            original[0] * scale + px,
            original[1] * scale + py,
            original[2] * scale + px,
            original[3] * scale + py,
        )
        back = scale_box(forward, scale, pad, image.size)
        for got, want in zip(back, original, strict=True):
            self.assertAlmostEqual(got, want, delta=0.5)


class DecodeTest(TestCase):
    """Decoding yields one detection per plate with a valid confidence."""

    def test_single_plate_decoded(self):
        preds = make_predictions([(320.0, 320.0, 200.0, 60.0, 0.95)])
        found = decode_yolox(preds, 1.0, (0.0, 0.0), (640, 640))
        self.assertEqual(len(found), 1)
        d = found[0]
        self.assertAlmostEqual(d.x1, 220.0, delta=1.0)
        self.assertAlmostEqual(d.x2, 420.0, delta=1.0)
        self.assertGreaterEqual(d.confidence, 0.0)
        self.assertLessEqual(d.confidence, 1.0)

    def test_multiple_plates_decoded(self):
        preds = make_predictions([(160.0, 320.0, 100.0, 40.0, 0.9), (480.0, 320.0, 100.0, 40.0, 0.9)])
        found = decode_yolox(preds, 1.0, (0.0, 0.0), (640, 640))
        self.assertEqual(len(found), 2)

    def test_no_plates_yields_empty_list(self):
        found = decode_yolox(make_predictions([]), 1.0, (0.0, 0.0), (640, 640))
        self.assertEqual(found, [])

    def test_below_threshold_is_discarded(self):
        preds = make_predictions([(320.0, 320.0, 200.0, 60.0, 0.10)])
        self.assertEqual(decode_yolox(preds, 1.0, (0.0, 0.0), (640, 640), conf_threshold=0.5), [])

    def test_above_threshold_is_kept(self):
        preds = make_predictions([(320.0, 320.0, 200.0, 60.0, 0.90)])
        self.assertEqual(len(decode_yolox(preds, 1.0, (0.0, 0.0), (640, 640), conf_threshold=0.5)), 1)

    def test_malformed_array_is_rejected(self):
        from lpr_app.pipeline.stages.base import StageError

        with self.assertRaises(StageError):
            decode_yolox(np.zeros((5,)), 1.0, (0.0, 0.0), (640, 640))


class DuplicateSuppressionTest(TestCase):
    """Overlapping detections collapse to the most confident one."""

    def test_identical_boxes_collapse(self):
        a = Detection(0, 0, 100, 40, 0.9)
        b = Detection(1, 1, 101, 41, 0.8)
        kept = suppress_duplicates([a, b])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].confidence, 0.9)

    def test_distinct_boxes_are_both_kept(self):
        a = Detection(0, 0, 100, 40, 0.9)
        b = Detection(300, 200, 400, 240, 0.8)
        self.assertEqual(len(suppress_duplicates([a, b])), 2)

    def test_iou_threshold_is_respected(self):
        # Barely overlapping boxes fall below a strict IoU threshold.
        a = Detection(0, 0, 100, 40, 0.9)
        b = Detection(90, 0, 190, 40, 0.8)
        self.assertGreater(box_iou(a, b), 0.0)
        self.assertEqual(len(suppress_duplicates([a, b], iou_threshold=0.45)), 2)

    def test_disjoint_boxes_have_zero_iou(self):
        self.assertEqual(box_iou(Detection(0, 0, 10, 10, 0.9), Detection(50, 50, 60, 60, 0.9)), 0.0)

    def test_stacked_plate_is_one_detection_not_two_rows(self):
        """A two-line plate is one plate; its rows must not become two detections."""
        stacked = Detection(100, 100, 260, 220, 0.9)  # ratio ~1.07
        top_row = Detection(100, 100, 260, 158, 0.85)
        bottom_row = Detection(100, 162, 260, 220, 0.85)
        found = decode_yolox(
            make_predictions([(180.0, 160.0, 160.0, 120.0, 0.9)]),
            1.0,
            (0.0, 0.0),
            (640, 640),
        )
        self.assertEqual(len(found), 1, "the detector emits one box for the plate")
        self.assertEqual(found[0].layout, "stacked")
        # A row-sized box overlapping the plate is suppressed against it.
        kept = suppress_duplicates([stacked, top_row, bottom_row], iou_threshold=0.3)
        self.assertEqual(len(kept), 1)


class LayoutTest(TestCase):
    """Layout classification drives OCR row handling."""

    def test_stacked_detection(self):
        self.assertEqual(guess_layout(Detection(0, 0, 160, 100, 0.9)), "stacked")

    def test_single_line_detection(self):
        self.assertEqual(guess_layout(Detection(0, 0, 300, 100, 0.9)), "single_line")

    def test_eu_proportion_is_single_line(self):
        # 520x110 EU plates have ratio ~4.7.
        self.assertEqual(guess_layout(Detection(0, 0, 470, 100, 0.9)), "single_line")

    def test_degenerate_detection_defaults_to_single_line(self):
        self.assertEqual(guess_layout(Detection(0, 0, 100, 0, 0.9)), "single_line")

    def test_layout_threshold_is_configurable(self):
        d = Detection(0, 0, 200, 100, 0.9)  # ratio 2.0 exactly
        self.assertEqual(guess_layout(d, stacked_threshold=2.5), "stacked")
        self.assertEqual(guess_layout(d, stacked_threshold=1.5), "single_line")

    def test_detections_carry_their_layout(self):
        found = decode_yolox(make_predictions([(320.0, 320.0, 320.0, 100.0, 0.9)]), 1.0, (0.0, 0.0), (640, 640))
        self.assertEqual(found[0].layout, "single_line")


class OutputShapeTest(TestCase):
    """Output matches what the API already consumes."""

    def test_to_dict_matches_the_llm_shape(self):
        payload = Detection(10.4, 20.6, 110.4, 60.6, 0.8712).to_dict()
        self.assertEqual(set(payload), {"confidence", "coordinates"})
        self.assertEqual(set(payload["coordinates"]), {"x1", "y1", "x2", "y2"})

    def test_coordinates_are_integers(self):
        payload = Detection(10.4, 20.6, 110.4, 60.6, 0.87).to_dict()
        for value in payload["coordinates"].values():
            self.assertIsInstance(value, int)

    def test_corners_included_only_when_present(self):
        without = Detection(0, 0, 10, 10, 0.9).to_dict()
        self.assertNotIn("corners", without)
        with_corners = Detection(0, 0, 10, 10, 0.9, corners=[(0.0, 0.0)]).to_dict()
        self.assertIn("corners", with_corners)


class StageContractTest(TestCase):
    """The stage satisfies the graph's routing contract."""

    def test_declares_inputs_and_outputs(self):
        stage = PlateDetectionStage()
        self.assertEqual(stage.inputs, ("image",))
        self.assertEqual(stage.outputs, ("detections",))

    def test_thresholds_are_configurable(self):
        stage = PlateDetectionStage(conf_threshold=0.7, nms_iou=0.3)
        self.assertEqual(stage.conf_threshold, 0.7)
        self.assertEqual(stage.nms_iou, 0.3)

    def test_missing_image_is_rejected(self):
        from lpr_app.pipeline.stages.base import StageError

        with self.assertRaises(StageError):
            PlateDetectionStage().run({})


class LetterboxMaxScaleTest(TestCase):
    """``max_scale`` pastes a small image onto the canvas at native size."""

    def test_max_scale_caps_upscaling(self):
        tensor, scale, _pad = letterbox(make_image(100, 50), (640, 640), max_scale=1.0)
        self.assertEqual(scale, 1.0)
        self.assertEqual(tensor.shape, (1, 3, 640, 640))

    def test_without_the_cap_small_images_are_enlarged(self):
        _tensor, scale, _pad = letterbox(make_image(100, 50), (640, 640))
        self.assertAlmostEqual(scale, 6.4)

    def test_capped_content_keeps_its_native_pixel_size(self):
        """The paste, not a resize, fills the canvas: a 100x50 white square
        occupies exactly 100x50 canvas pixels."""
        image = Image.new("RGB", (100, 50), (255, 255, 255))
        tensor, _scale, _pad = letterbox(image, (640, 640), max_scale=1.0)
        white = tensor[0, 0] > 250
        rows = np.flatnonzero(white.any(axis=1))
        cols = np.flatnonzero(white.any(axis=0))
        self.assertEqual(int(rows.max() - rows.min() + 1), 50)
        self.assertEqual(int(cols.max() - cols.min() + 1), 100)

    def test_images_larger_than_the_input_are_unaffected(self):
        _tensor, scale, _pad = letterbox(make_image(1280, 720), (640, 640), max_scale=1.0)
        self.assertAlmostEqual(scale, 0.5)


class NativeScalePassTest(TestCase):
    """The second pass runs only for images the letterbox pass would upscale."""

    def _stage(self, **kwargs):
        stage = PlateDetectionStage(conf_threshold=0.3, **kwargs)
        stage._session = FakeDetector()
        return stage

    def test_small_image_pays_two_inferences(self):
        stage = self._stage()
        stage.run({"image": make_image(300, 200)})
        self.assertEqual(len(stage._session.calls), 2)

    def test_image_fitting_the_input_pays_one_inference(self):
        """max(image.size) >= input means the letterbox pass downscales, which
        is the training regime; no second pass is needed."""
        stage = self._stage()
        stage.run({"image": make_image(640, 480)})
        self.assertEqual(len(stage._session.calls), 1)

    def test_pass_can_be_disabled(self):
        stage = self._stage(native_scale_pass=False)
        stage.run({"image": make_image(300, 200)})
        self.assertEqual(len(stage._session.calls), 1)

    def test_merged_duplicates_keep_the_more_confident_detection(self):
        stage = self._stage()
        with (
            patch.object(stage, "_detect_at_letterbox_scale", return_value=[Detection(0, 0, 100, 40, 0.4)]),
            patch.object(stage, "_detect_at_native_scale", return_value=[Detection(0, 0, 100, 40, 0.6)]),
        ):
            detections = stage.run({"image": make_image(300, 200)})["detections"]
        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0].confidence, 0.6)

    def test_disjoint_detections_from_both_passes_are_kept(self):
        stage = self._stage()
        with (
            patch.object(stage, "_detect_at_letterbox_scale", return_value=[Detection(0, 0, 100, 40, 0.4)]),
            patch.object(stage, "_detect_at_native_scale", return_value=[Detection(0, 200, 100, 240, 0.5)]),
        ):
            detections = stage.run({"image": make_image(300, 200)})["detections"]
        self.assertEqual(len(detections), 2)

    def test_native_scale_detection_coordinates_map_back_unscaled(self):
        """A box at input position (x, y) on a scale-1.0 pass sits at
        (x - pad_x, y - pad_y) in the original image."""
        stage = self._stage()
        image = make_image(300, 200)
        # One prediction centred at (300, 300) in input space, 80x30 px. The
        # native pass pads a 300x200 image by (170, 220), so this box lands
        # inside the image and is not clamped.
        predictions = make_predictions([(300, 300, 80, 30, 0.9, 0.9)])
        stage._session.predictions = predictions
        detections = stage._detect_at_native_scale(image)
        self.assertEqual(len(detections), 1)
        box = detections[0]
        self.assertAlmostEqual(box.x1, 300 - 40 - 170, places=1)
        self.assertAlmostEqual(box.y1, 300 - 15 - 220, places=1)


class FakeDetector:
    """Session stand-in returning a fixed (optionally empty) prediction."""

    def __init__(self, predictions=None):
        self.predictions = predictions
        self.calls: list[tuple[int, int]] = []
        self.input_names = ("images",)
        self.input_shapes = (("images", ("N", 3, 640, 640)),)
        self.output_names = PlateDetectionStage.ONNX_OUTPUTS
        self.session = self

    def run(self, output_names, feed):
        tensor = feed["images"]
        self.calls.append(tuple(tensor.shape[2:]))
        if self.predictions is None:
            # The stride-8/16/32 level counts of a 640 prediction grid, all below
            # any confidence threshold.
            total = 80 * 80 + 40 * 40 + 20 * 20
            return [np.zeros((1, total, 6), dtype=np.float32)]
        return [self.predictions]
