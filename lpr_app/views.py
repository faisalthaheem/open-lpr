import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.urls import reverse
from django.core.paginator import Paginator
from django.db.models import Q
from django.conf import settings

from .models import UploadedImage, ProcessingLog
from .forms import ImageUploadForm, LPRSettingsForm, ImageSearchForm
from .services.qwen_client import get_qwen_client, LPR_PROMPT, parse_lpr_response
from .services.image_processor import ImageProcessor
from .services.bbox_visualizer import visualize_lpr_on_image, create_side_by_side_comparison
from .metrics import (
    PROCESSING_DURATION, API_REQUEST_DURATION, UPLOAD_TOTAL, PROCESSING_TOTAL,
    PLATES_DETECTED_TOTAL, OCR_TEXTS_DETECTED_TOTAL, DETECTION_CONFIDENCE,
    IMAGES_IN_STORAGE, PROCESSING_QUEUE_SIZE, PROCESSING_ERRORS_TOTAL,
    API_ERRORS_TOTAL, FILE_ERRORS_TOTAL, API_HEALTH_STATUS, get_metrics_response
)

logger = logging.getLogger(__name__)

# Initialize metrics on module import
try:
    from .metrics import initialize_persistent_metrics
    initialize_persistent_metrics()
    logger.info("Metrics initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize metrics: {e}")


def home(request):
    """
    Home page with image upload form
    """
    upload_form = ImageUploadForm()
    search_form = ImageSearchForm()
    
    # Get recent uploads for display
    recent_uploads = UploadedImage.objects.filter(
        processing_status='completed'
    ).order_by('-upload_timestamp')[:9]
    
    context = {
        'upload_form': upload_form,
        'search_form': search_form,
        'recent_uploads': recent_uploads,
        'title': 'License Plate Recognition',
        'settings': settings
    }
    
    return render(request, 'lpr_app/upload.html', context)


