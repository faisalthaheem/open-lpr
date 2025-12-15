"""
Response helper utilities for LPR application.

This module contains standardized response formatting functions
for web and API responses.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)


class ResponseHelper:
    """Utility class for standardizing HTTP responses."""
    
    @staticmethod
    def success_json_response(
        data: Dict[str, Any],
        status_code: int = 200,
        message: Optional[str] = None
    ) -> JsonResponse:
        """
        Create a standardized success JSON response.
        
        Args:
            data: Response data dictionary
            status_code: HTTP status code (default: 200)
            message: Optional success message
            
        Returns:
            JsonResponse with standardized success format
        """
        response_data = {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            **data
        }
        
        if message:
            response_data['message'] = message
        
        return JsonResponse(response_data, status=status_code)
    
    @staticmethod
    def error_json_response(
        error_message: str,
        error_code: Optional[str] = None,
        status_code: int = 400,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> JsonResponse:
        """
        Create a standardized error JSON response.
        
        Args:
            error_message: Error message
            error_code: Optional error code for client reference
            status_code: HTTP status code (default: 400)
            additional_data: Additional data to include in response
            
        Returns:
            JsonResponse with standardized error format
        """
        response_data = {
            'success': False,
            'error': error_message,
            'timestamp': datetime.now().isoformat()
        }
        
        if error_code:
            response_data['error_code'] = error_code
        
        if additional_data:
            response_data.update(additional_data)
        
        return JsonResponse(response_data, status=status_code)
    
    @staticmethod
    def validation_error_response(form_errors: Dict[str, Any]) -> JsonResponse:
        """
        Create a validation error response from form errors.
        
        Args:
            form_errors: Dictionary of form validation errors
            
        Returns:
            JsonResponse with validation error format
        """
        return ResponseHelper.error_json_response(
            error_message='Validation failed',
            error_code='VALIDATION_ERROR',
            status_code=400,
            additional_data={'errors': form_errors}
        )
    
    @staticmethod
    def not_found_response(resource_name: str = 'Resource') -> JsonResponse:
        """
        Create a standardized not found response.
        
        Args:
            resource_name: Name of the resource that was not found
            
        Returns:
            JsonResponse with not found format
        """
        return ResponseHelper.error_json_response(
            error_message=f'{resource_name} not found',
            error_code='NOT_FOUND',
            status_code=404
        )
    
    @staticmethod
    def method_not_allowed_response(allowed_methods: str = 'GET') -> JsonResponse:
        """
        Create a method not allowed response.
        
        Args:
            allowed_methods: String of allowed HTTP methods
            
        Returns:
            JsonResponse with method not allowed format
        """
        return ResponseHelper.error_json_response(
            error_message=f'Method not allowed. Allowed methods: {allowed_methods}',
            error_code='METHOD_NOT_ALLOWED',
            status_code=405
        )
    
    @staticmethod
    def server_error_response(error_message: str = 'Internal server error') -> JsonResponse:
        """
        Create a standardized server error response.
        
        Args:
            error_message: Error message (default: 'Internal server error')
            
        Returns:
            JsonResponse with server error format
        """
        return ResponseHelper.error_json_response(
            error_message=error_message,
            error_code='INTERNAL_ERROR',
            status_code=500
        )


class WebResponseHelper:
    """Utility class for web-specific response helpers."""
    
    @staticmethod
    def get_base_context(title: str = 'License Plate Recognition') -> Dict[str, Any]:
        """
        Get base context for web templates.
        
        Args:
            title: Page title
            
        Returns:
            Dictionary with base context data
        """
        from django.conf import settings
        
        return {
            'title': title,
            'settings': settings,
        }
    
    @staticmethod
    def get_image_context(uploaded_image) -> Dict[str, Any]:
        """
        Get context data for an image template.
        
        Args:
            uploaded_image: UploadedImage instance
            
        Returns:
            Dictionary with image context data
        """
        return {
            'uploaded_image': uploaded_image,
            'detection_results': uploaded_image.get_detection_results(),
            'plate_count': uploaded_image.get_plate_count(),
            'ocr_count': uploaded_image.get_total_ocr_count(),
            'first_ocr_text': uploaded_image.get_first_ocr_text(),
        }


class ApiPaginationHelper:
    """Utility class for API pagination responses."""
    
    @staticmethod
    def paginate_queryset(queryset, page: int, per_page: int) -> tuple:
        """
        Paginate a queryset and return page object and pagination info.
        
        Args:
            queryset: Django queryset to paginate
            page: Page number
            per_page: Items per page
            
        Returns:
            Tuple of (page_obj, pagination_info)
        """
        from django.core.paginator import Paginator
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        pagination_info = {
            'current_page': page_obj.number,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'items_per_page': per_page,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        }
        
        if page_obj.has_next():
            pagination_info['next_page'] = page_obj.next_page_number()
        
        if page_obj.has_previous():
            pagination_info['previous_page'] = page_obj.previous_page_number()
        
        return page_obj, pagination_info
    
    @staticmethod
    def format_paginated_response(
        items: list,
        pagination_info: Dict[str, Any],
        request_path: str
    ) -> Dict[str, Any]:
        """
        Format a paginated API response.
        
        Args:
            items: List of items for current page
            pagination_info: Pagination metadata
            request_path: Base request path for building URLs
            
        Returns:
            Dictionary formatted for API response
        """
        return {
            'items': items,
            'pagination': pagination_info,
            'links': {
                'self': f"{request_path}?page={pagination_info['current_page']}",
                'first': f"{request_path}?page=1",
                'last': f"{request_path}?page={pagination_info['total_pages']}",
            }
        }
