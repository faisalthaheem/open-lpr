"""The LLM backend path, extracted into a method without changing its behaviour.

Extracting the three-phase procedure out of `process_uploaded_image` is the only
edit the backend switch made to it, and an extraction is exactly the kind of change
that can quietly alter a call. These tests pin the observable behaviour of the
extracted method -- the prompts sent, the fixed-pixel crop padding, the validation
applied to recognized text, and the errors returned -- rather than restating the
code, so a behavioural change during extraction fails here.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import numpy as np
from django.test import TestCase, override_settings
from PIL import Image

from lpr_app.models import ProcessingLog, UploadedImage
from lpr_app.services.image_processing_service import ImageProcessingService, LLMPipelineError

DETECTION_RESPONSE = json.dumps(
    {"detections": [{"plate": {"confidence": 0.93, "coordinates": {"x1": 500, "y1": 400, "x2": 740, "y2": 500}}}]}
)

OCR_RESPONSE = json.dumps(
    {"text": "EG209", "confidence": 0.88, "coordinates": {"x1": 510, "y1": 410, "x2": 730, "y2": 490}}
)


def write_test_image(path) -> None:
    array = np.full((960, 1280, 3), 150, dtype=np.uint8)
    array[400:500, 500:740] = 225
    Image.fromarray(array).save(path)


class LLMPipelinePathTest(TestCase):
    """The extracted method reproduces the inlined code's behaviour."""

    def setUp(self):
        import tempfile
        from pathlib import Path

        from django.core.files.uploadedfile import SimpleUploadedFile

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.image_path = self.root / "plate.jpg"
        write_test_image(self.image_path)

        uploaded = SimpleUploadedFile("plate.jpg", self.image_path.read_bytes(), content_type="image/jpeg")
        self.image = UploadedImage.objects.create(filename="plate.jpg", original_image=uploaded)
        self.api_call_log = ProcessingLog.objects.create(
            uploaded_image=self.image, status="api_call", message="Starting Phase 1"
        )

    def _run(self, detection=DETECTION_RESPONSE, ocr=(OCR_RESPONSE,), **overrides):
        with (
            override_settings(MEDIA_ROOT=str(self.root), **overrides),
            patch("lpr_app.services.image_processing_service.get_qwen_client") as get_client,
        ):
            client = get_client.return_value
            client.analyze_image.return_value = detection
            client.analyze_images_batch.return_value = list(ocr)
            detections, summary = ImageProcessingService._run_llm_pipeline(
                self.image, str(self.image_path), 960, 1280, 0.0, self.api_call_log
            )
        return detections, summary, client

    def test_detection_produces_the_expected_collection(self):
        """Coordinates are scaled from the downscaled detection image back to the
        original, so the box is proportional to the mock response rather than equal
        to it. What is asserted is that scaling happened and the box landed on the
        plate rather than on the whole frame."""
        detections, _summary, _client = self._run()
        self.assertEqual(len(detections), 1)
        coords = detections[0]["plate"]["coordinates"]
        self.assertGreater(coords["x1"], 500, "coordinates were not scaled back up to the original image")
        self.assertLess(coords["x2"], 1280)
        self.assertLess(coords["y2"], 960)

    def test_validated_text_is_attached_to_the_detection(self):
        detections, _summary, _client = self._run()
        self.assertEqual(detections[0]["ocr"][0]["text"], "EG209")

    def test_implausible_text_is_discarded_but_the_plate_is_kept(self):
        """The LLM path's long-standing behaviour: a rejected read empties ``ocr``
        rather than dropping the detection."""
        detections, _summary, _client = self._run(ocr=(json.dumps({"text": "X", "confidence": 0.9}),))
        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0]["ocr"], [])

    def test_crop_padding_is_the_configured_fixed_pixel_amount(self):
        """The contract the ocr-crop-padding requirement specifies: the crop is
        expanded by OCR_CROP_PADDING_PX, not by a percentage of the box."""
        captured: list[tuple[int, int, int, int, int]] = []

        from lpr_app.services.image_processor import ImageProcessor

        original = ImageProcessor.crop_region

        def spy(image_path, x1, y1, x2, y2, padding_pct=0.1, padding_px=None):
            captured.append((x1, y1, x2, y2, padding_px))
            return original(image_path, x1, y1, x2, y2, padding_pct=padding_pct, padding_px=padding_px)

        with patch.object(ImageProcessor, "crop_region", staticmethod(spy)):
            self._run()

        self.assertEqual(len(captured), 1)
        # The box passed to crop_region is the scaled one, so only the padding
        # amount is asserted exactly; the box itself is covered above.
        self.assertEqual(captured[0][4], 25)

    def test_custom_crop_padding_is_honoured(self):
        captured: list[int | None] = []
        from lpr_app.services.image_processor import ImageProcessor

        original = ImageProcessor.crop_region

        def spy(image_path, x1, y1, x2, y2, padding_pct=0.1, padding_px=None):
            captured.append(padding_px)
            return original(image_path, x1, y1, x2, y2, padding_pct=padding_pct, padding_px=padding_px)

        with patch.object(ImageProcessor, "crop_region", staticmethod(spy)):
            self._run(OCR_CROP_PADDING_PX=40)

        self.assertEqual(captured, [40])

    def test_one_ocr_call_is_made_per_image_regardless_of_plate_count(self):
        _detections, _summary, client = self._run()
        client.analyze_images_batch.assert_called_once()

    def test_detection_uses_the_detection_only_prompt(self):
        """Phase 1 must not ask for text; the split is what keeps the LLM call count
        at two regardless of how many plates the image holds."""
        _detections, _summary, client = self._run()
        prompt = client.analyze_image.call_args[0][1]
        self.assertNotIn("OCR", prompt.upper().replace("LICENSE", ""))

    def test_api_call_log_records_a_duration(self):
        self._run()
        self.api_call_log.refresh_from_db()
        self.assertIsNotNone(self.api_call_log.duration_ms)

    def test_no_plates_is_an_empty_collection_not_a_failure(self):
        detections, _summary, _client = self._run(detection=json.dumps({"detections": []}))
        self.assertEqual(detections, [])

    def test_unparseable_detection_response_is_an_error(self):
        with self.assertRaises(LLMPipelineError):
            self._run(detection="not json at all")

    def test_empty_detection_response_is_an_error(self):
        with self.assertRaises(LLMPipelineError):
            self._run(detection="")

    def test_ocr_response_count_mismatch_leaves_detections_without_text(self):
        """A short batch response must not discard the detections that were found.

        The batch-length check fails and no text is attached at all, so ``ocr`` is
        absent rather than empty. That is the long-standing behaviour of this path
        and is pinned here so the extraction is confirmed not to have changed it.
        """
        detections, _summary, _client = self._run(ocr=())
        self.assertEqual(len(detections), 1)
        self.assertNotIn("ocr", detections[0])
        self.assertIn("plate", detections[0])

    def test_a_failed_ocr_response_leaves_the_plate_without_text(self):
        detections, _summary, _client = self._run(ocr=(None,))
        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0]["ocr"], [])

    def test_downscaled_image_is_cleaned_up(self):
        """The temporary downscale is removed whether or not the path succeeded, so
        a failure cannot leave one behind per request."""
        before = set(self.root.rglob("*"))
        self._run()
        after = set(self.root.rglob("*"))
        leftovers = [p for p in after - before if "downscale" in p.name.lower()]
        self.assertEqual(leftovers, [])
