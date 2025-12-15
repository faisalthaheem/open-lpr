"""
Image processing service for LPR application.

This service handles the core image processing workflow, including
API integration, coordinate scaling, and file operations.
"""

import logging
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional

from django.conf import settings

from ..models import UploadedImage, ProcessingLog
from .qwen_client import get_qwen_client, LPR_PROMPT, parse_lpr_response
from .image_processor import ImageProcessor
from .bbox_visualizer import visualize_lpr_on_image, create_side_by_side_comparison

logger = logging.getLogger(__name__)


class ImageProcessingService:
    """Service for handling image processing workflow."""
    
    @staticmethod
    def process_uploaded_image(uploaded_image: UploadedImage, save_image: bool = True) -> Dict[str, Any]:
        """
        Process an uploaded image through the LPR pipeline.
        
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
            uploaded_image.api_response = parsed_response  # type: ignore[arg-type]
            uploaded_image.processing_status = 'completed'
            uploaded_image.processing_timestamp = datetime.now()
            
            # Only save processed image path if we actually saved image
            if save_image and output_path:
                output_path_str = str(output_path)
                uploaded_image.processed_image.name = output_path_str.replace(str(settings.MEDIA_ROOT) + '/', '')
            
            logger.info(f"DEBUG: About to save record, save_image={save_image}")
            uploaded_image.save()
            logger.info(f"DEBUG: Record saved, checking cleanup condition")
            
            # Handle cleanup for canary requests
            result = ImageProcessingService._handle_canary_cleanup(
                uploaded_image, save_image, comparison_path
            )
            if result:
                return result
            
            logger.info(f"DEBUG: Not cleaning up because save_image={save_image}")
            
            # Log success
            duration = (time.time() - start_time) * 1000
            ProcessingLog.objects.create(
                uploaded_image=uploaded_image,
                status='success',
                message=f'Processing completed successfully',
                duration_ms=int(duration)
            )
            
            # Clean up temporary files
            if prepared_path != image_path and os.path.exists(prepared_path):
                os.remove(prepared_path)
            
            processing_duration = time.time() - processing_start_time
            
            return {
                'success': True, 
                'processed_image_path': output_path,
                'processing_duration': processing_duration
            }
            
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
    
    @staticmethod
    def _handle_canary_cleanup(uploaded_image: UploadedImage, save_image: bool, comparison_path: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Handle cleanup for canary requests.
        
        Args:
            uploaded_image: The uploaded image instance
            save_image: Whether images should be saved
            comparison_path: Path to comparison image
            
        Returns:
            Result dictionary if cleanup was performed, None otherwise
        """
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
        
        return None
