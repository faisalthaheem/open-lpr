"""Integration tests against a real exported detector.

These run only when a trained artifact is present at MODEL_PATH, or when
OPENLPR_TEST_MODEL points at one. They exist because of a bug no synthetic
fixture could catch.

The YOLOX ONNX export applies exp() to the regressed width and height inside the
graph, so the exported tensor already carries linear pixels. A decoder that
exponentiates again inflates every box until it clamps to the whole image:

    predicted: 0, 0, 1280, 960    (the entire image)
    truth:     516, 403, 208, 109

Synthetic fixtures written to match the decoder rather than the export agreed
with the decoder and passed, so only the real artifact exposed it. These tests
assert against real inference output, which is what makes them a guard against
that class of error rather than a restatement of the decoder.

Skipped when no model is available, so the suite still passes on a checkout
without trained artifacts.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest import skipUnless

import numpy as np
from django.test import SimpleTestCase
from PIL import Image

from lpr_app.pipeline.stages.detect import (
    Detection,
    PlateDetectionStage,
    box_iou,
    decode_yolox,
    letterbox,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = REPO_ROOT / "model" / "plate" / "plate_yolox_tiny_640.onnx"
MODEL_PATH = Path(os.environ.get("OPENLPR_TEST_MODEL", DEFAULT_MODEL))

has_model = MODEL_PATH.is_file()


@skipUnless(has_model, f"no trained detector at {MODEL_PATH}")
class RealDetectorTest(SimpleTestCase):
    """Decoding against a genuine exported model.

    Tests that need plate-like content build it by pasting a real plate crop
    onto a synthetic background, rather than drawing an abstract rectangle. A
    flat dark block is not what this detector was trained to recognise, so
    asserting it detects one would test the fixture rather than the model. When
    the corpus is absent those tests skip; the shape assertions still run.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stage = PlateDetectionStage(model_path=str(MODEL_PATH), conf_threshold=0.3)
        cls.stage.load()
        cls.plate_crop, cls.plate_box = cls._load_a_real_plate()

    @staticmethod
    def _load_a_real_plate():
        """Return (PIL image, (x1, y1, x2, y2)) of one real annotated plate.

        Read from the corpus's annotation database rather than guessed at with a
        centre crop, because a centre crop of a vehicle photo is usually the hood,
        not a plate, and the model rightly ignores it.
        """
        corpus = os.environ.get("OPENLPR_TEST_CORPUS")
        if not corpus or not Path(corpus).is_dir():
            return None, None
        db_path = Path(corpus) / "train.db"
        if not db_path.is_file():
            return None, None

        import json
        import sqlite3

        try:
            connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            rows = connection.execute(
                "SELECT filename, imgareas FROM annotations WHERE imgareas IS NOT NULL LIMIT 400"
            ).fetchall()
            connection.close()
        except sqlite3.Error:
            return None, None

        for filename, areas in rows:
            for root in (Path(corpus) / "train", Path(corpus) / "val"):
                path = root / filename
                if not path.is_file():
                    continue
                try:
                    regions = json.loads(areas)
                except (json.JSONDecodeError, TypeError):
                    continue
                if not regions:
                    continue
                region = regions[0]
                x, y = float(region["x"]), float(region["y"])
                w, h = float(region["width"]), float(region["height"])
                if w < 40 or h < 16:
                    continue
                with Image.open(path) as image:
                    # A little context around the plate, as a real frame has.
                    pad_x, pad_y = w * 0.5, h * 1.5
                    box = (
                        max(0, int(x - pad_x)),
                        max(0, int(y - pad_y)),
                        min(image.width, int(x + w + pad_x)),
                        min(image.height, int(y + h + pad_y)),
                    )
                    crop = image.convert("RGB").crop(box)
                    # Where the plate itself now sits inside the crop.
                    plate = (int(x - box[0]), int(y - box[1]), int(x - box[0] + w), int(y - box[1] + h))
                    return crop, plate
        return None, None

    @classmethod
    def _pasted(cls):
        """A real plate crop pasted onto a neutral background at known coordinates."""
        if cls.plate_crop is None:
            return None, None
        canvas = Image.new("RGB", (1280, 960), (150, 150, 150))
        position = (430, 400)
        canvas.paste(cls.plate_crop, position)
        return canvas, (
            position[0],
            position[1],
            position[0] + cls.plate_crop.width,
            position[1] + cls.plate_crop.height,
        )

    def _pasted_with_plate_box(self):
        """Canvas, the pasted region, and the plate's box inside the canvas."""
        canvas, outer = self._pasted()
        if canvas is None:
            return None, None, None
        inner = self.plate_box
        plate = (outer[0] + inner[0], outer[1] + inner[1], outer[0] + inner[2], outer[1] + inner[3])
        return canvas, outer, plate

    def test_output_tensor_shape_matches_the_decoder_assumption(self):
        """The decoder assumes a level-major layout with 5+num_classes columns.

        Asserting the shape here means a changed export fails loudly instead of
        silently producing wrong boxes.
        """
        import onnxruntime as ort

        session = ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])
        image = Image.new("RGB", (640, 640), (120, 120, 120))
        tensor, scale, pad = letterbox(image, (640, 640))
        raw = session.run(None, {session.get_inputs()[0].name: tensor})[0]

        self.assertEqual(raw.ndim, 3)
        self.assertEqual(raw.shape[0], 1)
        height, width = self.stage.input_size
        expected_anchors = sum((height // s) * (width // s) for s in (8, 16, 32))
        self.assertEqual(raw.shape[1], expected_anchors)
        # 5 box terms plus one class score for this single-class model.
        self.assertEqual(raw.shape[2], 6)

    def test_blank_image_yields_no_detections(self):
        """A featureless frame must not produce confident plates."""
        detections = self.stage.run({"image": Image.new("RGB", (1280, 960), (200, 200, 200))})["detections"]
        self.assertEqual(detections, [], "a blank frame produced false positives")

    def test_decoding_the_real_tensor_yields_plausible_geometry(self):
        """decode_yolox must consume real output without exploding."""
        import onnxruntime as ort

        session = ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])
        canvas, box = self._pasted()
        if canvas is None:
            self.skipTest("no plate crop available; set OPENLPR_TEST_CORPUS")

        tensor, scale, pad = letterbox(canvas, (640, 640))
        raw = session.run(None, {session.get_inputs()[0].name: tensor})[0]

        detections = decode_yolox(np.asarray(raw), scale, pad, canvas.size, input_size=(640, 640), conf_threshold=0.3)
        self.assertTrue(detections)
        for detection in detections:
            self.assertLessEqual(detection.x1, detection.x2)
            self.assertLessEqual(detection.y1, detection.y2)
            self.assertLessEqual(detection.area, 1280 * 960)
            self.assertTrue(0.0 <= detection.confidence <= 1.0)

    def test_detects_a_real_plate(self):
        canvas, box = self._pasted()
        if canvas is None:
            self.skipTest("no plate crop available; set OPENLPR_TEST_CORPUS")

        detections = self.stage.run({"image": canvas})["detections"]
        self.assertTrue(detections, "the detector must find a pasted real plate")

    def test_box_is_a_plaque_not_the_whole_image(self):
        """Guards the double-exponentiation bug.

        A mis-decoded box clamps to the full frame. Requiring the prediction to
        cover well under half the image catches that directly.
        """
        canvas, box = self._pasted()
        if canvas is None:
            self.skipTest("no plate crop available; set OPENLPR_TEST_CORPUS")

        detections = self.stage.run({"image": canvas})["detections"]
        self.assertTrue(detections)
        largest = max(detections, key=lambda d: d.area)
        self.assertLess(
            largest.area / (1280 * 960),
            0.5,
            f"largest detection covers {largest.area / (1280 * 960):.0%} of the frame; "
            "a whole-frame box indicates a decode error",
        )

    def test_detection_is_localised_on_the_plate(self):
        """The box must land on the plate itself, not merely be small."""
        canvas, _outer, plate = self._pasted_with_plate_box()
        if canvas is None:
            self.skipTest("no plate crop available; set OPENLPR_TEST_CORPUS")

        detections = self.stage.run({"image": canvas})["detections"]
        self.assertTrue(detections)

        target = Detection(*plate, 1.0)
        best = max(detections, key=lambda d: box_iou(d, target))
        overlap = box_iou(best, target)
        self.assertGreater(overlap, 0.2, f"best detection IoU with the true plate is {overlap:.2f}")
