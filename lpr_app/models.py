import os
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def _guid_filename(filename):
    return f"{uuid.uuid4().hex[:8]}_{filename}"


def upload_to_uploads(instance, filename):
    # Bucketed with an aware clock so the path date agrees with the stored
    # upload_timestamp, regardless of the server's local timezone.
    now = timezone.now()
    return f"uploads/{now.year}/{now.month:02d}/{now.day:02d}/{_guid_filename(filename)}"


def upload_to_processed(instance, filename):
    now = timezone.now()
    return f"processed/{now.year}/{now.month:02d}/{now.day:02d}/{_guid_filename(filename)}"


class UploadedImage(models.Model):
    """Model to track uploaded images and their processing results"""

    id = models.AutoField(primary_key=True)
    original_image = models.ImageField(upload_to=upload_to_uploads, verbose_name="Original Image")
    processed_image = models.ImageField(
        upload_to=upload_to_processed, null=True, blank=True, verbose_name="Processed Image"
    )
    upload_timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Upload Time")
    processing_timestamp = models.DateTimeField(null=True, blank=True, verbose_name="Processing Time")
    api_response = models.JSONField(null=True, blank=True, verbose_name="API Response")
    filename = models.CharField(max_length=255, verbose_name="Filename")
    file_size = models.PositiveIntegerField(null=True, blank=True, verbose_name="File Size (bytes)")
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        default="pending",
        verbose_name="Processing Status",
    )
    error_message = models.TextField(null=True, blank=True, verbose_name="Error Message")
    retry_count = models.PositiveIntegerField(default=0, verbose_name="Retry Count")
    max_retries = models.PositiveIntegerField(default=2, verbose_name="Max Retries")

    class Meta:
        verbose_name = "Uploaded Image"
        verbose_name_plural = "Uploaded Images"
        ordering = ["-upload_timestamp"]

    def __str__(self):
        return f"{self.filename} - {self.upload_timestamp.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        if not self.pk:
            if self.original_image:
                self.filename = os.path.basename(self.original_image.name)
                if hasattr(self.original_image, "size"):
                    self.file_size = self.original_image.size
            self.max_retries = getattr(settings, "MAX_RETRIES", 2)

        super().save(*args, **kwargs)

    @property
    def original_image_url(self):
        """Get URL for original image"""
        if self.original_image:
            return self.original_image.url
        return None

    @property
    def processed_image_url(self):
        """Get URL for processed image"""
        if self.processed_image:
            return self.processed_image.url
        return None

    @property
    def file_size_mb(self):
        """Get file size in MB"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return None

    def get_detection_results(self):
        """Parse and return detection results from API response"""
        if not self.api_response:
            return None

        import json

        try:
            # Parse the JSON response to extract detection results
            if isinstance(self.api_response, str):
                response_data = json.loads(self.api_response)
            else:
                response_data = self.api_response

            return response_data
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def get_plate_count(self):
        """Get the number of license plates detected"""
        detections = self._detections()
        return len(detections) if detections else 0

    def get_total_ocr_count(self):
        """Get the total number of OCR detections"""
        detections = self._detections()
        if not detections:
            return 0
        return sum(len(d.get("ocr", [])) for d in detections)

    def get_first_ocr_text(self):
        """Get the first OCR text from the detection results"""
        detections = self._detections()
        for detection in detections or []:
            ocr_items = detection.get("ocr") or []
            if ocr_items:
                return ocr_items[0].get("text")
        return None

    def _detections(self):
        """
        Return the stored detections as a list.

        ``detections`` is always written as a JSON array by the current pipeline.
        A non-array value is not a supported shape, so it yields no detections
        rather than raising or producing a misleading count.
        """
        results = self.get_detection_results()
        if not isinstance(results, dict):
            return None
        detections = results.get("detections")
        return detections if isinstance(detections, list) else None


class ProcessingLog(models.Model):
    """Model to log processing attempts and errors"""

    uploaded_image = models.ForeignKey(UploadedImage, on_delete=models.CASCADE, related_name="processing_logs")
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("started", "Started"),
            ("api_call", "API Call"),
            ("success", "Success"),
            ("error", "Error"),
        ],
    )
    message = models.TextField()
    duration_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Processing Log"
        verbose_name_plural = "Processing Logs"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.uploaded_image.filename} - {self.status} - {self.timestamp}"
