"""
Tests for query parameter validation on the image list endpoint.

Malformed pagination previously raised out of the view and produced a 500.
"""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.utils import timezone

from lpr_app.models import UploadedImage


def _make_image_file(name="p.jpg"):
    return SimpleUploadedFile(name, b"fake-jpeg-bytes", content_type="image/jpeg")


class ImageListPaginationValidationTest(TestCase):
    def setUp(self):
        self.client = Client()
        for i in range(3):
            UploadedImage.objects.create(
                original_image=_make_image_file(f"p{i}.jpg"),
                filename=f"p{i}.jpg",
                processing_status="completed",
                processing_timestamp=timezone.now(),
            )

    def test_valid_request_succeeds(self):
        response = self.client.get("/api/v1/images/?page=1&page_size=2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 2)

    def test_non_integer_page_returns_400(self):
        response = self.client.get("/api/v1/images/?page=abc")
        self.assertEqual(response.status_code, 400)
        self.assertIn("page", response.json()["error"])

    def test_non_integer_page_size_returns_400(self):
        response = self.client.get("/api/v1/images/?page_size=xyz")
        self.assertEqual(response.status_code, 400)
        self.assertIn("page_size", response.json()["error"])

    def test_empty_page_returns_400(self):
        self.assertEqual(self.client.get("/api/v1/images/?page=").status_code, 400)

    def test_whitespace_page_size_returns_400(self):
        self.assertEqual(self.client.get("/api/v1/images/?page_size=%20").status_code, 400)

    def test_page_below_one_is_clamped(self):
        response = self.client.get("/api/v1/images/?page=0")
        self.assertEqual(response.status_code, 200)

    def test_negative_page_is_clamped(self):
        response = self.client.get("/api/v1/images/?page=-5")
        self.assertEqual(response.status_code, 200)

    def test_page_size_above_maximum_is_clamped(self):
        response = self.client.get("/api/v1/images/?page_size=5000")
        self.assertEqual(response.status_code, 200)

    def test_page_size_below_minimum_is_clamped(self):
        response = self.client.get("/api/v1/images/?page_size=0")
        self.assertEqual(response.status_code, 200)

    def test_pagination_links_carry_validated_values(self):
        response = self.client.get("/api/v1/images/?page=1&page_size=1")
        self.assertEqual(response.status_code, 200)
        self.assertIn("page_size=1", response.json()["next"])


class DetectionSchemaTest(TestCase):
    """`detections` is always a JSON array; other shapes read as zero plates."""

    def setUp(self):
        self.client = Client()

    def _image(self, api_response):
        return UploadedImage.objects.create(
            original_image=_make_image_file("d.jpg"),
            filename="d.jpg",
            processing_status="completed",
            api_response=api_response,
        )

    def test_array_detections_are_counted(self):
        img = self._image(
            {
                "detections": [
                    {"plate": {"confidence": 0.9, "coordinates": {}}, "ocr": [{"text": "ABC123", "confidence": 0.9}]},
                    {"plate": {"confidence": 0.8, "coordinates": {}}, "ocr": []},
                ]
            }
        )
        self.assertEqual(img.get_plate_count(), 2)
        self.assertEqual(img.get_total_ocr_count(), 1)
        self.assertEqual(img.get_first_ocr_text(), "ABC123")

    def test_non_array_detections_read_as_zero(self):
        img = self._image({"detections": {"a": {"ocr": [{"text_value": {"confidence": 0.9}}]}}})
        self.assertEqual(img.get_plate_count(), 0)
        self.assertEqual(img.get_total_ocr_count(), 0)
        self.assertIsNone(img.get_first_ocr_text())

    def test_missing_detections_read_as_zero(self):
        img = self._image({"filename": "x.jpg"})
        self.assertEqual(img.get_plate_count(), 0)
        self.assertIsNone(img.get_first_ocr_text())

    def test_null_api_response_read_as_zero(self):
        img = self._image(None)
        self.assertEqual(img.get_plate_count(), 0)

    def test_image_list_endpoint_does_not_500_on_non_array_detections(self):
        self._image({"detections": {"legacy": {"ocr": [{"text": "OLD"}]}}})
        response = self.client.get("/api/v1/images/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["plate_count"], 0)
