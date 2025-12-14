"""
Prometheus metrics for the LPR application
"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from django.db import connection
from django.core.files.storage import default_storage
from django.conf import settings
import os
import time

# Application Performance Metrics
PROCESSING_DURATION = Histogram(
    'lpr_processing_duration_seconds',
    'Time spent processing images',
    ['status'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, float('inf')]
)

API_REQUEST_DURATION = Histogram(
    'lpr_api_request_duration_seconds',
    'Time spent calling external AI API',
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, float('inf')]
)

UPLOAD_TOTAL = Counter(
    'lpr_upload_total',
    'Total number of image uploads',
    ['status']
)

PROCESSING_TOTAL = Counter(
    'lpr_processing_total',
    'Total number of image processing operations',
    ['status']
)

# Business Metrics
PLATES_DETECTED_TOTAL = Counter(
    'lpr_plates_detected_total',
    'Total number of license plates detected'
)

OCR_TEXTS_DETECTED_TOTAL = Counter(
    'lpr_ocr_texts_detected_total',
    'Total number of OCR text extractions'
)

DETECTION_CONFIDENCE = Gauge(
    'lpr_detection_accuracy',
    'Average confidence score for detections'
)

IMAGES_IN_STORAGE = Gauge(
    'lpr_images_in_storage',
    'Total number of images in storage'
)

# System Health Metrics
DATABASE_CONNECTIONS_ACTIVE = Gauge(
    'lpr_database_connections_active',
    'Number of active database connections'
)

FILE_STORAGE_SIZE_BYTES = Gauge(
    'lpr_file_storage_size_bytes',
    'Total size of file storage in bytes'
)

API_HEALTH_STATUS = Gauge(
    'lpr_api_health_status',
    'Health status of external API (1=healthy, 0=unhealthy)'
)

PROCESSING_QUEUE_SIZE = Gauge(
    'lpr_processing_queue_size',
    'Number of images pending processing'
)

# Error Metrics
PROCESSING_ERRORS_TOTAL = Counter(
    'lpr_processing_errors_total',
    'Total number of processing errors',
    ['error_type']
)

API_ERRORS_TOTAL = Counter(
    'lpr_api_errors_total',
    'Total number of external API errors',
    ['error_type']
)

FILE_ERRORS_TOTAL = Counter(
    'lpr_file_errors_total',
    'Total number of file operation errors',
    ['error_type']
)


def update_system_metrics():
    """Update system-level metrics"""
    try:
        # Update database connections
        DATABASE_CONNECTIONS_ACTIVE.set(len(connection.queries))
        
        # Update file storage size (approximate)
        try:
            total_size = 0
            # Use MEDIA_ROOT setting instead of storage.location
            media_root = getattr(settings, 'MEDIA_ROOT', '/app/media')
            if os.path.exists(media_root):
                for root, dirs, files in os.walk(media_root):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if os.path.exists(file_path):
                            total_size += os.path.getsize(file_path)
            FILE_STORAGE_SIZE_BYTES.set(total_size)
        except Exception:
            FILE_STORAGE_SIZE_BYTES.set(0)
            
    except Exception:
        # Don't let metric updates break the application
        pass


def get_metrics_response():
    """Generate HTTP response with Prometheus metrics"""
    # Update dynamic metrics before generating response
    update_system_metrics()
    
    # Generate the metrics
    metrics_data = generate_latest()
    
    return metrics_data, CONTENT_TYPE_LATEST
