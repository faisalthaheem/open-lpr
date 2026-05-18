import os
import tempfile
from unittest import skipUnless

from django.test import TestCase
from PIL import Image, ImageDraw, ImageFont

from lpr_app.services.bbox_visualizer import BoundingBoxVisualizer, visualize_lpr_on_image

TEST_IMAGES_DIR = os.path.join(os.path.dirname(__file__), "test_images")

HAS_NOTO = os.path.exists("/usr/share/fonts/noto/NotoSans-Regular.ttf") or os.path.exists(
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
)
HAS_NOTO_ARABIC = os.path.exists("/usr/share/fonts/noto/NotoSansArabic-Regular.ttf") or os.path.exists(
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf"
)
HAS_NOTO_CJK = (
    os.path.exists("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    or os.path.exists("/usr/share/fonts/truetype/noto-cjk/NotoSansCJK-Regular.ttc")
    or os.path.exists("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc")
)
HAS_ARABIC_TEST_IMAGE = os.path.exists(os.path.join(TEST_IMAGES_DIR, "arabic.jpg"))


def _create_test_image(width=800, height=600):
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(img)
    d.text((10, 10), "test", fill="black")
    img.save(tmp.name, "JPEG")
    tmp.close()
    return tmp.name


def _count_unique_glyphs(font, chars):
    hashes = []
    for c in chars:
        img = Image.new("L", (60, 60), 255)
        d = ImageDraw.Draw(img)
        d.text((5, 5), c, font=font, fill=0)
        hashes.append(hash(img.tobytes()))
    return len(set(hashes))


class FontLoadingTest(TestCase):
    def test_load_font_returns_freetype(self):
        viz = BoundingBoxVisualizer.__new__(BoundingBoxVisualizer)
        font = viz._load_font(20)
        self.assertIsInstance(font, ImageFont.FreeTypeFont)

    def test_load_font_with_size(self):
        viz = BoundingBoxVisualizer.__new__(BoundingBoxVisualizer)
        font = viz._load_font(30)
        self.assertIsInstance(font, ImageFont.FreeTypeFont)

    @skipUnless(HAS_NOTO, "Noto Sans font not installed")
    def test_load_font_prefers_noto_sans(self):
        viz = BoundingBoxVisualizer.__new__(BoundingBoxVisualizer)
        font = viz._load_font(20)
        name = font.getname()
        self.assertEqual(name[0], "Noto Sans")


class ScriptDetectionTest(TestCase):
    def test_latin_text(self):
        self.assertEqual(BoundingBoxVisualizer._detect_script("Hello World"), "latin")

    def test_arabic_text(self):
        self.assertEqual(BoundingBoxVisualizer._detect_script("٥١٥٦٢٩ اربيل العراق"), "arabic")

    def test_arabic_chars(self):
        self.assertEqual(BoundingBoxVisualizer._detect_script("مرحبا"), "arabic")

    def test_cjk_japanese(self):
        self.assertEqual(BoundingBoxVisualizer._detect_script("こんにちは"), "cjk")

    def test_cjk_chinese(self):
        self.assertEqual(BoundingBoxVisualizer._detect_script("中文"), "cjk")

    def test_cjk_korean(self):
        self.assertEqual(BoundingBoxVisualizer._detect_script("안녕하세요"), "cjk")

    def test_mixed_arabic_latin(self):
        self.assertEqual(BoundingBoxVisualizer._detect_script("٥١٥٦٢٩ (0.95)"), "arabic")

    def test_mixed_cjk_latin(self):
        self.assertEqual(BoundingBoxVisualizer._detect_script("東京 ABC"), "cjk")

    def test_empty_string(self):
        self.assertEqual(BoundingBoxVisualizer._detect_script(""), "latin")

    def test_numbers_only(self):
        self.assertEqual(BoundingBoxVisualizer._detect_script("123.45"), "latin")

    def test_hebrew_text(self):
        self.assertEqual(BoundingBoxVisualizer._detect_script("שלום"), "hebrew")

    def test_thai_text(self):
        self.assertEqual(BoundingBoxVisualizer._detect_script("สวัสดี"), "thai")

    def test_devanagari_text(self):
        self.assertEqual(BoundingBoxVisualizer._detect_script("नमस्ते"), "devanagari")


class ScriptFontLoadingTest(TestCase):
    @skipUnless(HAS_NOTO, "Noto Sans font not installed")
    def test_latin_text_uses_default_font(self):
        path = _create_test_image()
        try:
            viz = BoundingBoxVisualizer(path)
            font = viz._load_font_for_text("Hello World")
            self.assertEqual(font, viz.font)
        finally:
            os.unlink(path)

    @skipUnless(HAS_NOTO_ARABIC, "Noto Sans Arabic font not installed")
    def test_arabic_text_loads_arabic_font(self):
        path = _create_test_image()
        try:
            viz = BoundingBoxVisualizer(path)
            font = viz._load_font_for_text("مرحبا")
            self.assertNotEqual(font, viz.font)
            name = font.getname()
            self.assertIn("Arabic", name[0])
        finally:
            os.unlink(path)

    @skipUnless(HAS_NOTO_ARABIC, "Noto Sans Arabic font not installed")
    def test_arabic_font_cached(self):
        path = _create_test_image()
        try:
            viz = BoundingBoxVisualizer(path)
            font1 = viz._load_font_for_text("مرحبا")
            font2 = viz._load_font_for_text("أخرى")
            self.assertIs(font1, font2)
        finally:
            os.unlink(path)

    @skipUnless(HAS_NOTO_CJK, "Noto Sans CJK font not installed")
    def test_cjk_text_loads_cjk_font(self):
        path = _create_test_image()
        try:
            viz = BoundingBoxVisualizer(path)
            font = viz._load_font_for_text("こんにちは")
            self.assertNotEqual(font, viz.font)
            name = font.getname()
            self.assertIn("CJK", name[0])
        finally:
            os.unlink(path)


class ArabicRenderingTest(TestCase):
    @skipUnless(HAS_NOTO_ARABIC, "Noto Sans Arabic font not installed")
    def test_arabic_text_renders_unique_glyphs(self):
        viz = BoundingBoxVisualizer.__new__(BoundingBoxVisualizer)
        viz._font_cache = {}
        viz.font = viz._load_font(36)
        viz.font_size = 36
        font = viz._load_font_for_text("أبيةعرقل")
        unique = _count_unique_glyphs(font, list("أبيةعرقل"))
        self.assertEqual(unique, 8, f"Arabic chars not distinct. Got {unique}/8 unique.")

    @skipUnless(HAS_NOTO_ARABIC, "Noto Sans Arabic font not installed")
    def test_arabic_digits_render_unique_glyphs(self):
        viz = BoundingBoxVisualizer.__new__(BoundingBoxVisualizer)
        viz._font_cache = {}
        viz.font = viz._load_font(36)
        viz.font_size = 36
        font = viz._load_font_for_text("٠١٢٣")
        unique = _count_unique_glyphs(font, list("٠١٢٣٤٥٦٧٨٩"))
        self.assertEqual(unique, 10, f"Arabic-Indic digits not distinct. Got {unique}/10 unique.")

    @skipUnless(HAS_NOTO_ARABIC, "Noto Sans Arabic font not installed")
    def test_arabic_vs_latin_glyphs_differ(self):
        viz = BoundingBoxVisualizer.__new__(BoundingBoxVisualizer)
        viz._font_cache = {}
        viz.font = viz._load_font(36)
        viz.font_size = 36
        ar_font = viz._load_font_for_text("أ")
        img_ar = Image.new("L", (60, 60), 255)
        ImageDraw.Draw(img_ar).text((5, 5), "أ", font=ar_font, fill=0)
        img_lat = Image.new("L", (60, 60), 255)
        ImageDraw.Draw(img_lat).text((5, 5), "A", font=ar_font, fill=0)
        self.assertNotEqual(hash(img_ar.tobytes()), hash(img_lat.tobytes()))

    @skipUnless(HAS_NOTO_ARABIC, "Noto Sans Arabic font not installed")
    def test_arabic_label_renders_non_blank(self):
        path = _create_test_image()
        try:
            viz = BoundingBoxVisualizer(path)
            viz.draw_bounding_box(
                x1=100, y1=100, x2=300, y2=200,
                color=(0, 255, 0),
                label="٥١٥٦٢٩ اربيل العراق (0.95)",
            )
            tmp_out = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            tmp_out.close()
            viz.save_result(tmp_out.name)
            with Image.open(tmp_out.name) as result:
                pixels = list(result.getdata())
                non_white = sum(1 for p in pixels if p != (255, 255, 255))
                self.assertGreater(non_white, 100, "Label area appears blank")
            os.unlink(tmp_out.name)
        finally:
            os.unlink(path)


class CJKRenderingTest(TestCase):
    @skipUnless(HAS_NOTO_CJK, "Noto Sans CJK font not installed")
    def test_cjk_text_renders_unique_glyphs(self):
        viz = BoundingBoxVisualizer.__new__(BoundingBoxVisualizer)
        viz._font_cache = {}
        viz.font = viz._load_font(36)
        viz.font_size = 36
        font = viz._load_font_for_text("こんにちは")
        unique = _count_unique_glyphs(font, list("こんにちは"))
        self.assertEqual(unique, 5, f"CJK chars not distinct. Got {unique}/5 unique.")

    @skipUnless(HAS_NOTO_CJK, "Noto Sans CJK font not installed")
    def test_cjk_label_renders_non_blank(self):
        path = _create_test_image()
        try:
            viz = BoundingBoxVisualizer(path)
            viz.draw_bounding_box(
                x1=100, y1=100, x2=300, y2=200,
                color=(0, 255, 0),
                label="品川 (0.95)",
            )
            tmp_out = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            tmp_out.close()
            viz.save_result(tmp_out.name)
            with Image.open(tmp_out.name) as result:
                pixels = list(result.getdata())
                non_white = sum(1 for p in pixels if p != (255, 255, 255))
                self.assertGreater(non_white, 100, "Label area appears blank")
            os.unlink(tmp_out.name)
        finally:
            os.unlink(path)


class ArabicPlateVisualTest(TestCase):
    """
    Visual verification tests using the actual arabic.jpg test image.

    These tests render the full LPR pipeline on the real image and save
    output for manual visual inspection. They also assert that:
      - Arabic text uses the Arabic-specific font (not Latin-only fallback)
      - Arabic glyphs are distinct (not replacement circles/boxes)
      - The label area is non-blank in the output image
      - Output is saved to /tmp/ for manual review
    """

    OCR_TEXT = "٥١٥٦٢٩ اربيل العراق"

    @skipUnless(HAS_ARABIC_TEST_IMAGE, "arabic.jpg test image not found in test_images/")
    def test_arabic_image_loads(self):
        path = os.path.join(TEST_IMAGES_DIR, "arabic.jpg")
        viz = BoundingBoxVisualizer(path)
        self.assertIsNotNone(viz.image)
        self.assertGreater(viz.image.width, 0)
        self.assertGreater(viz.image.height, 0)

    @skipUnless(HAS_ARABIC_TEST_IMAGE and HAS_NOTO_ARABIC, "arabic.jpg or Noto Arabic font missing")
    def test_arabic_image_uses_arabic_font(self):
        path = os.path.join(TEST_IMAGES_DIR, "arabic.jpg")
        viz = BoundingBoxVisualizer(path)
        label = f"{self.OCR_TEXT} (0.95)"
        font = viz._load_font_for_text(label)
        self.assertNotEqual(font, viz.font, "Arabic label should use Arabic-specific font")
        name = font.getname()
        self.assertIn("Arabic", name[0], f"Expected Arabic font, got {name}")

    @skipUnless(HAS_ARABIC_TEST_IMAGE and HAS_NOTO_ARABIC, "arabic.jpg or Noto Arabic font missing")
    def test_arabic_image_renders_distinct_glyphs(self):
        path = os.path.join(TEST_IMAGES_DIR, "arabic.jpg")
        viz = BoundingBoxVisualizer(path)
        label = f"{self.OCR_TEXT} (0.95)"
        font = viz._load_font_for_text(label)
        chars = [c for c in self.OCR_TEXT if c.strip()]
        unique = _count_unique_glyphs(font, chars)
        self.assertGreaterEqual(unique, 5, f"Arabic OCR text should have distinct glyphs, got {unique}/{len(chars)}")

    @skipUnless(HAS_ARABIC_TEST_IMAGE and HAS_NOTO_ARABIC, "arabic.jpg or Noto Arabic font missing")
    def test_arabic_image_full_pipeline_visual(self):
        """
        Full pipeline test: render plate detection + OCR on arabic.jpg.

        Saves output to /tmp/test_arabic_visual_result.png for manual inspection.
        Asserts that the label region is non-blank and uses Arabic font.
        """
        image_path = os.path.join(TEST_IMAGES_DIR, "arabic.jpg")
        output_path = "/tmp/test_arabic_visual_result.png"

        lpr_data = {
            "detections": [{
                "plate": {
                    "confidence": 0.98,
                    "coordinates": {"x1": 349, "y1": 682, "x2": 605, "y2": 852},
                },
                "ocr": [{
                    "text": self.OCR_TEXT,
                    "confidence": 0.95,
                    "coordinates": {"x1": 355, "y1": 685, "x2": 569, "y2": 828},
                }],
            }]
        }

        result = visualize_lpr_on_image(image_path, lpr_data, output_path)
        self.assertTrue(result, "visualize_lpr_on_image should return True")
        self.assertTrue(os.path.exists(output_path), f"Output file should exist at {output_path}")

        with Image.open(output_path) as img:
            self.assertEqual(img.mode, "RGB")

            label_region = img.crop((340, 620, 700, 685))
            pixels = list(label_region.getdata())
            non_white = sum(1 for p in pixels if p != (255, 255, 255))
            self.assertGreater(non_white, 500, "Label region should have significant non-white content")

            dark_bg = sum(1 for p in pixels if p[0] < 50 and p[1] < 50 and p[2] < 50)
            self.assertGreater(dark_bg, 100, "Label should have dark background bar")

            green_bar = sum(1 for p in pixels if p[1] > 200 and p[0] < 50 and p[2] < 50)
            self.assertGreater(green_bar, 10, "Label should have green color bar")

        print(f"\n  Visual output saved to: {output_path}")
        print(f"  Inspect this file to verify Arabic text renders correctly.")

    @skipUnless(HAS_ARABIC_TEST_IMAGE and HAS_NOTO_ARABIC, "arabic.jpg or Noto Arabic font missing")
    def test_arabic_image_label_pixel_diversity(self):
        """
        Verify that the label text area has diverse pixel values,
        indicating real text glyphs rather than uniform circles/boxes.
        """
        image_path = os.path.join(TEST_IMAGES_DIR, "arabic.jpg")
        output_path = "/tmp/test_arabic_pixel_diversity.png"

        lpr_data = {
            "detections": [{
                "plate": {
                    "confidence": 0.98,
                    "coordinates": {"x1": 349, "y1": 682, "x2": 605, "y2": 852},
                },
                "ocr": [{
                    "text": self.OCR_TEXT,
                    "confidence": 0.95,
                    "coordinates": {"x1": 355, "y1": 685, "x2": 569, "y2": 828},
                }],
            }]
        }

        visualize_lpr_on_image(image_path, lpr_data, output_path)

        with Image.open(output_path) as img:
            label_region = img.crop((340, 600, 700, 695))
            pixels = list(label_region.getdata())
            unique_colors = len(set(pixels))
            self.assertGreater(unique_colors, 10, f"Label region should have diverse colors, got {unique_colors}")

            bright_pixels = sum(1 for p in pixels if p[0] > 200 and p[1] > 200 and p[2] > 200)
            self.assertGreater(bright_pixels, 20, "Should have bright text pixels on dark background")

        os.unlink(output_path)


class BoundingBoxVisualizerInitTest(TestCase):
    def test_init_with_valid_image(self):
        path = _create_test_image()
        try:
            viz = BoundingBoxVisualizer(path)
            self.assertIsNotNone(viz.image)
            self.assertIsNotNone(viz.draw)
            self.assertIsNotNone(viz.font)
        finally:
            os.unlink(path)

    def test_font_size_computed_from_image_height(self):
        path = _create_test_image(height=1000)
        try:
            viz = BoundingBoxVisualizer(path)
            expected = max(16, min(64, int(1000 * 0.02)))
            self.assertEqual(viz.font_size, expected)
        finally:
            os.unlink(path)

    def test_font_size_minimum(self):
        path = _create_test_image(height=100)
        try:
            viz = BoundingBoxVisualizer(path)
            self.assertGreaterEqual(viz.font_size, 16)
        finally:
            os.unlink(path)

    def test_font_cache_initialized(self):
        path = _create_test_image()
        try:
            viz = BoundingBoxVisualizer(path)
            self.assertIsInstance(viz._font_cache, dict)
            self.assertEqual(len(viz._font_cache), 0)
        finally:
            os.unlink(path)


class RaqmSupportTest(TestCase):
    def test_pillow_has_raqm_support(self):
        from PIL import features
        self.assertTrue(
            features.check("raqm"),
            "Pillow raqm support is disabled. Install libraqm for proper "
            "Arabic/RTL text shaping (connected letter forms).",
        )
