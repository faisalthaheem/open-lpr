"""
Metrics helper utilities for LPR application.

This module contains centralized metrics tracking and calculation functions.
"""

import logging
import time
from typing import Dict, Any, Optional, List

from ..metrics import (
    PROCESSING_DURATION, API_REQUEST_DURATION, UPLOAD_TOTAL, PROCESSING_TOTAL,
    PLATES_DETECTED_TOTAL, OCR_TEXTS_DETECTED_TOTAL, DETECTION_CONFIDENCE,
    IMAGES_IN_STORAGE, PROCESSING_QUEUE_SIZE, PROCESSING_ERRORS_TOTAL,
    API_ERRORS_TOTAL, FILE_ERRORS_TOTAL, API_HEALTH_STATUS, CANARY_REQUESTS_TOTAL,
    CANARY_PROCESSING_DURATION, save_metrics_to_file
)

logger = logging.getLogger(__name__)


class MetricsHelper:
    """Utility class for centralized metrics operations."""
    
    @staticmethod
    def record_upload_attempt(status: str) -> None:
        """
        Record an upload attempt metric.
        
        Args:
            status: Status of the upload ('success', 'failed', 'error')
        """
        UPLOAD_TOTAL.labels(status=status).inc()
    
    @staticmethod
    def record_processing_attempt(status: str) -> None:
        """
        Record a processing attempt metric.
        
        Args:
            status: Status of the processing ('completed', 'failed', 'error')
        """
        PROCESSING_TOTAL.labels(status=status).inc()
    
    @staticmethod
    def record_processing_error(error_type: str) -> None:
        """
        Record a processing error metric.
        
        Args:
            error_type: Type of processing error
        """
        PROCESSING_ERRORS_TOTAL.labels(error_type=error_type).inc()
    
    @staticmethod
    def record_api_error() -> None:
        """Record an API error metric."""
        API_ERRORS_TOTAL.inc()
    
    @staticmethod
    def record_file_error() -> None:
        """Record a file error metric."""
        FILE_ERRORS_TOTAL.inc()
    
    @staticmethod
    def record_processing_duration(status: str, duration: float) -> None:
        """
        Record processing duration metric.
        
        Args:
            status: Status of processing
            duration: Duration in seconds
        """
        PROCESSING_DURATION.labels(status=status).observe(duration)
    
    @staticmethod
    def record_api_request_duration(duration: float) -> None:
        """
        Record API request duration metric.
        
        Args:
            duration: Duration in seconds
        """
        API_REQUEST_DURATION.observe(duration)
    
    @staticmethod
    def update_detection_metrics(uploaded_image) -> None:
        """
        Update detection-related metrics from an uploaded image.
        
        Args:
            uploaded_image: UploadedImage instance with processing results
        """
        try:
            # Update plate and OCR counts
            plate_count = uploaded_image.get_plate_count()
            ocr_count = uploaded_image.get_total_ocr_count()
            
            PLATES_DETECTED_TOTAL.inc(plate_count)
            OCR_TEXTS_DETECTED_TOTAL.inc(ocr_count)
            
            # Update confidence gauge
            detection_results = uploaded_image.get_detection_results()
            if detection_results and 'detections' in detection_results:
                confidences = []
                for detection in detection_results['detections']:
                    if 'plate' in detection and 'confidence' in detection['plate']:
                        confidences.append(detection['plate']['confidence'])
                    if 'ocr' in detection:
                        for ocr_item in detection['ocr']:
                            if isinstance(ocr_item, dict) and 'confidence' in ocr_item:
                                confidences.append(ocr_item['confidence'])
                
                if confidences:
                    avg_confidence = sum(confidences) / len(confidences)
                    DETECTION_CONFIDENCE.set(avg_confidence)
                    
        except Exception as e:
            logger.error(f"Error updating detection metrics: {e}")
    
    @staticmethod
    def update_storage_metrics() -> None:
        """Update storage-related metrics."""
        try:
            from ..models import UploadedImage
            
            # Update total images in storage
            total_images = UploadedImage.objects.count()
            IMAGES_IN_STORAGE.set(total_images)
            
            # Update processing queue size
            pending_count = UploadedImage.objects.filter(processing_status='pending').count()
            PROCESSING_QUEUE_SIZE.set(pending_count)
            
        except Exception as e:
            logger.error(f"Error updating storage metrics: {e}")
    
    @staticmethod
    def update_api_health_status(is_healthy: bool) -> None:
        """
        Update API health status metric.
        
        Args:
            is_healthy: Whether the API is healthy
        """
        API_HEALTH_STATUS.set(1 if is_healthy else 0)
    
    @staticmethod
    def record_canary_request(status: str) -> None:
        """
        Record a canary request metric.
        
        Args:
            status: Status of the canary request ('success', 'failed', 'error')
        """
        CANARY_REQUESTS_TOTAL.labels(status=status).inc()
    
    @staticmethod
    def record_canary_processing_duration(duration: float) -> None:
        """
        Record canary processing duration metric.
        
        Args:
            duration: Duration in seconds
        """
        CANARY_PROCESSING_DURATION.observe(duration)
    
    @staticmethod
    def save_metrics() -> None:
        """Save metrics to file immediately."""
        try:
            save_metrics_to_file()
        except Exception as e:
            logger.error(f"Error saving metrics: {e}")
    
    @staticmethod
    def get_metrics_summary() -> Dict[str, Any]:
        """
        Get a summary of current metrics values.
        
        Returns:
            Dictionary with metrics summary
        """
        try:
            from ..models import UploadedImage
            
            # Get basic counts
            total_images = UploadedImage.objects.count()
            completed_images = UploadedImage.objects.filter(processing_status='completed').count()
            pending_images = UploadedImage.objects.filter(processing_status='pending').count()
            failed_images = UploadedImage.objects.filter(processing_status='failed').count()
            
            return {
                'total_images': total_images,
                'completed_images': completed_images,
                'pending_images': pending_images,
                'failed_images': failed_images,
                'completion_rate': (completed_images / total_images * 100) if total_images > 0 else 0,
                'storage_usage': IMAGES_IN_STORAGE._value._value,
                'queue_size': PROCESSING_QUEUE_SIZE._value._value,
            }
            
        except Exception as e:
            logger.error(f"Error getting metrics summary: {e}")
            return {}


