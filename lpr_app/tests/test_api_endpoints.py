import io
import json
from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase, Client, override_settings
from django.urls import reverse, resolve
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


@override_settings(MEDIA_ROOT="/tmp/test_lpr_api_media/")
class APIImageListURLTest(TestCase):
    def test_url_resolves(self):
        url = reverse("lpr_app:api_image_list")
        self.assertEqual(url, "/api/v1/images/")

    def test_url_allows_get(self):
        response = self.client.get("/api/v1/images/")
        self.assertEqual(response.status_code, 200)

    def test_url_rejects_post(self):
        response = self.client.post("/api/v1/images/")
        self.assertEqual(response.status_code, 405)


@override_settings(MEDIA_ROOT="/tmp/test_lpr_api_media/")
class APIImageListResponseTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_empty_list(self):
        response = self.client.get("/api/v1/images/")
        data = response.json()
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["results"], [])
        self.assertIsNone(data["next"])
        self.assertIsNone(data["previous"])

    def test_returns_images_ordered_by_upload_timestamp_desc(self):
        img1 = UploadedImage.objects.create(
            original_image=_make_image_file("a.jpg"),
            filename="a.jpg",
            processing_status="completed",
        )
        img2 = UploadedImage.objects.create(
            original_image=_make_image_file("b.jpg"),
            filename="b.jpg",
            processing_status="completed",
        )
        response = self.client.get("/api/v1/images/")
        data = response.json()
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["results"][0]["id"], img2.id)
        self.assertEqual(data["results"][1]["id"], img1.id)

    def test_result_fields(self):
        UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="test.jpg",
            processing_status="completed",
            file_size=1024,
        )
        response = self.client.get("/api/v1/images/")
        result = response.json()["results"][0]
        self.assertIn("id", result)
        self.assertIn("filename", result)
        self.assertIn("processing_status", result)
        self.assertIn("upload_timestamp", result)
        self.assertIn("processing_timestamp", result)
        self.assertIn("original_image_url", result)
        self.assertIn("processed_image_url", result)
        self.assertIn("file_size", result)

    def test_timestamps_are_iso_format(self):
        UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="ts.jpg",
            processing_status="completed",
            processing_timestamp=datetime(2026, 1, 15, 10, 30, 0),
        )
        response = self.client.get("/api/v1/images/")
        result = response.json()["results"][0]
        self.assertIsNotNone(result["upload_timestamp"])
        self.assertIn("T", result["upload_timestamp"])
        self.assertEqual(result["processing_timestamp"], "2026-01-15T10:30:00+00:00")


@override_settings(MEDIA_ROOT="/tmp/test_lpr_api_media/")
class APIImageListSearchTest(TestCase):
    def setUp(self):
        self.client = Client()
        UploadedImage.objects.create(
            original_image=_make_image_file("abc.jpg"),
            filename="abc.jpg",
            processing_status="completed",
        )
        UploadedImage.objects.create(
            original_image=_make_image_file("xyz.jpg"),
            filename="xyz.jpg",
            processing_status="failed",
        )

    def test_filter_by_query(self):
        response = self.client.get("/api/v1/images/", {"query": "abc"})
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["filename"], "abc.jpg")

    def test_filter_by_status(self):
        response = self.client.get("/api/v1/images/", {"status": "failed"})
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["filename"], "xyz.jpg")

    def test_filter_by_date_from(self):
        future = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        response = self.client.get("/api/v1/images/", {"date_from": future})
        data = response.json()
        self.assertEqual(data["count"], 0)

    def test_filter_by_date_to(self):
        past = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        response = self.client.get("/api/v1/images/", {"date_to": past})
        data = response.json()
        self.assertEqual(data["count"], 0)

    def test_combined_filters(self):
        response = self.client.get("/api/v1/images/", {"query": "abc", "status": "failed"})
        data = response.json()
        self.assertEqual(data["count"], 0)

    def test_query_case_insensitive(self):
        response = self.client.get("/api/v1/images/", {"query": "ABC"})
        data = response.json()
        self.assertEqual(data["count"], 1)


