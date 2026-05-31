"""
API views for LPR application.

This module contains views for handling API requests and responses
including OCR processing, health checks, metrics, and image listing.
"""

import logging
import time
from datetime import datetime

from django.conf import settings as django_settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q

from ..models import UploadedImage
from ..services.api_service import ApiService
from ..services.image_processing_service import ImageProcessingService
from ..services.file_service import FileService
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
                
                response = ApiService.format_success_response(
                    result, uploaded_image, processing_time_ms, is_canary, save_image
                )
                logger.info(f"DEBUG: Returning success response of type: {type(response)}")
                return response
            else:
                MetricsHelper.record_upload_attempt('failed')
                MetricsHelper.record_processing_attempt('failed')
                MetricsHelper.record_processing_error('processing_failed')
                
                if is_canary:
                    MetricsHelper.record_canary_request('failed')
                    MetricsHelper.record_canary_processing_duration(processing_time_ms / 1000.0)
                    if not save_image:
                        ImageProcessingService._handle_canary_cleanup(
                            uploaded_image, save_image=False, comparison_path=None
                        )
                
                response_image_id = None if is_canary and not save_image else uploaded_image.id
                response = ApiService.format_error_response(
                    error_message=result.get('error', 'Unknown processing error'),
                    error_code='PROCESSING_FAILED',
                    image_id=response_image_id,
                    processing_time_ms=processing_time_ms,
                    is_canary=is_canary,
                    status_code=500
                )
                logger.info(f"DEBUG: Returning error response of type: {type(response)}")
                return response
                
        except Exception as e:
            logger.error(f"Error in api_ocr_upload: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Update error metrics
            MetricsHelper.record_upload_attempt('error')
            MetricsHelper.record_api_error()
            
            exception_processing_time_ms = int((time.time() - start_time) * 1000)
            
            if is_canary:
                MetricsHelper.record_canary_request('error')
                MetricsHelper.record_canary_processing_duration(exception_processing_time_ms / 1000.0)
                if not save_image and 'uploaded_image' in locals() and uploaded_image and uploaded_image.pk:
                    ImageProcessingService._handle_canary_cleanup(
                        uploaded_image, save_image=False, comparison_path=None
                    )
            
            return ApiService.format_error_response(
                error_message='Internal server error during image processing',
                error_code='INTERNAL_ERROR',
                processing_time_ms=exception_processing_time_ms,
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
        from django.http import HttpResponse
        return HttpResponse(metrics_data, content_type=content_type)
    except Exception as e:
        logger.error(f"Error generating metrics: {str(e)}")
        MetricsHelper.record_api_error()
        from django.http import HttpResponse
        return HttpResponse("Error generating metrics", status=500, content_type="text/plain")


def _serialize_image_summary(img):
    return {
        'id': img.id,
        'filename': img.filename,
        'processing_status': img.processing_status,
        'upload_timestamp': img.upload_timestamp.isoformat() if img.upload_timestamp else None,
        'processing_timestamp': img.processing_timestamp.isoformat() if img.processing_timestamp else None,
        'original_image_url': img.original_image_url,
        'processed_image_url': img.processed_image_url,
        'file_size': img.file_size,
    }


@require_http_methods(["GET"])
def api_image_list(request):
    queryset = UploadedImage.objects.all()

    query = request.GET.get('query')
    if query:
        queryset = queryset.filter(filename__icontains=query)

    date_from = request.GET.get('date_from')
    if date_from:
        queryset = queryset.filter(upload_timestamp__date__gte=date_from)

    date_to = request.GET.get('date_to')
    if date_to:
        queryset = queryset.filter(upload_timestamp__date__lte=date_to)

    status = request.GET.get('status')
    if status:
        queryset = queryset.filter(processing_status=status)

    queryset = queryset.order_by('-upload_timestamp')

    page_size = min(int(request.GET.get('page_size', 12)), 100)
    page_number = int(request.GET.get('page', 1))

    paginator = Paginator(queryset, page_size)
    page = paginator.get_page(page_number)

    base_url = request.build_absolute_uri(request.path)
    next_url = None
    if page.has_next():
        next_url = f"{base_url}?page={page.next_page_number()}&page_size={page_size}"
    prev_url = None
    if page.has_previous():
        prev_url = f"{base_url}?page={page.previous_page_number()}&page_size={page_size}"

    return JsonResponse({
        'count': paginator.count,
        'next': next_url,
        'previous': prev_url,
        'results': [_serialize_image_summary(img) for img in page],
    })


@require_http_methods(["GET"])
def api_image_detail(request, image_id):
    try:
        img = UploadedImage.objects.get(id=image_id)
    except UploadedImage.DoesNotExist:
        return JsonResponse({'error': 'Image not found'}, status=404)

    processing_logs = [
        {
            'status': log.status,
            'message': log.message,
            'timestamp': log.timestamp.isoformat() if log.timestamp else None,
            'duration_ms': log.duration_ms,
        }
        for log in img.processing_logs.order_by('-timestamp')
    ]

    return JsonResponse({
        'id': img.id,
        'filename': img.filename,
        'processing_status': img.processing_status,
        'upload_timestamp': img.upload_timestamp.isoformat() if img.upload_timestamp else None,
        'processing_timestamp': img.processing_timestamp.isoformat() if img.processing_timestamp else None,
        'original_image_url': img.original_image_url,
        'processed_image_url': img.processed_image_url,
        'file_size': img.file_size,
        'error_message': img.error_message,
        'detections': img.get_detection_results(),
        'processing_logs': processing_logs,
        'api_response': img.api_response,
    })


@require_http_methods(["GET"])
def api_download_image(request, image_id, image_type):
    try:
        return FileService.download_image(image_id, image_type)
    except Exception as e:
        logger.error(f"Error in api_download_image: {str(e)}")
        return JsonResponse({'error': 'File not found'}, status=404)


@require_http_methods(["GET"])
def api_config(request):
    return JsonResponse({
        'max_upload_bytes': django_settings.UPLOAD_FILE_MAX_SIZE,
        'processing_timeout_minutes': django_settings.PROCESSING_TIMEOUT_MINUTES,
    })
