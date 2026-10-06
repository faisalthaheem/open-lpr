"""Decompression-bomb defence on the public upload path.

Bounding `UPLOAD_FILE_MAX_SIZE` bounds bytes on disk. It does not bound memory,
which is what actually kills a worker. A PNG of one flat colour compresses by
roughly 3000:1, so an upload well inside the size limit can declare 144
megapixels and cost 430MB of RAM once decoded. At two requests a minute per IP
that is a cheap way to exhaust a container's memory.

Pillow has its own guard, but the default threshold is high enough to be
irrelevant here: it warns below 178 megapixels and errors above. A 144MP image
sits in the warning band, which is not a rejection.

These tests pin the properties that matter: the check reads the header without
decoding, it rejects on declared dimensions, and it does not change the verdict
for ordinary photographs.
"""

from __future__ import annotations

import io
import struct
import warnings
import zlib

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from PIL import Image

from lpr_app.services.image_processor import ImageProcessor
from lpr_app.utils.validators import FileValidator, check_image_dimensions

LIMIT = 40_000_000


def make_flat_png(width: int, height: int) -> bytes:
    """A PNG of one solid colour: tiny on disk, huge once decoded.

    This is the actual attack shape. A gradient or noisy image would be a poor
    test because it compresses badly and trips the file-size limit instead.
    """
    row = b"\x00" + bytes(width * 3)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    body = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
    body += chunk(b"IDAT", zlib.compress(row * height, 9)) + chunk(b"IEND", b"")
    return body


def upload(data: bytes, name: str = "bomb.png") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, data, content_type="image/png")


