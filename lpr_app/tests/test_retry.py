from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from lpr_app.models import UploadedImage, ProcessingLog


class UploadedImageRetryFieldsTest(TestCase):
    def test_retry_count_defaults_to_zero(self):
        img = UploadedImage.objects.create(
            filename='test.jpg',
            processing_status='pending',
        )
        self.assertEqual(img.retry_count, 0)

    def test_max_retries_defaults_from_settings(self):
        with override_settings(MAX_RETRIES=3):
            img = UploadedImage.objects.create(
                filename='test.jpg',
                processing_status='pending',
            )
            self.assertEqual(img.max_retries, 3)

    def test_max_retries_default_when_no_setting(self):
        img = UploadedImage.objects.create(
            filename='test.jpg',
            processing_status='pending',
        )
        self.assertEqual(img.max_retries, 2)

    def test_save_does_not_override_max_retries_on_update(self):
        img = UploadedImage.objects.create(
            filename='test.jpg',
            processing_status='pending',
        )
        img.max_retries = 5
        img.save()
        img.refresh_from_db()
        self.assertEqual(img.max_retries, 5)


class StuckImageDetectionTest(TestCase):
    def _create_image(self, status, minutes_ago, retry_count=0, max_retries=2, error_message=None):
        img = UploadedImage.objects.create(
            filename='test.jpg',
            processing_status=status,
            retry_count=retry_count,
            max_retries=max_retries,
            error_message=error_message,
        )
        UploadedImage.objects.filter(pk=img.pk).update(
            upload_timestamp=timezone.now() - timedelta(minutes=minutes_ago)
        )
        img.refresh_from_db()
        return img

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_recent_processing_image_not_retried(self, mock_service):
        self._create_image('processing', minutes_ago=2)
        call_command('retry_stuck_images')
        mock_service.process_uploaded_image.assert_not_called()

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_recent_pending_image_not_retried(self, mock_service):
        self._create_image('pending', minutes_ago=2)
        call_command('retry_stuck_images')
        mock_service.process_uploaded_image.assert_not_called()

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_stuck_processing_image_retried(self, mock_service):
        mock_service.process_uploaded_image.return_value = {'success': True}
        img = self._create_image('processing', minutes_ago=10)
        call_command('retry_stuck_images')
        mock_service.process_uploaded_image.assert_called_once()
        img.refresh_from_db()
        self.assertEqual(img.retry_count, 1)

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_stuck_pending_image_retried(self, mock_service):
        mock_service.process_uploaded_image.return_value = {'success': True}
        img = self._create_image('pending', minutes_ago=10)
        call_command('retry_stuck_images')
        mock_service.process_uploaded_image.assert_called_once()
        img.refresh_from_db()
        self.assertEqual(img.retry_count, 1)

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_completed_image_not_retried(self, mock_service):
        self._create_image('completed', minutes_ago=10)
        call_command('retry_stuck_images')
        mock_service.process_uploaded_image.assert_not_called()

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_failed_image_not_retried(self, mock_service):
        self._create_image('failed', minutes_ago=10)
        call_command('retry_stuck_images')
        mock_service.process_uploaded_image.assert_not_called()


class RetryExecutionTest(TestCase):
    def _create_image(self, status='processing', minutes_ago=10, retry_count=0, max_retries=2, error_message=None):
        img = UploadedImage.objects.create(
            filename='test.jpg',
            processing_status=status,
            retry_count=retry_count,
            max_retries=max_retries,
            error_message=error_message,
        )
        UploadedImage.objects.filter(pk=img.pk).update(
            upload_timestamp=timezone.now() - timedelta(minutes=minutes_ago)
        )
        img.refresh_from_db()
        return img

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_retry_increments_count(self, mock_service):
        mock_service.process_uploaded_image.return_value = {'success': True}
        img = self._create_image(retry_count=0)
        call_command('retry_stuck_images')
        img.refresh_from_db()
        self.assertEqual(img.retry_count, 1)

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_retry_clears_error_message(self, mock_service):
        mock_service.process_uploaded_image.return_value = {'success': True}
        img = self._create_image(error_message='old error')
        call_command('retry_stuck_images')
        img.refresh_from_db()
        self.assertIsNone(img.error_message)

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_retry_creates_started_log(self, mock_service):
        mock_service.process_uploaded_image.return_value = {'success': True}
        img = self._create_image()
        call_command('retry_stuck_images')
        log = ProcessingLog.objects.filter(uploaded_image=img, status='started').latest('timestamp')
        self.assertIn('Retry attempt 1/2', log.message)

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_retry_failure_sets_failed(self, mock_service):
        mock_service.process_uploaded_image.side_effect = Exception('API timeout')
        img = self._create_image()
        call_command('retry_stuck_images')
        img.refresh_from_db()
        self.assertEqual(img.processing_status, 'failed')
        self.assertEqual(img.error_message, 'API timeout')

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_retry_failure_creates_error_log(self, mock_service):
        mock_service.process_uploaded_image.side_effect = Exception('API timeout')
        img = self._create_image()
        call_command('retry_stuck_images')
        log = ProcessingLog.objects.filter(uploaded_image=img, status='error').latest('timestamp')
        self.assertIn('Retry attempt 1 failed', log.message)


