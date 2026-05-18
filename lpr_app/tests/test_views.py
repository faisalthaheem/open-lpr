import io
import json
import re
from datetime import datetime
from unittest.mock import patch

from django.test import TestCase, Client, override_settings
from django.urls import reverse, resolve
from django.core.files.uploadedfile import SimpleUploadedFile

from ..models import UploadedImage, ProcessingLog
from ..views.web_views import image_detail, result_redirect


def _make_image_file(name="test.jpg", content=b"fake image"):
    return SimpleUploadedFile(name, content, content_type="image/jpeg")


@override_settings(MEDIA_ROOT="/tmp/test_lpr_views_media/")
class URLResolutionTest(TestCase):
    def test_image_detail_url_resolves(self):
        url = reverse("lpr_app:image_detail", kwargs={"image_id": 1})
        self.assertEqual(url, "/image/1/")
        match = resolve(url)
        self.assertEqual(match.func, image_detail)

    def test_result_url_resolves_to_redirect(self):
        url = reverse("lpr_app:result", kwargs={"image_id": 1})
        self.assertEqual(url, "/result/1/")
        match = resolve(url)
        self.assertEqual(match.func, result_redirect)

    def test_home_url(self):
        self.assertEqual(reverse("lpr_app:home"), "/")

    def test_image_list_url(self):
        self.assertEqual(reverse("lpr_app:image_list"), "/images/")

    def test_upload_url(self):
        self.assertEqual(reverse("lpr_app:upload"), "/upload/")


@override_settings(MEDIA_ROOT="/tmp/test_lpr_views_media/")
class ResultRedirectTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.image = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="test.jpg",
            processing_status="completed",
        )

    def test_result_redirects_to_image_detail(self):
        response = self.client.get(
            reverse("lpr_app:result", kwargs={"image_id": self.image.id})
        )
        self.assertEqual(response.status_code, 301)
        expected = reverse("lpr_app:image_detail", kwargs={"image_id": self.image.id})
        self.assertEqual(response["Location"], expected)

    def test_result_redirect_for_nonexistent_id(self):
        response = self.client.get(
            reverse("lpr_app:result", kwargs={"image_id": 99999})
        )
        self.assertEqual(response.status_code, 301)


