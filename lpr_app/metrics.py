"""
Prometheus metrics for LPR application
"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST, REGISTRY, CollectorRegistry
from django.db import connection
from django.core.files.storage import default_storage
from django.conf import settings
import os
import time
import logging

logger = logging.getLogger(__name__)

# Create a custom registry for our metrics to ensure persistence
REGISTRY = CollectorRegistry()

# Application Performance Metrics
PROCESSING_DURATION = Histogram(
    'lpr_processing_duration_seconds',
    'Time spent processing images',
    ['status'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, float('inf')],
    registry=REGISTRY
)

API_REQUEST_DURATION = Histogram(
    'lpr_api_request_duration_seconds',
    'Time spent calling external AI API',
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, float('inf')],
    registry=REGISTRY
)

UPLOAD_TOTAL = Counter(
    'lpr_upload_total',
    'Total number of image uploads',
    ['status'],
    registry=REGISTRY
)

PROCESSING_TOTAL = Counter(
    'lpr_processing_total',
    'Total number of image processing operations',
    ['status'],
    registry=REGISTRY
)

# Business Metrics
PLATES_DETECTED_TOTAL = Counter(
    'lpr_plates_detected_total',
    'Total number of license plates detected',
    registry=REGISTRY
)

OCR_TEXTS_DETECTED_TOTAL = Counter(
    'lpr_ocr_texts_detected_total',
    'Total number of OCR text extractions',
    registry=REGISTRY
)

DETECTION_CONFIDENCE = Gauge(
    'lpr_detection_accuracy',
    'Average confidence score for detections',
    registry=REGISTRY
)

IMAGES_IN_STORAGE = Gauge(
    'lpr_images_in_storage',
    'Total number of images in storage',
    registry=REGISTRY
)

# System Health Metrics
DATABASE_CONNECTIONS_ACTIVE = Gauge(
    'lpr_database_connections_active',
    'Number of active database connections',
    registry=REGISTRY
)

FILE_STORAGE_SIZE_BYTES = Gauge(
    'lpr_file_storage_size_bytes',
    'Total size of file storage in bytes',
    registry=REGISTRY
)

API_HEALTH_STATUS = Gauge(
    'lpr_api_health_status',
    'Health status of external API (1=healthy, 0=unhealthy)',
    registry=REGISTRY
)

PROCESSING_QUEUE_SIZE = Gauge(
    'lpr_processing_queue_size',
    'Number of images pending processing',
    registry=REGISTRY
)

# Error Metrics
PROCESSING_ERRORS_TOTAL = Counter(
    'lpr_processing_errors_total',
    'Total number of processing errors',
    ['error_type'],
    registry=REGISTRY
)

API_ERRORS_TOTAL = Counter(
    'lpr_api_errors_total',
    'Total number of external API errors',
    ['error_type'],
    registry=REGISTRY
)

FILE_ERRORS_TOTAL = Counter(
    'lpr_file_errors_total',
    'Total number of file operation errors',
    ['error_type'],
    registry=REGISTRY
)


def initialize_persistent_metrics():
    """Initialize metrics with persistent values from database"""
    try:
        from .models import UploadedImage, ProcessingLog
        
        # Initialize counters with existing data
        total_images = UploadedImage.objects.count()
        completed_images = UploadedImage.objects.filter(processing_status='completed').count()
        failed_images = UploadedImage.objects.filter(processing_status='failed').count()
        
        # Initialize counters with historical values from database to ensure consistency
        # This prevents metrics from resetting to 0 when workers restart
        
        # Initialize processing counters
        if completed_images > 0:
            for _ in range(completed_images):
                PROCESSING_TOTAL.labels(status='completed').inc()
        if failed_images > 0:
            for _ in range(failed_images):
                PROCESSING_TOTAL.labels(status='failed').inc()
        
        # Initialize upload counters
        success_uploads = UploadedImage.objects.filter(processing_status__in=['completed', 'processing']).count()
        if success_uploads > 0:
            for _ in range(success_uploads):
                UPLOAD_TOTAL.labels(status='success').inc()
        if failed_images > 0:
            for _ in range(failed_images):
                UPLOAD_TOTAL.labels(status='failed').inc()
        
        # Initialize business metrics from database
        total_plates = 0
        total_ocr_texts = 0
        total_confidence_sum = 0
        total_confidence_count = 0
        
        for image in UploadedImage.objects.filter(processing_status='completed'):
            try:
                results = image.get_detection_results()
                if results and 'detections' in results:
                    for detection in results['detections']:
                        if 'plate' in detection and 'confidence' in detection['plate']:
                            total_plates += 1
                            total_confidence_sum += detection['plate']['confidence']
                            total_confidence_count += 1
                        if 'ocr' in detection:
                            for ocr_item in detection['ocr']:
                                if isinstance(ocr_item, dict) and 'confidence' in ocr_item:
                                    total_ocr_texts += 1
                                    total_confidence_sum += ocr_item['confidence']
                                    total_confidence_count += 1
            except Exception as e:
                logger.warning(f"Error processing detection results for image {image.id}: {e}")
                continue
        
        # Set initial values for counters
        if total_plates > 0:
            for _ in range(total_plates):
                PLATES_DETECTED_TOTAL.inc()
        if total_ocr_texts > 0:
            for _ in range(total_ocr_texts):
                OCR_TEXTS_DETECTED_TOTAL.inc()
        
        # Set average confidence
        if total_confidence_count > 0:
            avg_confidence = total_confidence_sum / total_confidence_count
            DETECTION_CONFIDENCE.set(avg_confidence)
        
        # Set gauge values
        IMAGES_IN_STORAGE.set(total_images)
        
        # Calculate queue size
        pending_count = UploadedImage.objects.filter(processing_status='pending').count()
        PROCESSING_QUEUE_SIZE.set(pending_count)
        
        logger.info(f"Initialized metrics with {total_images} total images, {completed_images} completed, {failed_images} failed")
        logger.info(f"Initialized business metrics: {total_plates} plates, {total_ocr_texts} OCR texts")
        
    except Exception as e:
        logger.error(f"Error initializing persistent metrics: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


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
    
    # Generate metrics using our custom registry
    metrics_data = generate_latest(REGISTRY)
    
    return metrics_data, CONTENT_TYPE_LATEST
