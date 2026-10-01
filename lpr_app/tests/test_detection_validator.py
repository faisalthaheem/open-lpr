"""
Tests for the DetectionValidator used to filter false-positive LPR results.
"""

from django.test import TestCase

from lpr_app.services.detection_validator import DetectionValidator


def _make_detection(confidence=0.95, x1=100, y1=200, x2=400, y2=250, **extra):
    detection = {
        "plate": {
            "confidence": confidence,
            "coordinates": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
        }
    }
    detection["plate"].update(extra)
    return detection


class BoundingBoxValidationTest(TestCase):
    def setUp(self):
        self.validator = DetectionValidator()
        self.img_w, self.img_h = 1000, 1000

    def test_valid_plate_passes(self):
        detection = _make_detection(confidence=0.95, x1=100, y1=400, x2=400, y2=450)
        is_valid, reason = self.validator.validate_plate_detection(detection, self.img_h, self.img_w)
        self.assertTrue(is_valid, msg=reason)
        self.assertIsNone(reason)

    def test_low_confidence_rejected(self):
        detection = _make_detection(confidence=0.3)
        is_valid, reason = self.validator.validate_plate_detection(detection, self.img_h, self.img_w)
        self.assertFalse(is_valid)
        self.assertIn("confidence", reason)

    def test_confidence_at_threshold_passes(self):
        validator = DetectionValidator(min_confidence=0.5)
        detection = _make_detection(confidence=0.5)
        is_valid, _ = validator.validate_plate_detection(detection, self.img_h, self.img_w)
        self.assertTrue(is_valid)

    def test_degenerate_box_rejected(self):
        detection = _make_detection(x1=100, y1=200, x2=100, y2=200)
        is_valid, reason = self.validator.validate_plate_detection(detection, self.img_h, self.img_w)
        self.assertFalse(is_valid)
        self.assertIn("degenerate", reason)

    def test_inverted_box_rejected(self):
        detection = _make_detection(x1=400, y1=200, x2=100, y2=250)
        is_valid, reason = self.validator.validate_plate_detection(detection, self.img_h, self.img_w)
        self.assertFalse(is_valid)
        self.assertIn("degenerate", reason)

    def test_box_outside_image_rejected(self):
        detection = _make_detection(x1=900, y1=900, x2=1100, y2=950)
        is_valid, reason = self.validator.validate_plate_detection(detection, self.img_h, self.img_w)
        self.assertFalse(is_valid)
        self.assertIn("outside image", reason)

    def test_box_too_small_rejected(self):
        detection = _make_detection(x1=500, y1=500, x2=502, y2=501)
        is_valid, reason = self.validator.validate_plate_detection(detection, self.img_h, self.img_w)
        self.assertFalse(is_valid)
        self.assertIn("area", reason.lower())

    def test_box_too_large_rejected(self):
        detection = _make_detection(x1=10, y1=10, x2=995, y2=995)
        is_valid, reason = self.validator.validate_plate_detection(detection, self.img_h, self.img_w)
        self.assertFalse(is_valid)
        self.assertIn("area", reason.lower())

    def test_aspect_too_tall_rejected(self):
        detection = _make_detection(x1=450, y1=100, x2=550, y2=900)
        is_valid, reason = self.validator.validate_plate_detection(detection, self.img_h, self.img_w)
        self.assertFalse(is_valid)
        self.assertIn("aspect", reason)

    def test_aspect_too_wide_rejected(self):
        detection = _make_detection(x1=10, y1=400, x2=990, y2=450)
        is_valid, reason = self.validator.validate_plate_detection(detection, self.img_h, self.img_w)
        self.assertFalse(is_valid)
        self.assertIn("aspect", reason)

    def test_missing_plate_field_rejected(self):
        is_valid, reason = self.validator.validate_plate_detection({"plate": None}, self.img_h, self.img_w)
        self.assertFalse(is_valid)
        self.assertIn("plate", reason)

    def test_missing_coordinates_rejected(self):
        is_valid, reason = self.validator.validate_plate_detection(
            {"plate": {"confidence": 0.9}}, self.img_h, self.img_w
        )
        self.assertFalse(is_valid)
        self.assertIn("coordinates", reason)

    def test_non_dict_detection_rejected(self):
        is_valid, reason = self.validator.validate_plate_detection("not a dict", self.img_h, self.img_w)
        self.assertFalse(is_valid)
        self.assertIn("dict", reason)