@override_settings(MEDIA_ROOT="/tmp/test_lpr_views_media/")
class ImageDetailViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_completed_image_shows_all_sections(self):
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
                            "coordinates": {"x1": 10, "y1": 20, "x2": 100, "y2": 50},
                        }
                    ],
                }
            ]
        }
        image = UploadedImage.objects.create(
            original_image=_make_image_file(),
            processed_image=_make_image_file("processed_test.jpg"),
            filename="test.jpg",
            processing_status="completed",
            api_response=api_response,
            processing_timestamp=datetime.now(),
        )
        ProcessingLog.objects.create(
            uploaded_image=image,
            status="success",
            message="Processing completed",
            duration_ms=1500,
        )

        response = self.client.get(
            reverse("lpr_app:image_detail", kwargs={"image_id": image.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "lpr_app/image_detail.html")

        content = response.content.decode()

        self.assertIn("Image Information", content)
        self.assertIn("Image Comparison", content)
        self.assertIn("Detection Summary", content)
        self.assertIn("License Plates Detected", content)
        self.assertIn("Detection Details", content)
        self.assertIn("Detection #1", content)
        self.assertIn("ABC 1234", content)
        self.assertIn("Raw API Response", content)
        self.assertIn("Processing Logs", content)
        self.assertIn("Processing completed", content)
        self.assertIn("OCR Texts Found", content)
        self.assertIn("Total Detections", content)
        self.assertIn("Upload Another Image", content)
        self.assertIn("View History", content)

        ctx = response.context
        self.assertEqual(ctx["plate_count"], 1)
        self.assertEqual(ctx["ocr_count"], 1)
        self.assertIsNotNone(ctx["detection_results"])
        self.assertTrue(ctx["processing_logs"].exists())

    def test_failed_image_shows_error_no_detection_sections(self):
        image = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="fail.jpg",
            processing_status="failed",
            error_message="API timeout",
        )
        response = self.client.get(
            reverse("lpr_app:image_detail", kwargs={"image_id": image.id})
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        self.assertIn("Processing Failed", content)
        self.assertIn("API timeout", content)
        self.assertNotIn("Detection Summary", content)
        self.assertNotIn("Detection Details", content)

    def test_pending_image_shows_info_alert(self):
        image = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="pending.jpg",
            processing_status="pending",
        )
        response = self.client.get(
            reverse("lpr_app:image_detail", kwargs={"image_id": image.id})
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        self.assertIn("not been processed yet", content)
        self.assertNotIn("Detection Summary", content)
        self.assertNotIn("Processing Failed", content)

    def test_completed_no_detections_shows_info(self):
        api_response = {"detections": []}
        image = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="nodetect.jpg",
            processing_status="completed",
            api_response=api_response,
        )
        response = self.client.get(
            reverse("lpr_app:image_detail", kwargs={"image_id": image.id})
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("No license plates were detected", content)

    def test_404_for_nonexistent_image(self):
        response = self.client.get(
            reverse("lpr_app:image_detail", kwargs={"image_id": 99999})
        )
        self.assertEqual(response.status_code, 404)

    def test_context_has_detection_data(self):
        api_response = {
            "detections": [
                {
                    "plate": {
                        "confidence": 0.8,
                        "coordinates": {"x1": 0, "y1": 0, "x2": 10, "y2": 10},
                    },
                    "ocr": [
                        {
                            "text": "XYZ",
                            "confidence": 0.7,
                            "coordinates": {"x1": 0, "y1": 0, "x2": 10, "y2": 10},
                        }
                    ],
                }
            ]
        }
        image = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="ctx.jpg",
            processing_status="completed",
            api_response=api_response,
        )
        response = self.client.get(
            reverse("lpr_app:image_detail", kwargs={"image_id": image.id})
        )
        ctx = response.context
        self.assertIn("detection_results", ctx)
        self.assertIn("plate_count", ctx)
        self.assertIn("ocr_count", ctx)
        self.assertIn("processing_logs", ctx)
        self.assertEqual(ctx["plate_count"], 1)
        self.assertEqual(ctx["ocr_count"], 1)

    def test_api_response_section_shows_when_present(self):
        image = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="api.jpg",
            processing_status="failed",
            api_response={"error": "timeout"},
        )
        response = self.client.get(
            reverse("lpr_app:image_detail", kwargs={"image_id": image.id})
        )
        content = response.content.decode()
        self.assertIn("View JSON Response", content)

    def test_api_response_section_hidden_when_absent(self):
        image = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="noapi.jpg",
            processing_status="pending",
        )
        response = self.client.get(
            reverse("lpr_app:image_detail", kwargs={"image_id": image.id})
        )
        content = response.content.decode()
        self.assertNotIn("apiResponseAccordion", content)
        self.assertNotIn("headingApi", content)

    def test_image_comparison_shown_when_processed_exists(self):
        image = UploadedImage.objects.create(
            original_image=_make_image_file(),
            processed_image=_make_image_file("proc.jpg"),
            filename="comp.jpg",
            processing_status="completed",
            api_response={"detections": []},
        )
        response = self.client.get(
            reverse("lpr_app:image_detail", kwargs={"image_id": image.id})
        )
        content = response.content.decode()
        self.assertIn("Image Comparison", content)

    def test_image_comparison_hidden_when_no_processed(self):
        image = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="nocomp.jpg",
            processing_status="completed",
            api_response={"detections": []},
        )
        response = self.client.get(
            reverse("lpr_app:image_detail", kwargs={"image_id": image.id})
        )
        content = response.content.decode()
        self.assertNotIn("Download Processed", content)

    def test_image_comparison_present_with_processed_image(self):
        image = UploadedImage.objects.create(
            original_image=_make_image_file(),
            processed_image=_make_image_file("proc.jpg"),
            filename="hascomp.jpg",
            processing_status="completed",
            api_response={"detections": []},
        )
        response = self.client.get(
            reverse("lpr_app:image_detail", kwargs={"image_id": image.id})
        )
        content = response.content.decode()
        self.assertIn("Original Image</h6>", content)
        self.assertIn("Processed Image</h6>", content)

    def test_dark_mode_uses_css_variables(self):
        image = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="dark.jpg",
            processing_status="completed",
            api_response={"detections": []},
        )
        response = self.client.get(
            reverse("lpr_app:image_detail", kwargs={"image_id": image.id})
        )
        content = response.content.decode()
        self.assertIn("var(--bg-tertiary)", content)
        self.assertIn("var(--text-primary)", content)
        style_blocks = re.findall(r'<style>(.*?)</style>', content, re.DOTALL)
        last_style = style_blocks[-1] if style_blocks else ""
        self.assertNotIn("#2d2d2d", last_style)
        self.assertNotIn("#1a1a1a", last_style)

    def test_processing_logs_format_duration(self):
        image = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="logs.jpg",
            processing_status="completed",
            api_response={"detections": []},
        )
        ProcessingLog.objects.create(
            uploaded_image=image,
            status="api_call",
            message="API call started",
            duration_ms=2500,
        )
        response = self.client.get(
            reverse("lpr_app:image_detail", kwargs={"image_id": image.id})
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("API call started", content)
        self.assertIn("2.5s", content)

    def test_no_result_url_in_page(self):
        image = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="nourl.jpg",
            processing_status="completed",
            api_response={"detections": []},
        )
        response = self.client.get(
            reverse("lpr_app:image_detail", kwargs={"image_id": image.id})
        )
        content = response.content.decode()
        self.assertNotIn("/result/", content)

    def test_accordion_chevron_js_present(self):
        image = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="accord.jpg",
            processing_status="completed",
            api_response={"detections": []},
        )
        response = self.client.get(
            reverse("lpr_app:image_detail", kwargs={"image_id": image.id})
        )
        content = response.content.decode()
        self.assertIn("bi-chevron-down", content)
        self.assertIn("bi-chevron-up", content)


