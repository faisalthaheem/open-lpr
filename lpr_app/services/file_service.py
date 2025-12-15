"""
File service for LPR application.

This service handles file operations including downloading, validation,
and file management.
"""

import logging
import os
from typing import Optional

from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404

from ..models import UploadedImage

logger = logging.getLogger(__name__)


class FileService:
    """Service for handling file operations."""
    
    @staticmethod
    def download_image(image_id: int, image_type: str) -> HttpResponse:
        """
        Download original or processed image.
        
        Args:
            image_id: ID of the uploaded image
            image_type: Type of image to download ('original' or 'processed')
            
        Returns:
            HttpResponse with the image file
            
        Raises:
            Http404: If image or file not found
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
    
    @staticmethod
    def get_image_info(image_id: int) -> Optional[dict]:
        """
        Get information about an uploaded image.
        
        Args:
            image_id: ID of the uploaded image
            
        Returns:
            Dictionary with image information or None if not found
        """
        try:
            uploaded_image = UploadedImage.objects.get(id=image_id)
            return {
                'id': uploaded_image.id,
                'filename': uploaded_image.filename,
                'file_size': uploaded_image.file_size,
                'file_size_mb': uploaded_image.file_size_mb,
                'upload_timestamp': uploaded_image.upload_timestamp,
                'processing_timestamp': uploaded_image.processing_timestamp,
                'processing_status': uploaded_image.processing_status,
                'error_message': uploaded_image.error_message,
                'original_image_url': uploaded_image.original_image_url,
                'processed_image_url': uploaded_image.processed_image_url,
                'plate_count': uploaded_image.get_plate_count(),
                'ocr_count': uploaded_image.get_total_ocr_count(),
                'first_ocr_text': uploaded_image.get_first_ocr_text(),
            }
        except UploadedImage.DoesNotExist:
            return None
    
    @staticmethod
    def cleanup_image_files(uploaded_image) -> bool:
        """
        Clean up all files associated with an uploaded image.
        
        Args:
            uploaded_image: UploadedImage instance
            
        Returns:
            True if cleanup was successful, False otherwise
        """
        success = True
        
        # Delete original image file
        if uploaded_image.original_image and os.path.exists(uploaded_image.original_image.path):
            try:
                os.remove(uploaded_image.original_image.path)
                logger.info(f"Deleted original image: {uploaded_image.original_image.path}")
            except Exception as e:
                logger.error(f"Failed to delete original image: {e}")
                success = False
        else:
            logger.warning(f"Original image file not found: {uploaded_image.original_image.path if uploaded_image.original_image else 'None'}")
        
        # Delete processed image file if it exists
        if uploaded_image.processed_image and os.path.exists(uploaded_image.processed_image.path):
            try:
                os.remove(uploaded_image.processed_image.path)
                logger.info(f"Deleted processed image: {uploaded_image.processed_image.path}")
            except Exception as e:
                logger.error(f"Failed to delete processed image: {e}")
                success = False
        
        return success
    
    @staticmethod
    def validate_file_exists(image_id: int, image_type: str = 'original') -> bool:
        """
        Check if a specific image file exists.
        
        Args:
            image_id: ID of the uploaded image
            image_type: Type of image to check ('original' or 'processed')
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            uploaded_image = UploadedImage.objects.get(id=image_id)
            
            if image_type == 'original':
                image_path = uploaded_image.original_image.path
            elif image_type == 'processed':
                if not uploaded_image.processed_image:
                    return False
                image_path = uploaded_image.processed_image.path
            else:
                return False
            
            return os.path.exists(image_path)
            
        except UploadedImage.DoesNotExist:
            return False
