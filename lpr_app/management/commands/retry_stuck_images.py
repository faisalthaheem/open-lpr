import logging
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from lpr_app.models import UploadedImage, ProcessingLog
from lpr_app.services.image_processing_service import ImageProcessingService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Retry processing images stuck in processing or pending state'

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout',
            type=int,
            default=None,
            help='Override PROCESSING_TIMEOUT_MINUTES for this run',
        )
        parser.add_argument(
            '--max-retries',
            type=int,
            default=None,
            help='Override MAX_RETRIES for this run',
        )

    def handle(self, *args, **options):
        timeout_minutes = options['timeout'] or settings.PROCESSING_TIMEOUT_MINUTES
        max_retries = options['max_retries'] or settings.MAX_RETRIES

        cutoff = timezone.now() - timedelta(minutes=timeout_minutes)

        stuck_images = UploadedImage.objects.filter(
            processing_status__in=('processing', 'pending'),
            upload_timestamp__lt=cutoff,
        )

        retried = 0
        exhausted = 0

        for image in stuck_images:
            if image.retry_count < max_retries:
                image.retry_count += 1
                image.processing_status = 'pending'
                image.error_message = None
                image.save()

                ProcessingLog.objects.create(
                    uploaded_image=image,
                    status='started',
                    message=f'Retry attempt {image.retry_count}/{image.max_retries}',
                )

                try:
                    ImageProcessingService.process_uploaded_image(image)
                    retried += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'Retried image {image.id} ({image.filename}): attempt {image.retry_count}/{image.max_retries}'
                    ))
                except Exception as e:
                    image.processing_status = 'failed'
                    image.error_message = str(e)
                    image.save()

                    ProcessingLog.objects.create(
                        uploaded_image=image,
                        status='error',
                        message=f'Retry attempt {image.retry_count} failed: {str(e)}',
                    )

                    self.stderr.write(self.style.ERROR(
                        f'Retry failed for image {image.id} ({image.filename}): {e}'
                    ))
            else:
                if image.processing_status != 'failed':
                    prev_error = image.error_message or 'unknown'
                    image.processing_status = 'failed'
                    image.error_message = (
                        f'Processing failed after {image.retry_count} attempts. '
                        f'Last error: {prev_error}'
                    )
                    image.save()

                    ProcessingLog.objects.create(
                        uploaded_image=image,
                        status='error',
                        message=f'Retries exhausted after {image.retry_count} attempts. Last error: {prev_error}',
                    )

                    exhausted += 1
                    self.stdout.write(self.style.WARNING(
                        f'Exhausted retries for image {image.id} ({image.filename})'
                    ))

        self.stdout.write(self.style.SUCCESS(
            f'Done: {retried} retried, {exhausted} exhausted, '
            f'{stuck_images.count() - retried - exhausted} already failed'
        ))