@override_settings(MEDIA_ROOT="/tmp/test_lpr_views_media/")
class ImageListViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_image_list_returns_200(self):
        response = self.client.get(reverse("lpr_app:image_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "lpr_app/image_list.html")

    def test_image_list_links_to_image_detail(self):
        image = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="list.jpg",
            processing_status="completed",
        )
        response = self.client.get(reverse("lpr_app:image_list"))
        content = response.content.decode()
        detail_url = reverse("lpr_app:image_detail", kwargs={"image_id": image.id})
        self.assertIn(detail_url, content)

    def test_image_list_no_result_links(self):
        image = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="list2.jpg",
            processing_status="completed",
        )
        response = self.client.get(reverse("lpr_app:image_list"))
        content = response.content.decode()
        result_url = f"/result/{image.id}/"
        self.assertNotIn(result_url, content)

    def test_image_list_invalid_page_defaults_to_1(self):
        response = self.client.get(reverse("lpr_app:image_list"), {"page": "invalid"})
        self.assertEqual(response.status_code, 200)


@override_settings(MEDIA_ROOT="/tmp/test_lpr_views_media/")
class UploadRedirectURLTest(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("lpr_app.services.image_processing_service.ImageProcessingService.process_uploaded_image")
    def test_upload_redirects_to_image_detail(self, mock_process):
        mock_process.return_value = {"success": True}
        from PIL import Image
        import io
        buf = io.BytesIO()
        Image.new("RGB", (100, 100), "red").save(buf, format="JPEG")
        buf.seek(0)
        img_file = SimpleUploadedFile("test.jpg", buf.read(), content_type="image/jpeg")
        response = self.client.post(
            reverse("lpr_app:upload"),
            {"image": img_file},
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("redirect_url", data)
        self.assertIn("/image/", data["redirect_url"])
        self.assertNotIn("/result/", data["redirect_url"])


@override_settings(MEDIA_ROOT="/tmp/test_lpr_views_media/")
class HomePageTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_home_page_returns_200(self):
        response = self.client.get(reverse("lpr_app:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "lpr_app/upload.html")

    def test_home_page_has_fullscreen_preview_js(self):
        response = self.client.get(reverse("lpr_app:home"))
        content = response.content.decode()
        self.assertIn("openFullscreenPreview", content)
        self.assertIn("result-card", content)
        self.assertIn("Click to preview", content)

    def test_home_page_shows_recent_uploads(self):
        image = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="recent.jpg",
            processing_status="completed",
            api_response={"detections": []},
        )
        response = self.client.get(reverse("lpr_app:home"))
        content = response.content.decode()
        self.assertIn("Recent Uploads", content)
        self.assertIn(image.filename, content)

    def test_home_page_recent_uploads_link_to_detail(self):
        image = UploadedImage.objects.create(
            original_image=_make_image_file(),
            filename="home.jpg",
            processing_status="completed",
        )
        response = self.client.get(reverse("lpr_app:home"))
        content = response.content.decode()
        detail_url = reverse("lpr_app:image_detail", kwargs={"image_id": image.id})
        self.assertIn(detail_url, content)
        self.assertNotIn(f"/result/{image.id}/", content)
