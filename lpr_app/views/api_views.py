"""
API views for LPR application.

This module contains views for handling API requests and responses
including OCR processing, health checks, and metrics.
"""

import logging
import time
from datetime import datetime

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..services.api_service import ApiService
from ..services.image_processing_service import ImageProcessingService
from ..services.qwen_client import get_qwen_client
from ..metrics import get_metrics_response
from ..utils.metrics_helpers import MetricsHelper, PerformanceTracker
from ..utils.response_helpers import ResponseHelper

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def api_ocr_upload(request):
    """
    REST API endpoint to upload an image and get OCR results synchronously.
    
    Expected request:
    - Method: POST
    - Content-Type: multipart/form-data
    - Form field: image (file)
    - Optional form field: save_image (boolean, default: true)
    
    Canary requests can use save_image=false to skip saving processed images.
    Canary requests must provide a configurable header for authentication.
    
    Returns:
    - JSON response with OCR results or error information
    """
    logger.info("DEBUG: api_ocr_upload function called!")
    
    # Detect if this is a canary request
    is_canary = ApiService.detect_canary_request(request)
    
    # Validate API request
    is_valid, error_response = ApiService.validate_api_request(request)
    if not is_valid:
        MetricsHelper.record_api_error()
        return error_response
    
    uploaded_file = request.FILES['image']
    
    # Determine save_image setting
    save_image = ApiService.determine_save_image_setting(request, is_canary)
    
    start_time = time.time()
    
    with PerformanceTracker('api_request') as tracker:
        try:
            # Create upload record
            uploaded_image = ApiService.create_upload_image_record(
                uploaded_file, save_image, is_canary
            )
            
            logger.info(f"DEBUG: About to call process_uploaded_image with save_image={save_image}, is_canary={is_canary}")
            
            # Process the image
            result = ImageProcessingService.process_uploaded_image(uploaded_image, save_image=save_image)
            
            logger.info(f"DEBUG: process_uploaded_image returned: {result}")
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Update canary-specific metrics
            if is_canary:
                MetricsHelper.record_canary_request(
                    'success' if result['success'] else 'failed'
                )
                MetricsHelper.record_canary_processing_duration(processing_time_ms / 1000.0)
            
            if result['success']:
                # Update detection metrics if image was saved
                if save_image and uploaded_image.pk:
                    MetricsHelper.update_detection_metrics(uploaded_image)
                
                MetricsHelper.record_upload_attempt('success')
                MetricsHelper.record_processing_attempt('completed')
                MetricsHelper.update_storage_metrics()
                MetricsHelper.save_metrics()
                
                return ApiService.format_success_response(
                    result, uploaded_image, processing_time_ms, is_canary, save_image
                )
            else:
                MetricsHelper.record_upload_attempt('failed')
                MetricsHelper.record_processing_attempt('failed')
                MetricsHelper.record_processing_error('processing_failed')
                
                if is_canary:
                    MetricsHelper.record_canary_request('failed')
                
                return ApiService.format_error_response(
                    error_message=result.get('error', 'Unknown processing error'),
                    error_code='PROCESSING_FAILED',
                    image_id=uploaded_image.id,
                    processing_time_ms=processing_time_ms,
                    is_canary=is_canary,
                    status_code=500
                )
                
        except Exception as e:
            logger.error(f"Error in api_ocr_upload: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Update error metrics
            MetricsHelper.record_upload_attempt('error')
            MetricsHelper.record_api_error()
            
            if is_canary:
                MetricsHelper.record_canary_request('error')
            
            return ApiService.format_error_response(
                error_message='Internal server error during image processing',
                error_code='INTERNAL_ERROR',
                processing_time_ms=int((time.time() - start_time) * 1000),
                is_canary=is_canary,
                status_code=500
            )


def api_health_check(request):
    """
    Health check endpoint for the API.
    """
    try:
        with PerformanceTracker('api_request') as tracker:
            # Check Qwen3-VL API
            api_start_time = time.time()
            client = get_qwen_client()
            api_healthy = client.health_check()
            api_duration = time.time() - api_start_time
            
            # Update API health status metric
            MetricsHelper.update_api_health_status(api_healthy)
            MetricsHelper.record_api_request_duration(api_duration)
            
            # Check database connection
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                db_healthy = result is not None and result[0] == 1
            
            status_code = 200 if api_healthy and db_healthy else 503
            
            return JsonResponse({
                'status': 'healthy' if status_code == 200 else 'unhealthy',
                'api_healthy': api_healthy,
                'database_healthy': db_healthy,
                'timestamp': datetime.now().isoformat()
            }, status=status_code)
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        MetricsHelper.update_api_health_status(False)
        MetricsHelper.record_api_error()
        
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, status=503)


def metrics_view(request):
    """
    Prometheus metrics endpoint.
    """
    try:
        metrics_data, content_type = get_metrics_response()
        return JsonResponse(metrics_data, content_type=content_type)
    except Exception as e:
        logger.error(f"Error generating metrics: {str(e)}")
        MetricsHelper.record_api_error()
        return JsonResponse("Error generating metrics", status=500, safe=False)
