import io
import json
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile

from ..models import UploadedImage, ProcessingLog


def _make_image_file(name="test.jpg", content=b"fake image"):
    return SimpleUploadedFile(name, content, content_type="image/jpeg")


def _create_real_image_file(name="test.jpg"):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), "red").save(buf, format="JPEG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/jpeg")


CANARY_SETTINGS = {
    "MEDIA_ROOT": "/tmp/test_lpr_canary_media/",
    "CANARY_ENABLED": True,
    "CANARY_HEADER_NAME": "X-Canary-Request",
    "CANARY_HEADER_VALUE": "test-canary-secret",
}


@override_settings(**CANARY_SETTINGS)
class CanaryProcessingFailureCleanupTest(TestCase):
    def setUp(self):
        self.client = Client()

    def _post_canary_ocr(self, image_file=None):
        if image_file is None:
            image_file = _create_real_image_file("canary.jpg")
        return self.client.post(
            "/api/v1/ocr/",
            {"image": image_file, "save_image": "false"},
            HTTP_X_CANARY_REQUEST="test-canary-secret",
        )

    @patch("lpr_app.views.api_views.ImageProcessingService.process_uploaded_image")
    def test_canary_failure_deletes_db_record(self, mock_process):
        mock_process.return_value = {"success": False, "error": "API timeout"}

        self._post_canary_ocr()

        self.assertEqual(UploadedImage.objects.count(), 0)

    @patch("lpr_app.views.api_views.ImageProcessingService.process_uploaded_image")
    def test_canary_failure_returns_image_id_none(self, mock_process):
        mock_process.return_value = {"success": False, "error": "API timeout"}

        response = self._post_canary_ocr()
        data = response.json()

        self.assertEqual(response.status_code, 500)
        self.assertTrue(data["canary_request"])
        self.assertIsNone(data["image_id"])
        self.assertIn("error", data)

    @patch("lpr_app.views.api_views.ImageProcessingService.process_uploaded_image")
    def test_canary_failure_returns_error_details(self, mock_process):
        mock_process.return_value = {"success": False, "error": "Detection parse error"}

        response = self._post_canary_ocr()
        data = response.json()

        self.assertEqual(data["error_code"], "PROCESSING_FAILED")
        self.assertIn("Detection parse error", data["error"])

    @patch("lpr_app.views.api_views.ImageProcessingService.process_uploaded_image")
    def test_canary_failure_does_not_appear_in_image_list(self, mock_process):
        mock_process.return_value = {"success": False, "error": "API timeout"}

        self._post_canary_ocr()

        response = self.client.get("/api/v1/images/")
        data = response.json()
        self.assertEqual(data["count"], 0)

    @patch("lpr_app.views.api_views.ImageProcessingService.process_uploaded_image")
    def test_canary_failure_records_metrics_before_cleanup(self, mock_process):
        mock_process.return_value = {"success": False, "error": "API timeout"}

        from ..utils.metrics_helpers import MetricsHelper
        from ..metrics import CANARY_REQUESTS_TOTAL

        initial_failed = CANARY_REQUESTS_TOTAL.labels(status="failed")._value._value

        self._post_canary_ocr()

        new_failed = CANARY_REQUESTS_TOTAL.labels(status="failed")._value._value
        self.assertGreater(new_failed, initial_failed)

    @patch("lpr_app.views.api_views.ImageProcessingService.process_uploaded_image")
    def test_canary_failure_processing_logs_deleted(self, mock_process):
        mock_process.return_value = {"success": False, "error": "API timeout"}

        self._post_canary_ocr()

        self.assertEqual(ProcessingLog.objects.count(), 0)


@override_settings(**CANARY_SETTINGS)
class CanaryExceptionCleanupTest(TestCase):
    def setUp(self):
        self.client = Client()

    def _post_canary_ocr(self, image_file=None):
        if image_file is None:
            image_file = _create_real_image_file("canary_exc.jpg")
        return self.client.post(
            "/api/v1/ocr/",
            {"image": image_file, "save_image": "false"},
            HTTP_X_CANARY_REQUEST="test-canary-secret",
        )

    @patch("lpr_app.views.api_views.ImageProcessingService.process_uploaded_image")
    def test_canary_exception_deletes_db_record(self, mock_process):
        mock_process.side_effect = Exception("Unexpected error")

        self._post_canary_ocr()

        self.assertEqual(UploadedImage.objects.count(), 0)

    @patch("lpr_app.views.api_views.ImageProcessingService.process_uploaded_image")
    def test_canary_exception_returns_500(self, mock_process):
        mock_process.side_effect = Exception("Unexpected error")

        response = self._post_canary_ocr()
        data = response.json()

        self.assertEqual(response.status_code, 500)
        self.assertTrue(data["canary_request"])
        self.assertEqual(data["error_code"], "INTERNAL_ERROR")

    @patch("lpr_app.views.api_views.ImageProcessingService.process_uploaded_image")
    def test_canary_exception_does_not_appear_in_image_list(self, mock_process):
        mock_process.side_effect = Exception("Unexpected error")

        self._post_canary_ocr()

        response = self.client.get("/api/v1/images/")
        data = response.json()
        self.assertEqual(data["count"], 0)

    @patch("lpr_app.views.api_views.ImageProcessingService.process_uploaded_image")
    def test_canary_exception_records_canary_error_metric(self, mock_process):
        mock_process.side_effect = Exception("Unexpected error")

        from ..metrics import CANARY_REQUESTS_TOTAL

        initial_error = CANARY_REQUESTS_TOTAL.labels(status="error")._value._value

        self._post_canary_ocr()

        new_error = CANARY_REQUESTS_TOTAL.labels(status="error")._value._value
        self.assertGreater(new_error, initial_error)

    @patch("lpr_app.views.api_views.ImageProcessingService.process_uploaded_image")
    def test_canary_exception_processing_logs_deleted(self, mock_process):
        mock_process.side_effect = Exception("Unexpected error")

        self._post_canary_ocr()

        self.assertEqual(ProcessingLog.objects.count(), 0)


