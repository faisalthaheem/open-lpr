"""
File views for LPR application.

This module contains views for handling file operations including
downloading and file management.
"""

import logging

from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404

from ..services.file_service import FileService
from ..utils.response_helpers import ResponseHelper
from ..utils.validators import FileValidator

logger = logging.getLogger(__name__)


def download_image(request, image_id: int, image_type: str):
    """
    Download original or processed image.
    
    Args:
        request: Django request object
        image_id: ID of the uploaded image
        image_type: Type of image to download ('original' or 'processed')
        
    Returns:
        HttpResponse with the image file or error response
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
    except Http404:
        # Re-raise Http404 to let Django handle it properly
        raise
    except Exception as e:
        logger.error(f"Error in download_image: {str(e)}")
        return ResponseHelper.not_found_response('Image file')