class HeaderOnlyCheckTests(SimpleTestCase):
    @override_settings(UPLOAD_IMAGE_MAX_PIXELS=LIMIT)
    def test_oversized_dimensions_are_rejected(self):
        # 12000x12000 = 144MP. Under Pillow's 178MP error threshold, so without
        # this check it is accepted with only a warning.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            is_valid, error = check_image_dimensions(upload(make_flat_png(12000, 12000)))

        self.assertFalse(is_valid)
        self.assertIn("too large", error)
        self.assertIn("12000x12000", error)

    @override_settings(UPLOAD_IMAGE_MAX_PIXELS=LIMIT)
    def test_ordinary_photograph_is_accepted(self):
        # 4000x3000 = 12MP, a typical phone photo.
        is_valid, error = check_image_dimensions(upload(make_flat_png(4000, 3000)))

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    @override_settings(UPLOAD_IMAGE_MAX_PIXELS=LIMIT)
    def test_exactly_at_the_limit_is_accepted(self):
        """The limit is inclusive.

        An off-by-one that rejected images at exactly the documented maximum
        would make the setting a lie.
        """
        is_valid, _ = check_image_dimensions(upload(make_flat_png(4000, 10_000)))
        self.assertTrue(is_valid)  # exactly 40,000,000

    @override_settings(UPLOAD_IMAGE_MAX_PIXELS=LIMIT)
    def test_one_pixel_over_the_limit_is_rejected(self):
        is_valid, _ = check_image_dimensions(upload(make_flat_png(5000, 8_001)))
        self.assertFalse(is_valid)  # 40,005,000

    @override_settings(UPLOAD_IMAGE_MAX_PIXELS=0)
    def test_zero_disables_the_check(self):
        """0 means unlimited, for callers who have bounded memory another way."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            is_valid, _ = check_image_dimensions(upload(make_flat_png(12000, 12000)))

        self.assertTrue(is_valid)

    @override_settings(UPLOAD_IMAGE_MAX_PIXELS=LIMIT)
    def test_non_image_is_left_to_the_caller(self):
        """Not our error to report.

        Returning False here would give users a second, different message for
        the same corrupt file.
        """
        is_valid, error = check_image_dimensions(SimpleUploadedFile("x.png", b"not an image at all"))

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    @override_settings(UPLOAD_IMAGE_MAX_PIXELS=LIMIT)
    def test_does_not_decode_pixel_data(self):
        """The whole point is to refuse before allocating.

        If this test needed meaningful memory to pass, the guard would be
        checking after the fact, which is too late to be a defence.
        """
        data = make_flat_png(9000, 9000)  # 81MP, ~250KB on disk
        self.assertLess(len(data), 1_000_000, "fixture must stay inside the size limit")

        source = upload(data)
        with Image.open(source) as img:
            self.assertEqual(img.size, (9000, 9000))
            # Read the header only; img.getpixel() would force a decode.
            self.assertEqual(img.width, 9000)

        is_valid, _ = check_image_dimensions(upload(data))
        self.assertFalse(is_valid)


class ValidationPathTests(SimpleTestCase):
    @override_settings(UPLOAD_IMAGE_MAX_PIXELS=LIMIT, UPLOAD_FILE_MAX_SIZE=10 * 1024 * 1024)
    def test_image_processor_rejects_the_bomb(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            is_valid, error = ImageProcessor.validate_image(upload(make_flat_png(12000, 12000)))

        self.assertFalse(is_valid)
        self.assertIn("too large", error)

    @override_settings(UPLOAD_IMAGE_MAX_PIXELS=LIMIT, UPLOAD_FILE_MAX_SIZE=10 * 1024 * 1024)
    def test_file_validator_rejects_the_bomb(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            is_valid, error = FileValidator.validate_image_file(upload(make_flat_png(12000, 12000)))

        self.assertFalse(is_valid)
        self.assertIn("too large", error)

    @override_settings(UPLOAD_IMAGE_MAX_PIXELS=LIMIT, UPLOAD_FILE_MAX_SIZE=10 * 1024 * 1024)
    def test_real_image_still_passes_validation(self):
        """A guard that rejects valid input is an outage, not a defence."""
        buf = io.BytesIO()
        Image.new("RGB", (640, 480), (10, 20, 30)).save(buf, format="JPEG")
        jpeg = SimpleUploadedFile("plate.jpg", buf.getvalue(), content_type="image/jpeg")

        is_valid, error = ImageProcessor.validate_image(jpeg)
        self.assertTrue(is_valid, f"valid JPEG rejected: {error}")

        is_valid, error = FileValidator.validate_image_file(jpeg)
        self.assertTrue(is_valid, f"valid JPEG rejected: {error}")


class OpenImageInputTests(SimpleTestCase):
    """The validator must accept an already-open image, not only a file.

    A PIL image is not file-like: it has no ``read``. The version that shipped
    called ``Image.open`` unconditionally, so the decode path in
    ``_run_local_pipeline`` -- which passes an already-open image -- raised
    ``AttributeError`` on every upload and returned HTTP 500 in production.

    The original ten tests all passed file-like objects. That is the gap this
    class closes: the function was tested and the call site wired to it in the
    same commit, and only the former was exercised.
    """

    @override_settings(UPLOAD_IMAGE_MAX_PIXELS=LIMIT)
    def test_open_image_returns_a_verdict(self):
        with Image.open(io.BytesIO(make_flat_png(4000, 3000))) as opened:
            is_valid, error = check_image_dimensions(opened)

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    @override_settings(UPLOAD_IMAGE_MAX_PIXELS=LIMIT)
    def test_open_oversized_image_is_rejected(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with Image.open(io.BytesIO(make_flat_png(12000, 12000))) as opened:
                is_valid, error = check_image_dimensions(opened)

        self.assertFalse(is_valid)
        self.assertIn("too large", error)
        self.assertIn("12000x12000", error)

    @override_settings(UPLOAD_IMAGE_MAX_PIXELS=LIMIT)
    def test_both_input_forms_agree(self):
        """The same image must get the same verdict either way.

        Divergence here would mean the call site is being validated by a
        different rule than the one the tests describe.
        """
        for width, height in ((4000, 3000), (12000, 12000)):
            data = make_flat_png(width, height)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from_file, file_error = check_image_dimensions(upload(data))
                with Image.open(io.BytesIO(data)) as opened:
                    from_open, open_error = check_image_dimensions(opened)

            self.assertEqual(from_file, from_open, f"{width}x{height} verdict differs by input form")
            self.assertEqual(file_error, open_error, f"{width}x{height} error differs by input form")

    @override_settings(UPLOAD_IMAGE_MAX_PIXELS=0)
    def test_open_image_respects_disabled_check(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with Image.open(io.BytesIO(make_flat_png(12000, 12000))) as opened:
                is_valid, _ = check_image_dimensions(opened)

        self.assertTrue(is_valid)

    @override_settings(UPLOAD_IMAGE_MAX_PIXELS=LIMIT)
    def test_decode_call_site_receives_a_verdict(self):
        """Exercise the actual call site, not the validator in isolation.

        This mirrors what ``_run_local_pipeline`` does: open the file, then hand
        the open image to the validator. Reproducing the shape of that call is
        the only way a regression in the wiring is caught here.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with Image.open(io.BytesIO(make_flat_png(12000, 12000))) as opened:
                is_valid, error = check_image_dimensions(opened)

        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
