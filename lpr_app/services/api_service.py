"""
API service for LPR application.

This service handles API-specific logic including canary request detection,
validation, and response formatting.
"""

import logging
import mimetypes
import time
from typing import Dict, Any, Optional, Tuple

from django.conf import settings
from django.http import JsonResponse

from ..models import UploadedImage, ProcessingLog
from .image_processing_service import ImageProcessingService

logger = logging.getLogger(__name__)


class ApiService:
    """Service for handling API operations and canary requests."""
    
    @staticmethod
    def detect_canary_request(request) -> bool:
        """
        Detect if the current request is a canary request.
        
        Args:
            request: Django request object
            
        Returns:
            True if this is a canary request, False otherwise
        """
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
        
        return is_canary
    
    @staticmethod
    def validate_api_request(request) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validate API request for image upload.
        
        Args:
            request: Django request object
            
        Returns:
            Tuple of (is_valid, error_response)
        """
        # Check if image file is provided
        if 'image' not in request.FILES:
            return False, {
                'success': False,
                'error': 'No image file provided',
                'error_code': 'MISSING_IMAGE'
            }
        
        uploaded_file = request.FILES['image']
        
        # Validate file type - use more robust detection
        content_type = uploaded_file.content_type or mimetypes.guess_type(uploaded_file.name)[0]
        
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/bmp']
        if content_type not in allowed_types:
            return False, {
                'success': False,
                'error': f'Unsupported file type: {content_type}',
                'error_code': 'INVALID_FILE_TYPE'
            }
        
        # Validate file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB in bytes
        if uploaded_file.size > max_size:
            return False, {
                'success': False,
                'error': f'File too large. Maximum size is 10MB',
                'error_code': 'FILE_TOO_LARGE'
            }
        
        return True, None
    
    @staticmethod
    def determine_save_image_setting(request, is_canary: bool) -> bool:
        """
        Determine if images should be saved based on request parameters and canary status.
        
        Args:
            request: Django request object
            is_canary: Whether this is a canary request
            
        Returns:
            Boolean indicating whether to save images
        """
        # Handle save_image parameter - only honor for canary requests
        save_image_param = request.POST.get('save_image', 'true').lower() != 'false'
        save_image = save_image_param if is_canary else True
        
        if not save_image and not is_canary:
            logger.warning("Non-canary request attempted to use save_image=false, forcing save=True")
        
        return save_image
    
    @staticmethod
    def create_upload_image_record(uploaded_file, save_image: bool, is_canary: bool) -> UploadedImage:
        """
        Create an UploadedImage record.
        
        Args:
            uploaded_file: The uploaded file
            save_image: Whether images will be saved
            is_canary: Whether this is a canary request
            
        Returns:
            UploadedImage instance
        """
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
        
        return uploaded_image
    
    @staticmethod
    def format_success_response(
        result: Dict[str, Any], 
        uploaded_image: Optional[UploadedImage],
        processing_time_ms: int,
        is_canary: bool,
        save_image: bool
    ) -> JsonResponse:
        """
        Format success response for API requests.
        
        Args:
            result: Processing result
            uploaded_image: UploadedImage instance (may be None for cleaned up canary requests)
            processing_time_ms: Processing time in milliseconds
            is_canary: Whether this was a canary request
            save_image: Whether images were saved
            
        Returns:
            JsonResponse with formatted success response
        """
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
        detection_results = None
        plate_count = 0
        ocr_count = 0
        processing_timestamp = None
        
        if uploaded_image:
            try:
                detection_results = uploaded_image.get_detection_results()
                plate_count = uploaded_image.get_plate_count()
                ocr_count = uploaded_image.get_total_ocr_count()
                processing_timestamp = uploaded_image.processing_timestamp.isoformat() if uploaded_image.processing_timestamp else None
            except UploadedImage.DoesNotExist:
                # Record was deleted (canary cleanup)
                pass
        
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
    
    @staticmethod
    def format_error_response(
        error_message: str,
        error_code: str,
        image_id: Optional[int] = None,
        processing_time_ms: int = 0,
        is_canary: bool = False,
        status_code: int = 500
    ) -> JsonResponse:
        """
        Format error response for API requests.
        
        Args:
            error_message: Error message
            error_code: Error code for client reference
            image_id: Optional image ID
            processing_time_ms: Processing time in milliseconds
            is_canary: Whether this was a canary request
            status_code: HTTP status code
            
        Returns:
            JsonResponse with formatted error response
        """
        response_data = {
            'success': False,
            'error': error_message,
            'error_code': error_code,
            'image_id': image_id,
            'processing_time_ms': processing_time_ms,
            'canary_request': is_canary
        }
        
        return JsonResponse(response_data, status=status_code)
