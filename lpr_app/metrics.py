"""
Prometheus metrics for LPR application with file-based persistence
"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST, REGISTRY, CollectorRegistry
from django.db import connection
from django.core.files.storage import default_storage
from django.conf import settings
import os
import time
import json
import logging
import threading
import atexit

logger = logging.getLogger(__name__)

# Create a custom registry for our metrics to ensure persistence
REGISTRY = CollectorRegistry()

# File-based persistence
METRICS_FILE_PATH = getattr(settings, 'METRICS_FILE_PATH', '/app/metrics/metrics_state.json')
_persistence_lock = threading.Lock()

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


def load_metrics_from_file():
    """Load metrics values from persistent storage file"""
    try:
        if os.path.exists(METRICS_FILE_PATH):
            with open(METRICS_FILE_PATH, 'r') as f:
                data = json.load(f)
                logger.info(f"Loaded metrics from {METRICS_FILE_PATH}: {data}")
                return data
        else:
            logger.info(f"No metrics file found at {METRICS_FILE_PATH}, starting fresh")
            return {}
    except Exception as e:
        logger.error(f"Error loading metrics from file: {e}")
        return {}


def save_metrics_to_file():
    """Save current metrics values to persistent storage file"""
    try:
        with _persistence_lock:
            # Get current metric values
            metrics_data = {
                'upload_total_success': UPLOAD_TOTAL.labels(status='success')._value._value,
                'upload_total_failed': UPLOAD_TOTAL.labels(status='failed')._value._value,
                'upload_total_error': UPLOAD_TOTAL.labels(status='error')._value._value,
                'processing_total_completed': PROCESSING_TOTAL.labels(status='completed')._value._value,
                'processing_total_failed': PROCESSING_TOTAL.labels(status='failed')._value._value,
                'processing_total_error': PROCESSING_TOTAL.labels(status='error')._value._value,
                'plates_detected_total': PLATES_DETECTED_TOTAL._value._value,
                'ocr_texts_detected_total': OCR_TEXTS_DETECTED_TOTAL._value._value,
                'detection_accuracy': DETECTION_CONFIDENCE._value._value,
                'images_in_storage': IMAGES_IN_STORAGE._value._value,
                'api_health_status': API_HEALTH_STATUS._value._value,
                'processing_queue_size': PROCESSING_QUEUE_SIZE._value._value,
                'file_storage_size_bytes': FILE_STORAGE_SIZE_BYTES._value._value,
            }
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(METRICS_FILE_PATH), exist_ok=True)
            
            # Save to file
            with open(METRICS_FILE_PATH, 'w') as f:
                json.dump(metrics_data, f, indent=2)
            
            logger.info(f"Saved metrics to {METRICS_FILE_PATH}")
            
    except Exception as e:
        logger.error(f"Error saving metrics to file: {e}")


def initialize_persistent_metrics():
    """Initialize metrics with persistent values from database and file"""
    try:
        from .models import UploadedImage, ProcessingLog
        
        # Load any saved metrics values
        saved_metrics = load_metrics_from_file()
        
        # Initialize counters with existing data from database (prioritize database over file)
        total_images = UploadedImage.objects.count()
        completed_images = UploadedImage.objects.filter(processing_status='completed').count()
        failed_images = UploadedImage.objects.filter(processing_status='failed').count()
        
        # For counters, prioritize database counts over saved file values
        # Only use file values if database counts are 0 (fresh start)
        upload_success = completed_images if completed_images > 0 else saved_metrics.get('upload_total_success', 0)
        upload_failed = failed_images if failed_images > 0 else saved_metrics.get('upload_total_failed', 0)
        upload_error = saved_metrics.get('upload_total_error', 0)
        processing_completed = completed_images if completed_images > 0 else saved_metrics.get('processing_total_completed', 0)
        processing_failed = failed_images if failed_images > 0 else saved_metrics.get('processing_total_failed', 0)
        processing_error = saved_metrics.get('processing_total_error', 0)
        
        # For business metrics, calculate from database first, fallback to file
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
                logger.warning(f"Error processing detection results for image {image.pk}: {e}")
                continue
        
        # Use calculated values if available, otherwise fallback to saved file values
        plates_detected = total_plates if total_plates > 0 else saved_metrics.get('plates_detected_total', 0)
        ocr_texts_detected = total_ocr_texts if total_ocr_texts > 0 else saved_metrics.get('ocr_texts_detected_total', 0)
        
        # Set counter values directly (bypassing increment for initialization)
        UPLOAD_TOTAL.labels(status='success')._value._value = float(upload_success)
        UPLOAD_TOTAL.labels(status='failed')._value._value = float(upload_failed)
        UPLOAD_TOTAL.labels(status='error')._value._value = float(upload_error)
        PROCESSING_TOTAL.labels(status='completed')._value._value = float(processing_completed)
        PROCESSING_TOTAL.labels(status='failed')._value._value = float(processing_failed)
        PROCESSING_TOTAL.labels(status='error')._value._value = float(processing_error)
        PLATES_DETECTED_TOTAL._value._value = float(plates_detected)
        OCR_TEXTS_DETECTED_TOTAL._value._value = float(ocr_texts_detected)
        
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
                logger.warning(f"Error processing detection results for image {image.pk}: {e}")
                continue
        
        # Restore gauge values from file if available
        detection_accuracy = saved_metrics.get('detection_accuracy', 0)
        if total_confidence_count > 0 and detection_accuracy == 0:
            avg_confidence = total_confidence_sum / total_confidence_count
            DETECTION_CONFIDENCE.set(avg_confidence)
        elif detection_accuracy > 0:
            DETECTION_CONFIDENCE.set(detection_accuracy)
        
        # Set gauge values
        images_in_storage = saved_metrics.get('images_in_storage', total_images)
        IMAGES_IN_STORAGE.set(images_in_storage)
        
        api_health_status = saved_metrics.get('api_health_status', 0)
        API_HEALTH_STATUS.set(api_health_status)
        
        processing_queue_size = saved_metrics.get('processing_queue_size', 0)
        PROCESSING_QUEUE_SIZE.set(processing_queue_size)
        
        file_storage_size = saved_metrics.get('file_storage_size_bytes', 0)
        FILE_STORAGE_SIZE_BYTES.set(file_storage_size)
        
        logger.info(f"Initialized metrics with {total_images} total images, {completed_images} completed, {failed_images} failed")
        logger.info(f"Restored counters: uploads={upload_success}, processing={processing_completed}, plates={plates_detected}")
        
    except Exception as e:
        logger.error(f"Error initializing persistent metrics: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


def update_system_metrics():
    """Update system-level metrics and save to file"""
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
            
        # Save current state to file
        save_metrics_to_file()
            
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


# Register save function to be called on exit
atexit.register(save_metrics_to_file)
