"""
Views module for LPR app.

This module provides backward compatibility imports while the refactoring is in progress.
The actual views are organized into separate modules for better maintainability.
"""

# Import all views from their respective modules for backward compatibility
from .web_views import *
from .api_views import *
from .file_views import *

# Maintain backward compatibility with existing imports
__all__ = [
    # Web views
    'home',
    'upload_image',
    'result_view',
    'image_list',
    'image_detail',
    
    # API views
    'api_health_check',
    'api_ocr_upload',
    'upload_progress',
    'metrics_view',
    
    # File views
    'download_image',
    
    # Utility functions (kept for backward compatibility)
    'process_uploaded_image',
]
