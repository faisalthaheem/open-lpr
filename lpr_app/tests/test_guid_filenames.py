import io
import os
import tempfile
from unittest.mock import MagicMock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from PIL import Image

from lpr_app.models import upload_to_uploads, upload_to_processed, UploadedImage
from lpr_app.services.file_service import FileService


def _make_uploaded_file(name='test.jpg', content_type='image/jpeg'):
    img = Image.new('RGB', (100, 100), 'white')
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type=content_type)


class GuidUploadPathTest(TestCase):

    def test_two_same_name_files_get_distinct_paths(self):
        path1 = upload_to_uploads(MagicMock(), 'plate.jpg')
        path2 = upload_to_uploads(MagicMock(), 'plate.jpg')
        self.assertNotEqual(path1, path2)
        self.assertTrue(path1.startswith('uploads/'))
        self.assertTrue(path2.startswith('uploads/'))

    def test_guid_prefix_is_8_hex_chars(self):
        path = upload_to_uploads(MagicMock(), 'photo.png')
        basename = os.path.basename(path)
        parts = basename.split('_', 1)
        self.assertEqual(len(parts[0]), 8)
        int(parts[0], 16)

    def test_processed_path_uses_guid_prefix(self):
        path = upload_to_processed(MagicMock(), 'photo.png')
        basename = os.path.basename(path)
        self.assertTrue(path.startswith('processed/'))
        parts = basename.split('_', 1)
        self.assertEqual(len(parts[0]), 8)

    def test_extension_preserved_in_upload_path(self):
        path = upload_to_uploads(MagicMock(), 'photo.png')
        self.assertTrue(path.endswith('.png'))

    def test_extension_preserved_in_processed_path(self):
        path = upload_to_processed(MagicMock(), 'photo.bmp')
        self.assertTrue(path.endswith('.bmp'))

    def test_no_extension_file_preserved(self):
        path = upload_to_uploads(MagicMock(), 'image')
        basename = os.path.basename(path)
        self.assertTrue(basename.endswith('_image'))
        self.assertNotIn('.', basename.split('_', 1)[0])


class FilenameFieldPreservedTest(TestCase):

    def test_filename_field_retains_original_name(self):
        uploaded_file = _make_uploaded_file(name='my-car.jpg')
        img = UploadedImage.objects.create(
            original_image=uploaded_file,
            filename='my-car.jpg',
            processing_status='pending',
        )
        self.assertEqual(img.filename, 'my-car.jpg')

    def test_storage_path_differs_from_filename(self):
        uploaded_file = _make_uploaded_file(name='my-car.jpg')
        img = UploadedImage.objects.create(
            original_image=uploaded_file,
            filename='my-car.jpg',
            processing_status='pending',
        )
        basename = os.path.basename(img.original_image.name)
        self.assertNotEqual(basename, 'my-car.jpg')
        self.assertIn('my-car.jpg', basename)


class DownloadFilenameTest(TestCase):

    def test_download_uses_original_filename(self):
        uploaded_file = _make_uploaded_file(name='plate-number.jpg')
        img = UploadedImage.objects.create(
            original_image=uploaded_file,
            filename='plate-number.jpg',
            processing_status='completed',
        )
        response = FileService.download_image(img.id, 'original')
        self.assertIn('plate-number.jpg', response['Content-Disposition'])


class GuidPrefixExtensionTest(TestCase):

    def test_jpg_extension_preserved(self):
        path = upload_to_uploads(MagicMock(), 'test.jpg')
        self.assertTrue(path.endswith('.jpg'))

    def test_png_extension_preserved(self):
        path = upload_to_uploads(MagicMock(), 'test.png')
        self.assertTrue(path.endswith('.png'))

    def test_date_partitioning_preserved(self):
        from datetime import datetime
        now = datetime.now()
        path = upload_to_uploads(MagicMock(), 'test.jpg')
        expected_prefix = f'uploads/{now.year}/{now.month:02d}/{now.day:02d}/'
        self.assertTrue(path.startswith(expected_prefix))