def upload_image(request):
    """
    Handle image upload and processing
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    form = ImageUploadForm(request.POST, request.FILES)
    
    if not form.is_valid():
        return JsonResponse({
            'error': 'Form validation failed',
            'errors': form.errors
        }, status=400)
    
    try:
        # Get uploaded image
        uploaded_file = form.cleaned_data['image']
        
        # Create database record
        uploaded_image = UploadedImage.objects.create(
            original_image=uploaded_file,
            filename=uploaded_file.name,
            processing_status='pending'
        )
        
        # Log processing start
        ProcessingLog.objects.create(
            uploaded_image=uploaded_image,
            status='started',
            message='Image upload started'
        )
        
        # Process image asynchronously (for now, process synchronously)
        try:
            result = process_uploaded_image(uploaded_image)
            
            if result['success']:
                UPLOAD_TOTAL.labels(status='success').inc()
                PROCESSING_TOTAL.labels(status='completed').inc()
                
                # Update storage metrics
                total_images = UploadedImage.objects.count()
                IMAGES_IN_STORAGE.set(total_images)
                
                # Update queue size
                pending_count = UploadedImage.objects.filter(processing_status='pending').count()
                PROCESSING_QUEUE_SIZE.set(pending_count)
                
                return JsonResponse({
                    'success': True,
                    'image_id': uploaded_image.id,
                    'message': 'Image processed successfully',
                    'redirect_url': reverse('lpr_app:result', kwargs={'image_id': uploaded_image.id})
                })
            else:
                UPLOAD_TOTAL.labels(status='failed').inc()
                PROCESSING_TOTAL.labels(status='failed').inc()
                PROCESSING_ERRORS_TOTAL.labels(error_type='processing_failed').inc()
                
                return JsonResponse({
                    'error': result['error'],
                    'message': 'Image processing failed'
                }, status=500)
                
        except Exception as e:
            logger.error(f"Error processing image {uploaded_image.id}: {str(e)}")
            
            # Update status to failed
            uploaded_image.processing_status = 'failed'
            uploaded_image.error_message = str(e)
            uploaded_image.save()
            
            UPLOAD_TOTAL.labels(status='error').inc()
            PROCESSING_TOTAL.labels(status='error').inc()
            PROCESSING_ERRORS_TOTAL.labels(error_type='exception').inc()
            
            return JsonResponse({
                'error': 'Processing failed',
                'message': str(e)
            }, status=500)
            
    except Exception as e:
        logger.error(f"Error in upload_image view: {str(e)}")
        return JsonResponse({
            'error': 'Upload failed',
            'message': str(e)
        }, status=500)


def process_uploaded_image(uploaded_image: UploadedImage, save_image: bool = True) -> Dict[str, Any]:
    """
    Process an uploaded image through the LPR pipeline
    
    Args:
        uploaded_image: UploadedImage instance
        save_image: Whether to save processed images (default: True)
        
    Returns:
        Dictionary with processing result
    """
    processing_start_time = time.time()
    logger.info(f"DEBUG: process_uploaded_image called with save_image={save_image}")
    try:
        # Update status to processing
        uploaded_image.processing_status = 'processing'
        uploaded_image.save()
        logger.info(f"DEBUG: Status updated to processing")
        
        # Log API call start
        ProcessingLog.objects.create(
            uploaded_image=uploaded_image,
            status='api_call',
            message='Starting Qwen3-VL API call'
        )
        
        start_time = time.time()
        
        # Prepare image for API
        image_path = uploaded_image.original_image.path
        prepared_path = ImageProcessor.prepare_image_for_api(image_path)
        
        if not prepared_path:
            return {'success': False, 'error': 'Failed to prepare image for API'}
        
        # Get image dimensions for coordinate scaling
        original_image_info = ImageProcessor.get_image_info(image_path)
        if not original_image_info:
            return {'success': False, 'error': 'Failed to get original image info'}
        
        original_h = original_image_info['height']
        original_w = original_image_info['width']
        
        # Get resized image dimensions if different from original
        resized_h = original_h
        resized_w = original_w
        if prepared_path != image_path:
            resized_image_info = ImageProcessor.get_image_info(prepared_path)
            if resized_image_info:
                resized_h = resized_image_info['height']
                resized_w = resized_image_info['width']
        
        # Encode image to base64
        base64_image = ImageProcessor.encode_image_to_base64(prepared_path)
        
        if not base64_image:
            return {'success': False, 'error': 'Failed to encode image'}
        
        # Call Qwen3-VL API with customized prompt
        client = get_qwen_client()
        # Customize prompt with actual filename
        customized_prompt = LPR_PROMPT.replace('[actual filename of the image]', uploaded_image.filename)
        api_response = client.analyze_image(base64_image, customized_prompt)
        
        if not api_response:
            return {'success': False, 'error': 'API call failed'}
        
        # Parse response with coordinate scaling
        parsed_response = parse_lpr_response(api_response, original_h, original_w, resized_h, resized_w)
        
        if not parsed_response:
            return {'success': False, 'error': 'Failed to parse API response'}
        
        # Conditionally visualize and save processed images
        output_path = None
        comparison_path = None
        
        if save_image:
            # Visualize results
            output_filename = f"processed_{uploaded_image.filename}"
            output_path = os.path.join(
                os.path.dirname(str(uploaded_image.original_image.path)),
                output_filename
            )
            
            success = visualize_lpr_on_image(image_path, parsed_response, output_path)
            
            if not success:
                return {'success': False, 'error': 'Failed to create visualization'}
            
            # Create side-by-side comparison
            comparison_filename = f"comparison_{uploaded_image.filename}"
            comparison_path = os.path.join(
                os.path.dirname(str(uploaded_image.original_image.path)),
                comparison_filename
            )
            
            create_side_by_side_comparison(image_path, output_path, comparison_path)
        
        # Update database record
        uploaded_image.api_response = parsed_response
        uploaded_image.processing_status = 'completed'
        uploaded_image.processing_timestamp = datetime.now()
        
        # Only save processed image path if we actually saved image
        if save_image and output_path:
            output_path_str = str(output_path)
            uploaded_image.processed_image.name = output_path_str.replace(str(settings.MEDIA_ROOT) + '/', '')
        
        logger.info(f"DEBUG: About to save record, save_image={save_image}")
        uploaded_image.save()
        logger.info(f"DEBUG: Record saved, checking cleanup condition")
        
        # For canary requests with save_image=False, clean up completely
        logger.info(f"DEBUG: save_image={save_image}, about to check cleanup condition")
        if not save_image:
            logger.info(f"Cleaning up canary image {uploaded_image.id} ({uploaded_image.filename})")
            
            # Delete original image file
            if uploaded_image.original_image and os.path.exists(uploaded_image.original_image.path):
                try:
                    os.remove(uploaded_image.original_image.path)
                    logger.info(f"Deleted original image: {uploaded_image.original_image.path}")
                except Exception as e:
                    logger.error(f"Failed to delete original image: {e}")
            else:
                logger.warning(f"Original image file not found: {uploaded_image.original_image.path if uploaded_image.original_image else 'None'}")
            
            # Delete comparison image if it exists
            if comparison_path and os.path.exists(comparison_path):
                try:
                    os.remove(comparison_path)
                    logger.info(f"Deleted comparison image: {comparison_path}")
                except Exception as e:
                    logger.error(f"Failed to delete comparison image: {e}")
            
            # Delete database record
            try:
                image_id = uploaded_image.id  # Save ID for logging after deletion
                uploaded_image.delete()
                logger.info(f"Deleted database record for canary image {image_id}")
            except Exception as e:
                logger.error(f"Failed to delete database record: {e}")
            
            return {'success': True, 'message': 'Canary image processed and cleaned up'}
        else:
            logger.info(f"DEBUG: Not cleaning up because save_image={save_image}")
        
        # Log success
        duration = (time.time() - start_time) * 1000
        ProcessingLog.objects.create(
            uploaded_image=uploaded_image,
            status='success',
            message=f'Processing completed successfully',
            duration_ms=int(duration)
        )
        
                # Update business metrics
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
        
        # Update processing duration metric
        processing_duration = time.time() - processing_start_time
        PROCESSING_DURATION.labels(status='completed').observe(processing_duration)
        
        # Immediately save metrics after processing
        from .metrics import save_metrics_to_file
        save_metrics_to_file()
        
        # Clean up temporary files
        if prepared_path != image_path and os.path.exists(prepared_path):
            os.remove(prepared_path)
        
        return {'success': True, 'processed_image_path': output_path}
        
    except Exception as e:
        logger.error(f"Error in process_uploaded_image: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Update status to failed
        uploaded_image.processing_status = 'failed'
        uploaded_image.error_message = str(e)
        uploaded_image.save()
        
        # Log error
        ProcessingLog.objects.create(
            uploaded_image=uploaded_image,
            status='error',
            message=f'Processing failed: {str(e)}'
        )
        
        return {'success': False, 'error': str(e)}


def result_view(request, image_id: int):
    """
    Display processing results for a specific image
    """
    uploaded_image = get_object_or_404(UploadedImage, id=image_id)
    
    # Get detection results
    detection_results = uploaded_image.get_detection_results()
    plate_count = uploaded_image.get_plate_count()
    ocr_count = uploaded_image.get_total_ocr_count()
    
    context = {
        'uploaded_image': uploaded_image,
        'detection_results': detection_results,
        'plate_count': plate_count,
        'ocr_count': ocr_count,
        'title': f'Results - {uploaded_image.filename}'
    }
    
    return render(request, 'lpr_app/results.html', context)


def image_list(request):
    """
    Display list of uploaded images with search and filtering
    """
    search_form = ImageSearchForm(request.GET)
    queryset = UploadedImage.objects.all()
    
    # Apply filters
    if search_form.is_valid():
        query = search_form.cleaned_data.get('query')
        date_from = search_form.cleaned_data.get('date_from')
        date_to = search_form.cleaned_data.get('date_to')
        status = search_form.cleaned_data.get('processing_status')
        
        if query:
            queryset = queryset.filter(filename__icontains=query)
        
        if date_from:
            queryset = queryset.filter(upload_timestamp__date__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(upload_timestamp__date__lte=date_to)
        
        if status:
            queryset = queryset.filter(processing_status=status)
    
    # Order by upload timestamp (newest first)
    queryset = queryset.order_by('-upload_timestamp')
    
    # Pagination
    paginator = Paginator(queryset, 12)  # 12 images per page
    page_number = request.GET.get('page')
    
    # Handle invalid page numbers gracefully
    try:
        page_number = int(page_number) if page_number else 1
        if page_number < 1:
            page_number = 1
    except (ValueError, TypeError):
        page_number = 1
    
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_form': search_form,
        'title': 'Image History'
    }
    
    return render(request, 'lpr_app/image_list.html', context)


def image_detail(request, image_id: int):
    """
    Display detailed information about a specific image
    """
    uploaded_image = get_object_or_404(UploadedImage, id=image_id)
    
    # Get processing logs
    processing_logs = uploaded_image.processing_logs.order_by('-timestamp')
    
    context = {
        'uploaded_image': uploaded_image,
        'processing_logs': processing_logs,
        'title': f'Details - {uploaded_image.filename}'
    }
    
    return render(request, 'lpr_app/image_detail.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def upload_progress(request):
    """
    AJAX endpoint to check upload progress
    """
    image_id = request.POST.get('image_id')
    
    if not image_id:
        return JsonResponse({'error': 'Image ID required'}, status=400)
    
    try:
        uploaded_image = UploadedImage.objects.get(id=image_id)
        
        return JsonResponse({
            'status': uploaded_image.processing_status,
            'error_message': uploaded_image.error_message,
            'processing_timestamp': uploaded_image.processing_timestamp.isoformat() if uploaded_image.processing_timestamp else None
        })
        
    except UploadedImage.DoesNotExist:
        return JsonResponse({'error': 'Image not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in upload_progress: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


def download_image(request, image_id: int, image_type: str):
    """
    Download original or processed image
    """
    uploaded_image = get_object_or_404(UploadedImage, id=image_id)
    
    if image_type == 'original':
        image_path = uploaded_image.original_image.path
        filename = uploaded_image.filename
    elif image_type == 'processed':
        if not uploaded_image.processed_image:
            raise Http404("Processed image not available")
        image_path = uploaded_image.processed_image.path
        filename = f"processed_{uploaded_image.filename}"
    else:
        raise Http404("Invalid image type")
    
    if not os.path.exists(image_path):
        raise Http404("Image file not found")
    
    # Serve the file
    with open(image_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='image/jpeg')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


def api_health_check(request):
    """
    Health check endpoint for the API
    """
    try:
        # Check Qwen3-VL API
        api_start_time = time.time()
        client = get_qwen_client()
        api_healthy = client.health_check()
        api_duration = time.time() - api_start_time
        
        # Update API health status metric
        API_HEALTH_STATUS.set(1 if api_healthy else 0)
        API_REQUEST_DURATION.observe(api_duration)
        
        # Check database connection
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_healthy = cursor.fetchone()[0] == 1
        
        status_code = 200 if api_healthy and db_healthy else 503
        
        return JsonResponse({
            'status': 'healthy' if status_code == 200 else 'unhealthy',
            'api_healthy': api_healthy,
            'database_healthy': db_healthy,
            'timestamp': datetime.now().isoformat()
        }, status=status_code)
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, status=503)


@csrf_exempt
@require_http_methods(["POST"])
def api_ocr_upload(request):
    """
    REST API endpoint to upload an image and get OCR results synchronously
    
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
    import time
    from datetime import datetime
    
    # Canary configuration from settings
    canary_header_name = getattr(settings, 'CANARY_HEADER_NAME', 'X-Canary-Request')
    canary_header_value = getattr(settings, 'CANARY_HEADER_VALUE', 'true')
    canary_enabled = str(getattr(settings, 'CANARY_ENABLED', 'true')).lower() == 'true'
    
    # Check if this is a canary request
    header_key = canary_header_name.upper().replace("-", "_")
    is_canary = (canary_enabled and 
                 request.META.get(f'HTTP_{header_key}') == canary_header_value)
    
    # Log canary requests for audit
    if is_canary:
        logger.info(f"Canary request detected from {request.META.get('REMOTE_ADDR')}")
    
    # Check if image file is provided
    if 'image' not in request.FILES:
        return JsonResponse({
            'success': False,
            'error': 'No image file provided',
            'error_code': 'MISSING_IMAGE'
        }, status=400)
    
    uploaded_file = request.FILES['image']
    
    # Validate file type - use more robust detection
    import mimetypes
    content_type = uploaded_file.content_type or mimetypes.guess_type(uploaded_file.name)[0]
    
    allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/bmp']
    if content_type not in allowed_types:
        return JsonResponse({
            'success': False,
            'error': f'Unsupported file type: {content_type}',
            'error_code': 'INVALID_FILE_TYPE'
        }, status=400)
    
    # Validate file size (max 10MB)
    max_size = 10 * 1024 * 1024  # 10MB in bytes
    if uploaded_file.size > max_size:
        return JsonResponse({
            'success': False,
            'error': f'File too large. Maximum size is 10MB',
            'error_code': 'FILE_TOO_LARGE'
        }, status=400)
    
    try:
        start_time = time.time()
        
        # Handle save_image parameter - only honor for canary requests
        save_image_param = request.POST.get('save_image', 'true').lower() != 'false'
        save_image = save_image_param if is_canary else True
        
        if not save_image and not is_canary:
            logger.warning("Non-canary request attempted to use save_image=false, forcing save=True")
        
        # Create database record
        uploaded_image = UploadedImage.objects.create(
            original_image=uploaded_file,
            filename=uploaded_file.name,
            processing_status='pending'
        )
        
        # Log processing start
        ProcessingLog.objects.create(
            uploaded_image=uploaded_image,
            status='started',
            message=f'API OCR processing started (save_image={save_image}, is_canary={is_canary})'
        )
        
        # Process the image
        result = process_uploaded_image(uploaded_image, save_image=save_image)
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Update canary-specific metrics
        if is_canary:
            from .metrics import CANARY_REQUESTS_TOTAL, CANARY_PROCESSING_DURATION
            CANARY_REQUESTS_TOTAL.labels(status='success' if result['success'] else 'failed').inc()
            CANARY_PROCESSING_DURATION.observe(processing_time_ms / 1000.0)
        
        if result['success']:
            # For canary requests with cleanup, the record may be deleted
            if is_canary and not save_image and 'message' in result and 'cleaned up' in result['message']:
                # Canary image was processed and cleaned up
                response_data = {
                    'success': True,
                    'message': result['message'],
                    'processing_time_ms': processing_time_ms,
                    'canary_request': is_canary,
                    'image_saved': False,
                    'image_id': None  # Record was deleted
                }
                return JsonResponse(response_data, status=200)
            
            # Get detection results (may be None if record was deleted for canary)
            try:
                detection_results = uploaded_image.get_detection_results()
                plate_count = uploaded_image.get_plate_count()
                ocr_count = uploaded_image.get_total_ocr_count()
                processing_timestamp = uploaded_image.processing_timestamp.isoformat() if uploaded_image.processing_timestamp else None
            except UploadedImage.DoesNotExist:
                # Record was deleted (canary cleanup)
                detection_results = None
                plate_count = 0
                ocr_count = 0
                processing_timestamp = None
            
            # Prepare response data
            response_data = {
                'success': True,
                'image_id': uploaded_image.id if uploaded_image and uploaded_image.pk else None,
                'filename': uploaded_image.filename if uploaded_image else 'deleted',
                'processing_time_ms': processing_time_ms,
                'results': detection_results,
                'summary': {
                    'total_plates': plate_count,
                    'total_ocr_texts': ocr_count
                },
                'processing_timestamp': processing_timestamp,
                'canary_request': is_canary,
                'image_saved': save_image
            }
            
            return JsonResponse(response_data, status=200)
        else:
            # Processing failed
            if is_canary:
                from .metrics import CANARY_REQUESTS_TOTAL
                CANARY_REQUESTS_TOTAL.labels(status='failed').inc()
            
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Unknown processing error'),
                'error_code': 'PROCESSING_FAILED',
                'image_id': uploaded_image.id,
                'processing_time_ms': processing_time_ms,
                'canary_request': is_canary
            }, status=500)
            
    except Exception as e:
        logger.error(f"Error in api_ocr_upload: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Update canary error metrics
        if is_canary:
            from .metrics import CANARY_REQUESTS_TOTAL
            CANARY_REQUESTS_TOTAL.labels(status='error').inc()
        
        return JsonResponse({
            'success': False,
            'error': 'Internal server error during image processing',
            'error_code': 'INTERNAL_ERROR',
            'canary_request': is_canary
        }, status=500)


def metrics_view(request):
    """
    Prometheus metrics endpoint
    """
    try:
        metrics_data, content_type = get_metrics_response()
        return HttpResponse(metrics_data, content_type=content_type)
    except Exception as e:
        logger.error(f"Error generating metrics: {str(e)}")
        return HttpResponse("Error generating metrics", status=500)
