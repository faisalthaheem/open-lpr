"""
Validation utilities for LPR application.

This module contains common validation functions used across the application.
"""

import logging
import mimetypes
from typing import Tuple, Optional, Dict, Any

from django.core.files.uploadedfile import UploadedFile

logger = logging.getLogger(__name__)


class FileValidator:
    """Utility class for file validation operations."""
    
    @staticmethod
    def validate_image_file(uploaded_file: UploadedFile) -> Tuple[bool, Optional[str]]:
        """
        Validate an uploaded image file.
        
        Args:
            uploaded_file: The uploaded file to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not uploaded_file:
            return False, 'No file provided'
        
        # Check file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB in bytes
        if uploaded_file.size > max_size:
            return False, f'File too large. Maximum size is 10MB, got {uploaded_file.size / (1024 * 1024):.1f}MB'
        
        # Check file size is not empty
        if uploaded_file.size == 0:
            return False, 'File is empty'
        
        # Validate file type
        content_type = uploaded_file.content_type or mimetypes.guess_type(uploaded_file.name)[0]
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/bmp', 'image/webp']
        
        if content_type not in allowed_types:
            return False, f'Unsupported file type: {content_type}. Allowed types: {", ".join(allowed_types)}'
        
        # Check file extension matches content type
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
        file_extension = uploaded_file.name.lower().split('.')[-1]
        if f'.{file_extension}' not in allowed_extensions:
            return False, f'Invalid file extension: .{file_extension}. Allowed extensions: {", ".join(allowed_extensions)}'
        
        return True, None
    
    @staticmethod
    def validate_image_id(image_id: Any) -> Tuple[bool, Optional[str]]:
        """
        Validate image ID parameter.
        
        Args:
            image_id: The image ID to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not image_id:
            return False, 'Image ID is required'
        
        try:
            image_id = int(image_id)
            if image_id <= 0:
                return False, 'Image ID must be a positive integer'
        except (ValueError, TypeError):
            return False, 'Invalid image ID format'
        
        return True, None
    
    @staticmethod
    def validate_image_type(image_type: str) -> Tuple[bool, Optional[str]]:
        """
        Validate image type parameter.
        
        Args:
            image_type: The image type to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not image_type:
            return False, 'Image type is required'
        
        valid_types = ['original', 'processed']
        if image_type not in valid_types:
            return False, f'Invalid image type: {image_type}. Valid types: {", ".join(valid_types)}'
        
        return True, None


class FormValidator:
    """Utility class for form validation operations."""
    
    @staticmethod
    def validate_search_params(params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate search parameters for image list.
        
        Args:
            params: Dictionary of search parameters
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate date range if both dates are provided
        date_from = params.get('date_from')
        date_to = params.get('date_to')
        
        if date_from and date_to:
            if date_from > date_to:
                return False, 'From date cannot be later than to date'
        
        # Validate status
        status = params.get('processing_status')
        if status:
            valid_statuses = ['', 'pending', 'processing', 'completed', 'failed']
            if status not in valid_statuses:
                return False, f'Invalid processing status: {status}'
        
        # Validate query length
        query = params.get('query', '')
        if len(query) > 100:
            return False, 'Search query is too long (maximum 100 characters)'
        
        return True, None


class ApiValidator:
    """Utility class for API validation operations."""
    
    @staticmethod
    def validate_canary_headers(request, canary_header_name: str, canary_header_value: str) -> bool:
        """
        Validate canary request headers.
        
        Args:
            request: Django request object
            canary_header_name: Expected header name
            canary_header_value: Expected header value
            
        Returns:
            True if headers are valid for canary request
        """
        header_key = canary_header_name.upper().replace("-", "_")
        actual_value = request.META.get(f'HTTP_{header_key}')
        
        return actual_value == canary_header_value
    
    @staticmethod
    def validate_pagination_params(page: Any, per_page: Any) -> Tuple[int, int, Optional[str]]:
        """
        Validate pagination parameters.
        
        Args:
            page: Page number parameter
            per_page: Items per page parameter
            
        Returns:
            Tuple of (validated_page, validated_per_page, error_message)
        """
        try:
            page = int(page) if page else 1
            if page < 1:
                page = 1
        except (ValueError, TypeError):
            page = 1
        
        try:
            per_page = int(per_page) if per_page else 12
            if per_page < 1:
                per_page = 12
            elif per_page > 100:  # Maximum 100 items per page
                per_page = 100
        except (ValueError, TypeError):
            per_page = 12
        
        return page, per_page, None
