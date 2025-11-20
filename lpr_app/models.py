import os
from django.db import models
from django.core.files.storage import default_storage
from django.conf import settings


def upload_to_uploads(instance, filename):
    """Generate upload path for original images"""
    # Create directory structure: uploads/YYYY/MM/DD/
    from datetime import datetime
    now = datetime.now()
    return f'uploads/{now.year}/{now.month:02d}/{now.day:02d}/{filename}'


def upload_to_processed(instance, filename):
    """Generate upload path for processed images"""
    # Create directory structure: processed/YYYY/MM/DD/
    from datetime import datetime
    now = datetime.now()
    return f'processed/{now.year}/{now.month:02d}/{now.day:02d}/{filename}'


class UploadedImage(models.Model):
    """Model to track uploaded images and their processing results"""
    
    original_image = models.ImageField(
        upload_to=upload_to_uploads,
        verbose_name="Original Image"
    )
    processed_image = models.ImageField(
        upload_to=upload_to_processed,
        null=True,
        blank=True,
        verbose_name="Processed Image"
    )
    upload_timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Upload Time"
    )
    processing_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Processing Time"
    )
    api_response = models.JSONField(
        null=True,
        blank=True,
        verbose_name="API Response"
    )
    filename = models.CharField(
        max_length=255,
        verbose_name="Filename"
    )
    file_size = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="File Size (bytes)"
    )
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending',
        verbose_name="Processing Status"
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        verbose_name="Error Message"
    )
    
    class Meta:
        verbose_name = "Uploaded Image"
        verbose_name_plural = "Uploaded Images"
        ordering = ['-upload_timestamp']
    
    def __str__(self):
        return f"{self.filename} - {self.upload_timestamp.strftime('%Y-%m-%d %H:%M')}"
    
    def save(self, *args, **kwargs):
        # Set filename and file size on first save
        if not self.pk and self.original_image:
            self.filename = os.path.basename(self.original_image.name)
            # Get file size
            if self.original_image and hasattr(self.original_image, 'size'):
                self.file_size = self.original_image.size
        
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
        
        try:
            # Parse the JSON response to extract detection results
            import json
            if isinstance(self.api_response, str):
                response_data = json.loads(self.api_response)
            else:
                response_data = self.api_response
            
            return response_data
        except (json.JSONDecodeError, KeyError, TypeError):
            return None
    
    def get_plate_count(self):
        """Get the number of license plates detected"""
        results = self.get_detection_results()
        if results and 'detections' in results:
            return len(results['detections'])
        return 0
    
    def get_total_ocr_count(self):
        """Get the total number of OCR detections"""
        results = self.get_detection_results()
        if results and 'detections' in results:
            total = 0
            detections = results['detections']
            # Handle both list and dictionary formats
            if isinstance(detections, list):
                # New API format: detections is a list
                for detection in detections:
                    if 'ocr' in detection:
                        total += len(detection['ocr'])
            elif isinstance(detections, dict):
                # Old API format: detections is a dictionary
                for detection in detections.values():
                    if 'ocr' in detection:
                        total += len(detection['ocr'])
            return total
        return 0


class ProcessingLog(models.Model):
    """Model to log processing attempts and errors"""
    
    uploaded_image = models.ForeignKey(
        UploadedImage,
        on_delete=models.CASCADE,
        related_name='processing_logs'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('started', 'Started'),
            ('api_call', 'API Call'),
            ('success', 'Success'),
            ('error', 'Error'),
        ]
    )
    message = models.TextField()
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Processing Log"
        verbose_name_plural = "Processing Logs"
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.uploaded_image.filename} - {self.status} - {self.timestamp}"