class PerformanceTracker:
    """Utility class for tracking performance metrics."""
    
    def __init__(self, operation_name: str):
        """
        Initialize performance tracker.
        
        Args:
            operation_name: Name of the operation being tracked
        """
        self.operation_name = operation_name
        self.start_time = time.time()
    
    def record_success(self) -> float:
        """
        Record successful completion and return duration.
        
        Returns:
            Duration in seconds
        """
        duration = time.time() - self.start_time
        logger.info(f"Operation '{self.operation_name}' completed successfully in {duration:.3f}s")
        return duration
    
    def record_error(self, error_message: Optional[str] = None) -> float:
        """
        Record error and return duration.
        
        Args:
            error_message: Optional error message
            
        Returns:
            Duration in seconds
        """
        duration = time.time() - self.start_time
        logger.error(f"Operation '{self.operation_name}' failed after {duration:.3f}s: {error_message}")
        return duration
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        duration = time.time() - self.start_time
        if exc_type is None:
            self.record_success()
        else:
            self.record_error(str(exc_val))
        
        # Record appropriate metrics based on operation
        if self.operation_name == 'processing':
            status = 'error' if exc_type else 'completed'
            MetricsHelper.record_processing_duration(status, duration)
        elif self.operation_name == 'api_request':
            MetricsHelper.record_api_request_duration(duration)
        elif self.operation_name == 'canary_processing':
            if not exc_type:
                MetricsHelper.record_canary_processing_duration(duration)