class RetryExhaustionTest(TestCase):
    def _create_image(self, status='processing', minutes_ago=10, retry_count=2, max_retries=2, error_message='prev error'):
        img = UploadedImage.objects.create(
            filename='test.jpg',
            processing_status=status,
            retry_count=retry_count,
            max_retries=max_retries,
            error_message=error_message,
        )
        UploadedImage.objects.filter(pk=img.pk).update(
            upload_timestamp=timezone.now() - timedelta(minutes=minutes_ago)
        )
        img.refresh_from_db()
        return img

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_exhausted_image_marked_failed(self, mock_service):
        img = self._create_image(status='processing')
        call_command('retry_stuck_images')
        img.refresh_from_db()
        self.assertEqual(img.processing_status, 'failed')
        mock_service.process_uploaded_image.assert_not_called()

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_exhausted_error_message_includes_previous(self, mock_service):
        img = self._create_image(status='processing', error_message='network error')
        call_command('retry_stuck_images')
        img.refresh_from_db()
        self.assertIn('Processing failed after 2 attempts', img.error_message)
        self.assertIn('Last error: network error', img.error_message)

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_exhausted_creates_error_log(self, mock_service):
        img = self._create_image(status='processing')
        call_command('retry_stuck_images')
        log = ProcessingLog.objects.filter(uploaded_image=img, status='error').latest('timestamp')
        self.assertIn('Retries exhausted', log.message)

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_already_failed_exhausted_image_skipped(self, mock_service):
        img = self._create_image(status='failed')
        call_command('retry_stuck_images')
        img.refresh_from_db()
        self.assertEqual(img.processing_status, 'failed')
        self.assertEqual(ProcessingLog.objects.filter(uploaded_image=img).count(), 0)

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_exhausted_with_no_previous_error(self, mock_service):
        img = self._create_image(status='processing', error_message=None)
        call_command('retry_stuck_images')
        img.refresh_from_db()
        self.assertIn('Last error: unknown', img.error_message)


class CLIOptionOverrideTest(TestCase):
    def _create_image(self, status='processing', minutes_ago=10, retry_count=0):
        img = UploadedImage.objects.create(
            filename='test.jpg',
            processing_status=status,
            retry_count=retry_count,
        )
        UploadedImage.objects.filter(pk=img.pk).update(
            upload_timestamp=timezone.now() - timedelta(minutes=minutes_ago)
        )
        img.refresh_from_db()
        return img

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_timeout_override(self, mock_service):
        self._create_image('processing', minutes_ago=3)
        call_command('retry_stuck_images', timeout=2)
        mock_service.process_uploaded_image.assert_called_once()

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_max_retries_override(self, mock_service):
        img = self._create_image(retry_count=2)
        call_command('retry_stuck_images', max_retries=5)
        mock_service.process_uploaded_image.assert_called_once()
        img.refresh_from_db()
        self.assertEqual(img.retry_count, 3)


class BatchSizeTest(TestCase):
    def _create_image(self, status='processing', minutes_ago=10, retry_count=0):
        img = UploadedImage.objects.create(
            filename='test.jpg',
            processing_status=status,
            retry_count=retry_count,
        )
        UploadedImage.objects.filter(pk=img.pk).update(
            upload_timestamp=timezone.now() - timedelta(minutes=minutes_ago)
        )
        img.refresh_from_db()
        return img

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_batch_size_limits_processed_images(self, mock_service):
        mock_service.process_uploaded_image.return_value = {'success': True}
        for i in range(10):
            self._create_image()
        call_command('retry_stuck_images', batch_size=3)
        self.assertEqual(mock_service.process_uploaded_image.call_count, 3)

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_batch_size_from_settings(self, mock_service):
        mock_service.process_uploaded_image.return_value = {'success': True}
        for i in range(10):
            self._create_image()
        with override_settings(RETRY_BATCH_SIZE=2):
            call_command('retry_stuck_images')
        self.assertEqual(mock_service.process_uploaded_image.call_count, 2)

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_fewer_images_than_batch_size(self, mock_service):
        mock_service.process_uploaded_image.return_value = {'success': True}
        for i in range(2):
            self._create_image()
        call_command('retry_stuck_images', batch_size=10)
        self.assertEqual(mock_service.process_uploaded_image.call_count, 2)

    @patch('lpr_app.management.commands.retry_stuck_images.ImageProcessingService')
    def test_batch_applies_to_total_including_exhausted(self, mock_service):
        for i in range(3):
            self._create_image(retry_count=2)
        for i in range(2):
            self._create_image(retry_count=0)
        call_command('retry_stuck_images', batch_size=4)
        self.assertEqual(mock_service.process_uploaded_image.call_count, 2)
        exhausted_count = UploadedImage.objects.filter(
            processing_status='failed', error_message__contains='Processing failed after 2 attempts'
        ).count()
        self.assertEqual(exhausted_count, 2)