@override_settings(MEDIA_ROOT="/tmp/test_lpr_api_media/")
class APIImageListPaginationTest(TestCase):
    def setUp(self):
        self.client = Client()
        for i in range(25):
            UploadedImage.objects.create(
                original_image=_make_image_file(f"img{i}.jpg"),
                filename=f"img{i}.jpg",
                processing_status="completed",
            )

    def test_default_page_size(self):
        response = self.client.get("/api/v1/images/")
        data = response.json()
        self.assertEqual(len(data["results"]), 12)
        self.assertEqual(data["count"], 25)
        self.assertIsNotNone(data["next"])
        self.assertIsNone(data["previous"])

    def test_second_page(self):
        response = self.client.get("/api/v1/images/", {"page": 2})
        data = response.json()
        self.assertEqual(len(data["results"]), 12)
        self.assertIsNotNone(data["previous"])
        self.assertIsNotNone(data["next"])

    def test_last_page(self):
        response = self.client.get("/api/v1/images/", {"page": 3})
        data = response.json()
        self.assertEqual(len(data["results"]), 1)
        self.assertIsNone(data["next"])

    def test_custom_page_size(self):
        response = self.client.get("/api/v1/images/", {"page_size": 5})
        data = response.json()
        self.assertEqual(len(data["results"]), 5)

    def test_page_size_capped_at_100(self):
        response = self.client.get("/api/v1/images/", {"page_size": 200})
        data = response.json()
        self.assertEqual(len(data["results"]), 25)

    def test_next_url_contains_page_param(self):
        response = self.client.get("/api/v1/images/", {"page_size": 5})
        data = response.json()
        self.assertIn("page=2", data["next"])

    def test_previous_url_contains_page_param(self):
        response = self.client.get("/api/v1/images/", {"page": 2, "page_size": 5})
        data = response.json()
        self.assertIn("page=1", data["previous"])


@override_settings(MEDIA_ROOT="/tmp/test_lpr_api_media/")
class APIImageDetailURLTest(TestCase):
    def test_url_resolves(self):
        url = reverse("lpr_app:api_image_detail", kwargs={"image_id": 1})
        self.assertEqual(url, "/api/v1/images/1/")

    def test_url_rejects_post(self):
        response = self.client.post("/api/v1/images/1/")
        self.assertEqual(response.status_code, 405)


@override_settings(MEDIA_ROOT="/tmp/test_lpr_api_media/")
class APIImageDetailResponseTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_404_for_nonexistent(self):
        response = self.client.get("/api/v1/images/99999/")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("error", data)

    def test_completed_image_detail(self):
        api_response = {
            "detections": [
                {
                    "plate": {
                        "confidence": 0.95,
                        "coordinates": {"x1": 10, "y1": 20, "x2": 100, "y2": 50},
                    },
                    "ocr": [
                        {
                            "text": "ABC 1234",
                            "confidence": 0.9,
                            "coordinates": {"x1": 12, "y1": 22, "x2": 98, "y2": 48},
                        }
                    ],
                }
            ]
        }
        img = UploadedImage.objects.create(
            original_image=_make_image_file("detail.jpg"),
            processed_image=_make_image_file("proc.jpg"),
            filename="detail.jpg",
            processing_status="completed",
            file_size=2048,
            api_response=api_response,
            processing_timestamp=datetime.now(),
            error_message=None,
        )
        ProcessingLog.objects.create(
            uploaded_image=img,
            status="success",
            message="Processing completed",
            duration_ms=1500,
        )

        response = self.client.get(f"/api/v1/images/{img.id}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["id"], img.id)
        self.assertIn("detail.jpg", data["filename"])
        self.assertEqual(data["processing_status"], "completed")
        self.assertIsNotNone(data["file_size"])
        self.assertIsNotNone(data["upload_timestamp"])
        self.assertIsNotNone(data["processing_timestamp"])
        self.assertIsNotNone(data["original_image_url"])
        self.assertIsNotNone(data["processed_image_url"])
        self.assertIsNone(data["error_message"])
        self.assertIsNotNone(data["detections"])
        self.assertEqual(len(data["detections"]["detections"]), 1)
        self.assertEqual(data["detections"]["detections"][0]["ocr"][0]["text"], "ABC 1234")

    def test_detail_includes_processing_logs(self):
        img = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="logs.jpg",
            processing_status="completed",
        )
        ProcessingLog.objects.create(
            uploaded_image=img,
            status="started",
            message="Started",
            duration_ms=100,
        )
        ProcessingLog.objects.create(
            uploaded_image=img,
            status="success",
            message="Done",
            duration_ms=2000,
        )

        response = self.client.get(f"/api/v1/images/{img.id}/")
        data = response.json()
        self.assertEqual(len(data["processing_logs"]), 2)
        log = data["processing_logs"][0]
        self.assertIn("status", log)
        self.assertIn("message", log)
        self.assertIn("timestamp", log)
        self.assertIn("duration_ms", log)

    def test_detail_includes_api_response(self):
        api_response = {"detections": []}
        img = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="api.jpg",
            processing_status="completed",
            api_response=api_response,
        )

        response = self.client.get(f"/api/v1/images/{img.id}/")
        data = response.json()
        self.assertEqual(data["api_response"], api_response)

    def test_failed_image_includes_error(self):
        img = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="fail.jpg",
            processing_status="failed",
            error_message="API timeout",
        )

        response = self.client.get(f"/api/v1/images/{img.id}/")
        data = response.json()
        self.assertEqual(data["processing_status"], "failed")
        self.assertEqual(data["error_message"], "API timeout")

    def test_null_fields_for_pending_image(self):
        img = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="pending.jpg",
            processing_status="pending",
        )

        response = self.client.get(f"/api/v1/images/{img.id}/")
        data = response.json()
        self.assertIsNone(data["processing_timestamp"])
        self.assertIsNone(data["processed_image_url"])
        self.assertIsNone(data["detections"])
        self.assertEqual(data["processing_logs"], [])