@override_settings(**CANARY_SETTINGS)
class CanarySuccessPathUnchangedTest(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("lpr_app.views.api_views.ImageProcessingService.process_uploaded_image")
    def test_canary_success_still_cleans_up(self, mock_process):
        mock_process.return_value = {
            "success": True,
            "message": "Canary image processed and cleaned up",
        }

        image_file = _create_real_image_file("canary_ok.jpg")
        response = self.client.post(
            "/api/v1/ocr/",
            {"image": image_file, "save_image": "false"},
            HTTP_X_CANARY_REQUEST="test-canary-secret",
        )

        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["canary_request"])
        self.assertFalse(data["image_saved"])
        self.assertIsNone(data["image_id"])

    @patch("lpr_app.views.api_views.ImageProcessingService.process_uploaded_image")
    def test_non_canary_failure_keeps_record(self, mock_process):
        mock_process.return_value = {"success": False, "error": "API timeout"}

        image_file = _create_real_image_file("normal.jpg")
        response = self.client.post(
            "/api/v1/ocr/",
            {"image": image_file},
        )

        data = response.json()
        self.assertEqual(response.status_code, 500)
        self.assertIsNotNone(data["image_id"])
        self.assertEqual(UploadedImage.objects.count(), 1)
        self.assertFalse(data["canary_request"])

    @patch("lpr_app.views.api_views.ImageProcessingService.process_uploaded_image")
    def test_non_canary_exception_keeps_record(self, mock_process):
        mock_process.side_effect = Exception("Unexpected error")

        image_file = _create_real_image_file("normal_exc.jpg")
        response = self.client.post(
            "/api/v1/ocr/",
            {"image": image_file},
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(UploadedImage.objects.count(), 1)
        img = UploadedImage.objects.first()
        self.assertEqual(img.processing_status, "pending")

    @patch("lpr_app.views.api_views.ImageProcessingService.process_uploaded_image")
    def test_canary_failure_with_save_image_true_keeps_record(self, mock_process):
        mock_process.return_value = {"success": False, "error": "API timeout"}

        image_file = _create_real_image_file("canary_save.jpg")
        response = self.client.post(
            "/api/v1/ocr/",
            {"image": image_file, "save_image": "true"},
            HTTP_X_CANARY_REQUEST="test-canary-secret",
        )

        data = response.json()
        self.assertEqual(response.status_code, 500)
        self.assertIsNotNone(data["image_id"])
        self.assertEqual(UploadedImage.objects.count(), 1)


@override_settings(**CANARY_SETTINGS)
class CanaryExceptionBeforeRecordTest(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("lpr_app.views.api_views.ApiService.create_upload_image_record")
    def test_canary_exception_before_record_creation_no_cleanup_error(self, mock_create):
        mock_create.side_effect = Exception("DB error")

        image_file = _create_real_image_file("before_rec.jpg")
        response = self.client.post(
            "/api/v1/ocr/",
            {"image": image_file, "save_image": "false"},
            HTTP_X_CANARY_REQUEST="test-canary-secret",
        )

        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertTrue(data["canary_request"])
        self.assertEqual(UploadedImage.objects.count(), 0)


@override_settings(MEDIA_ROOT="/tmp/test_lpr_canary_media/")
class CanaryImageNotInSerializerTest(TestCase):
    def test_canary_image_summary_after_cleanup_not_listed(self):
        from ..views.api_views import _serialize_image_summary

        img = UploadedImage.objects.create(
            original_image=_make_image_file("ser.jpg"),
            filename="ser.jpg",
            processing_status="completed",
            file_size=1024,
        )

        result = _serialize_image_summary(img)
        self.assertEqual(result["filename"], "ser.jpg")
        self.assertEqual(result["processing_status"], "completed")
        self.assertEqual(result["file_size"], 10)
        self.assertIn("id", result)

        img.delete()
        self.assertEqual(UploadedImage.objects.count(), 0)


@override_settings(MEDIA_ROOT="/tmp/test_lpr_canary_media/")
class APIConfigEndpointTest(TestCase):
    def test_config_endpoint(self):
        response = self.client.get("/api/v1/config/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("max_upload_bytes", data)
        self.assertIn("processing_timeout_minutes", data)

    @patch("lpr_app.views.api_views.get_qwen_client")
    def test_health_check_healthy(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.health_check.return_value = True
        mock_get_client.return_value = mock_client

        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertTrue(data["api_healthy"])
        self.assertTrue(data["database_healthy"])

    @patch("lpr_app.views.api_views.get_qwen_client")
    def test_health_check_api_unhealthy(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.health_check.return_value = False
        mock_get_client.return_value = mock_client

        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data["status"], "unhealthy")
        self.assertFalse(data["api_healthy"])