class FilterDetectionsTest(TestCase):
    def setUp(self):
        self.validator = DetectionValidator()
        self.img_w, self.img_h = 1000, 1000

    def test_keeps_valid_drops_invalid(self):
        detections = [
            _make_detection(confidence=0.95, x1=100, y1=400, x2=400, y2=450),
            _make_detection(confidence=0.2, x1=200, y1=500, x2=500, y2=550),
            _make_detection(confidence=0.9, x1=300, y1=600, x2=600, y2=650),
        ]
        filtered = self.validator.filter_detections(detections, self.img_h, self.img_w)
        self.assertEqual(len(filtered), 2)

    def test_empty_input_returns_empty(self):
        self.assertEqual(self.validator.filter_detections([], self.img_h, self.img_w), [])

    def test_all_invalid_returns_empty(self):
        detections = [
            _make_detection(confidence=0.1),
            _make_detection(confidence=0.05),
        ]
        filtered = self.validator.filter_detections(detections, self.img_h, self.img_w)
        self.assertEqual(filtered, [])


class OcrTextValidationTest(TestCase):
    def test_valid_plate_text_passes(self):
        is_valid, _ = DetectionValidator.validate_ocr_text("鄂A·R606L")
        self.assertTrue(is_valid)

    def test_valid_arabic_text_passes(self):
        is_valid, _ = DetectionValidator.validate_ocr_text("أ ب ج 123")
        self.assertTrue(is_valid)

    def test_alphanumeric_plate_passes(self):
        is_valid, _ = DetectionValidator.validate_ocr_text("ABC123")
        self.assertTrue(is_valid)

    def test_empty_string_rejected(self):
        is_valid, reason = DetectionValidator.validate_ocr_text("")
        self.assertFalse(is_valid)
        self.assertIn("empty", reason)

    def test_whitespace_only_rejected(self):
        is_valid, reason = DetectionValidator.validate_ocr_text("   \t  ")
        self.assertFalse(is_valid)
        self.assertIn("empty", reason)

    def test_none_rejected(self):
        is_valid, reason = DetectionValidator.validate_ocr_text(None)
        self.assertFalse(is_valid)

    def test_too_short_rejected(self):
        is_valid, reason = DetectionValidator.validate_ocr_text("A")
        self.assertFalse(is_valid)
        self.assertIn("short", reason)

    def test_too_long_rejected(self):
        is_valid, reason = DetectionValidator.validate_ocr_text("A" * 25)
        self.assertFalse(is_valid)
        self.assertIn("long", reason)

    def test_no_alphanumeric_rejected(self):
        is_valid, reason = DetectionValidator.validate_ocr_text("·-·-")
        self.assertFalse(is_valid)
        self.assertIn("alphanumeric", reason)

    def test_non_string_rejected(self):
        is_valid, reason = DetectionValidator.validate_ocr_text(12345)
        self.assertFalse(is_valid)
        self.assertIn("string", reason)


class IsMeaningfulOcrTextTest(TestCase):
    def test_returns_true_for_plate_like_strings(self):
        self.assertTrue(DetectionValidator.is_meaningful_ocr_text("ABC123"))
        self.assertTrue(DetectionValidator.is_meaningful_ocr_text("鄂A·R606L"))

    def test_returns_false_for_empty(self):
        self.assertFalse(DetectionValidator.is_meaningful_ocr_text(""))
        self.assertFalse(DetectionValidator.is_meaningful_ocr_text(None))

    def test_returns_false_for_too_short(self):
        self.assertFalse(DetectionValidator.is_meaningful_ocr_text("A"))

    def test_returns_false_for_too_long(self):
        self.assertFalse(DetectionValidator.is_meaningful_ocr_text("A" * 30))

    def test_returns_false_for_no_alphanumeric(self):
        self.assertFalse(DetectionValidator.is_meaningful_ocr_text("----"))