@override_settings(MEDIA_ROOT="/tmp/test_lpr_api_media/")
class APIDownloadURLTest(TestCase):
    def test_url_resolves(self):
        url = reverse("lpr_app:api_download_image", kwargs={"image_id": 1, "image_type": "original"})
        self.assertEqual(url, "/api/v1/download/1/original/")

    def test_url_rejects_post(self):
        response = self.client.post("/api/v1/download/1/original/")
        self.assertEqual(response.status_code, 405)


@override_settings(MEDIA_ROOT="/tmp/test_lpr_api_media/")
class APIDownloadResponseTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.img = UploadedImage.objects.create(
            original_image=_create_real_image_file("dl_test.jpg"),
            filename="dl_test.jpg",
            processing_status="completed",
        )

    def test_download_original(self):
        response = self.client.get(f"/api/v1/download/{self.img.id}/original/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("dl_test.jpg", response["Content-Disposition"])

    def test_download_processed_not_found(self):
        response = self.client.get(f"/api/v1/download/{self.img.id}/processed/")
        self.assertEqual(response.status_code, 404)

    def test_download_nonexistent_image(self):
        response = self.client.get("/api/v1/download/99999/original/")
        self.assertEqual(response.status_code, 404)

    def test_download_invalid_type(self):
        response = self.client.get(f"/api/v1/download/{self.img.id}/invalid/")
        self.assertEqual(response.status_code, 404)


@override_settings(
    MEDIA_ROOT="/tmp/test_lpr_api_media/",
    CORS_ALLOWED_ORIGINS=["http://testserver"],
)
class CORSMiddlewareTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_cors_header_on_api_response(self):
        response = self.client.get(
            "/api/v1/images/",
            HTTP_ORIGIN="http://testserver",
        )
        self.assertEqual(response.get("Access-Control-Allow-Origin"), "http://testserver")

    def test_cors_preflight(self):
        response = self.client.options(
            "/api/v1/images/",
            HTTP_ORIGIN="http://testserver",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get("Access-Control-Allow-Origin"), "http://testserver")

    def test_cors_rejects_unknown_origin(self):
        response = self.client.get(
            "/api/v1/images/",
            HTTP_ORIGIN="http://evil.example.com",
        )
        self.assertNotEqual(response.get("Access-Control-Allow-Origin"), "http://evil.example.com")

    def test_cors_on_ocr_endpoint(self):
        response = self.client.options(
            "/api/v1/ocr/",
            HTTP_ORIGIN="http://testserver",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )
        self.assertEqual(response.get("Access-Control-Allow-Origin"), "http://testserver")

    def test_cors_on_image_detail(self):
        img = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="cors.jpg",
            processing_status="completed",
        )
        response = self.client.get(
            f"/api/v1/images/{img.id}/",
            HTTP_ORIGIN="http://testserver",
        )
        self.assertEqual(response.get("Access-Control-Allow-Origin"), "http://testserver")

    def test_cors_on_download(self):
        img = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="corsdl.jpg",
            processing_status="completed",
        )
        response = self.client.get(
            f"/api/v1/download/{img.id}/original/",
            HTTP_ORIGIN="http://testserver",
        )
        self.assertIn(response.get("Access-Control-Allow-Origin"), ["http://testserver", None])


@override_settings(MEDIA_ROOT="/tmp/test_lpr_api_media/")
class CORSConfigTest(TestCase):
    def test_cors_allowed_origins_setting_exists(self):
        from django.conf import settings
        self.assertTrue(hasattr(settings, "CORS_ALLOWED_ORIGINS"))
        self.assertIsInstance(settings.CORS_ALLOWED_ORIGINS, list)

    def test_cors_middleware_installed(self):
        from django.conf import settings
        self.assertIn("corsheaders.middleware.CorsMiddleware", settings.MIDDLEWARE)

    def test_cors_middleware_before_common(self):
        from django.conf import settings
        cors_idx = settings.MIDDLEWARE.index("corsheaders.middleware.CorsMiddleware")
        common_idx = settings.MIDDLEWARE.index("django.middleware.common.CommonMiddleware")
        self.assertLess(cors_idx, common_idx)

    def test_corsheaders_in_installed_apps(self):
        from django.conf import settings
        self.assertIn("corsheaders", settings.INSTALLED_APPS)
