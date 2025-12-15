"""
Web views for LPR application.

This module contains views for rendering web pages and handling
web-based user interactions.
"""

import logging
from typing import Dict, Any

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q

from ..models import UploadedImage
from ..forms import ImageUploadForm, ImageSearchForm
from ..services.image_processing_service import ImageProcessingService
from ..services.file_service import FileService
from ..utils.response_helpers import WebResponseHelper, ResponseHelper
from ..utils.validators import FormValidator, FileValidator
from ..utils.metrics_helpers import MetricsHelper

logger = logging.getLogger(__name__)


def home(request):
    """
    Home page with image upload form.
    """
    upload_form = ImageUploadForm()
    search_form = ImageSearchForm()
    
    # Get recent uploads for display
    recent_uploads = UploadedImage.objects.filter(
        processing_status='completed'
    ).order_by('-upload_timestamp')[:9]
    
    context = WebResponseHelper.get_base_context('License Plate Recognition')
    context.update({
        'upload_form': upload_form,
        'search_form': search_form,
        'recent_uploads': recent_uploads,
    })
    
    return render(request, 'lpr_app/upload.html', context)


def upload_image(request):
    """
    Handle image upload and processing for web interface.
    """
    if request.method != 'POST':
        return ResponseHelper.method_not_allowed_response('POST')
    
    form = ImageUploadForm(request.POST, request.FILES)
    
    if not form.is_valid():
        return ResponseHelper.validation_error_response(form.errors)
    
    try:
        # Get uploaded image
        uploaded_file = form.cleaned_data['image']
        
        # Validate file using utility
        is_valid, error_message = FileValidator.validate_image_file(uploaded_file)
        if not is_valid:
            return ResponseHelper.error_json_response(
                error_message=error_message or 'Unknown validation error',
                error_code='VALIDATION_ERROR',
                status_code=400
            )
        
        # Create database record
        uploaded_image = UploadedImage.objects.create(
            original_image=uploaded_file,
            filename=uploaded_file.name,
            processing_status='pending'
        )
        
        # Log processing start
        from ..models import ProcessingLog
        ProcessingLog.objects.create(
            uploaded_image=uploaded_image,
            status='started',
            message='Image upload started'
        )
        
        # Process image (synchronously for web interface)
        result = ImageProcessingService.process_uploaded_image(uploaded_image, save_image=True)
        
        if result['success']:
            MetricsHelper.record_upload_attempt('success')
            MetricsHelper.record_processing_attempt('completed')
            MetricsHelper.update_detection_metrics(uploaded_image)
            MetricsHelper.update_storage_metrics()
            MetricsHelper.save_metrics()
            
            from django.urls import reverse
            return ResponseHelper.success_json_response({
                'image_id': uploaded_image.id,
                'message': 'Image processed successfully',
                'redirect_url': reverse('lpr_app:result', kwargs={'image_id': uploaded_image.id})
            })
        else:
            MetricsHelper.record_upload_attempt('failed')
            MetricsHelper.record_processing_attempt('failed')
            MetricsHelper.record_processing_error('processing_failed')
            
            return ResponseHelper.error_json_response(
                error_message=result['error'],
                error_code='PROCESSING_FAILED',
                status_code=500
            )
            
    except Exception as e:
        logger.error(f"Error in upload_image view: {str(e)}")
        MetricsHelper.record_upload_attempt('error')
        
        return ResponseHelper.server_error_response('Upload failed')


def result_view(request, image_id: int):
    """
    Display processing results for a specific image.
    """
    # Validate image ID
    is_valid, error_message = FileValidator.validate_image_id(image_id)
    if not is_valid:
        logger.error(f"Invalid image ID in result_view: {image_id}")
        # Return a proper error page instead of raising 404
        return render(request, 'lpr_app/error.html', {
            'error_message': 'Invalid image ID provided',
            'title': 'Error'
        })
    
    uploaded_image = get_object_or_404(UploadedImage, id=image_id)
    
    context = WebResponseHelper.get_base_context(f'Results - {uploaded_image.filename}')
    context.update(WebResponseHelper.get_image_context(uploaded_image))
    
    return render(request, 'lpr_app/results.html', context)


def image_list(request):
    """
    Display list of uploaded images with search and filtering.
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
    
    context = WebResponseHelper.get_base_context('Image History')
    context.update({
        'page_obj': page_obj,
        'search_form': search_form,
    })
    
    return render(request, 'lpr_app/image_list.html', context)


def image_detail(request, image_id: int):
    """
    Display detailed information about a specific image.
    """
    # Validate image ID
    is_valid, error_message = FileValidator.validate_image_id(image_id)
    if not is_valid:
        logger.error(f"Invalid image ID in image_detail: {image_id}")
        return render(request, 'lpr_app/error.html', {
            'error_message': 'Invalid image ID provided',
            'title': 'Error'
        })
    
    uploaded_image = get_object_or_404(UploadedImage, id=image_id)
    
    # Get processing logs
    processing_logs = uploaded_image.processing_logs.order_by('-timestamp')
    
    context = WebResponseHelper.get_base_context(f'Details - {uploaded_image.filename}')
    context.update({
        'uploaded_image': uploaded_image,
        'processing_logs': processing_logs,
    })
    
    return render(request, 'lpr_app/image_detail.html', context)


@require_http_methods(["POST"])
def upload_progress(request):
    """
    AJAX endpoint to check upload progress.
    """
    image_id = request.POST.get('image_id')
    
    if not image_id:
        return ResponseHelper.error_json_response(
            error_message='Image ID required',
            error_code='MISSING_IMAGE_ID',
            status_code=400
        )
    
    # Validate image ID
    is_valid, error_message = FileValidator.validate_image_id(image_id)
    if not is_valid:
        return ResponseHelper.error_json_response(
            error_message=error_message or 'Invalid image ID',
            error_code='INVALID_IMAGE_ID',
            status_code=400
        )
    
    try:
        uploaded_image = UploadedImage.objects.get(id=int(image_id))
        
        return ResponseHelper.success_json_response({
            'status': uploaded_image.processing_status,
            'error_message': uploaded_image.error_message,
            'processing_timestamp': uploaded_image.processing_timestamp.isoformat() if uploaded_image.processing_timestamp else None
        })
        
    except UploadedImage.DoesNotExist:
        return ResponseHelper.not_found_response('Image')
    except Exception as e:
        logger.error(f"Error in upload_progress: {str(e)}")
        return ResponseHelper.server_error_response()


def download_image(request, image_id: int, image_type: str):
    """
    Download original or processed image.
    """
    # Validate parameters
    is_valid_id, error_id = FileValidator.validate_image_id(image_id)
    is_valid_type, error_type = FileValidator.validate_image_type(image_type)
    
    if not is_valid_id:
        return ResponseHelper.error_json_response(
            error_message=error_id or 'Invalid image ID',
            error_code='INVALID_IMAGE_ID',
            status_code=400
        )
    
    if not is_valid_type:
        return ResponseHelper.error_json_response(
            error_message=error_type or 'Invalid image type',
            error_code='INVALID_IMAGE_TYPE',
            status_code=400
        )
    
    try:
        return FileService.download_image(image_id, image_type)
    except Exception as e:
        logger.error(f"Error in download_image: {str(e)}")
        return ResponseHelper.not_found_response('Image file')
