from django.test import TestCase
from lpr_app.templatetags.duration_format import format_duration


class FormatDurationFilterTest(TestCase):
    def test_none_returns_dash(self):
        self.assertEqual(format_duration(None), "-")

    def test_empty_string_returns_dash(self):
        self.assertEqual(format_duration(""), "-")

    def test_milliseconds_under_1000(self):
        self.assertEqual(format_duration(500), "500ms")

    def test_zero(self):
        self.assertEqual(format_duration(0), "0ms")

    def test_exactly_999(self):
        self.assertEqual(format_duration(999), "999ms")

    def test_1_second(self):
        self.assertEqual(format_duration(1000), "1.0s")

    def test_2_5_seconds(self):
        self.assertEqual(format_duration(2500), "2.5s")

    def test_30_seconds(self):
        self.assertEqual(format_duration(30000), "30.0s")

    def test_60_seconds_shows_minutes(self):
        self.assertEqual(format_duration(60000), "1m 0s")

    def test_90_seconds(self):
        self.assertEqual(format_duration(90000), "1m 30s")

    def test_2_minutes(self):
        self.assertEqual(format_duration(120000), "2m 0s")

    def test_large_value(self):
        self.assertEqual(format_duration(2204000), "36m 44s")

    def test_string_number(self):
        self.assertEqual(format_duration("500"), "500ms")

    def test_invalid_string(self):
        self.assertEqual(format_duration("abc"), "-")


class FullscreenPreviewTemplateTest(TestCase):
    def test_base_template_contains_overlay(self):
        from django.template.loader import render_to_string
        html = render_to_string("base.html")
        self.assertIn("fullscreenPreview", html)
        self.assertIn("openFullscreenPreview", html)
        self.assertIn("closeFullscreenPreview", html)
        self.assertIn("fullscreen-preview-close", html)

    def test_image_detail_template_loads_duration_filter(self):
        from django.template.loader import get_template
        try:
            tmpl = get_template("lpr_app/image_detail.html")
            self.assertIsNotNone(tmpl)
        except Exception:
            self.fail("image_detail.html failed to load (missing template tag?)")
