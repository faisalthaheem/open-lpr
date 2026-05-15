import base64
import logging
import os
from typing import Optional, Tuple
from PIL import Image
from django.core.files.uploadedfile import UploadedFile
from django.conf import settings

logger = logging.getLogger(__name__)


class ImageProcessor:
    """
    Service for processing images: encoding, validation, and format conversion
    """
    
    @staticmethod
    def validate_image(uploaded_file: UploadedFile) -> Tuple[bool, str]:
        """
        Validate uploaded image file
        
        Args:
            uploaded_file: Django UploadedFile object
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check file size
        if uploaded_file.size > settings.UPLOAD_FILE_MAX_SIZE:
            max_size_mb = settings.UPLOAD_FILE_MAX_SIZE / (1024 * 1024)
            return False, f"File size exceeds maximum allowed size of {max_size_mb}MB"
        
        # Check file extension
        file_extension = ImageProcessor.get_file_extension(uploaded_file.name)
        if file_extension.lower() not in settings.ALLOWED_IMAGE_TYPES:
            allowed_types = ', '.join(settings.ALLOWED_IMAGE_TYPES)
            return False, f"File type not allowed. Allowed types: {allowed_types}"
        
        # Try to open the image to verify it's a valid image
        try:
            with Image.open(uploaded_file) as img:
                img.verify()
        except Exception as e:
            logger.error(f"Image validation failed: {str(e)}")
            return False, "Invalid image file"
        
        return True, ""
    
    @staticmethod
    def get_file_extension(filename: str) -> str:
        """
        Get file extension from filename
        
        Args:
            filename: Original filename
            
        Returns:
            File extension without dot
        """
        return os.path.splitext(filename)[1].lstrip('.').lower()
    
    @staticmethod
    def encode_image_to_base64(image_path: str) -> Optional[str]:
        """
        Encode image file to base64 string
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Base64 encoded string or None if error occurs
        """
        try:
            with open(image_path, "rb") as image_file:
                base64_string = base64.b64encode(image_file.read()).decode("utf-8")
                logger.info(f"Successfully encoded image: {image_path}")
                return base64_string
                
        except FileNotFoundError:
            logger.error(f"Image file not found: {image_path}")
            return None
        except Exception as e:
            logger.error(f"Error encoding image {image_path}: {str(e)}")
            return None
    
    @staticmethod
    def encode_uploaded_file_to_base64(uploaded_file: UploadedFile) -> Optional[str]:
        """
        Encode uploaded file to base64 string
        
        Args:
            uploaded_file: Django UploadedFile object
            
        Returns:
            Base64 encoded string or None if error occurs
        """
        try:
            # Reset file pointer to beginning
            uploaded_file.seek(0)
            
            # Read file content and encode to base64
            file_content = uploaded_file.read()
            base64_string = base64.b64encode(file_content).decode("utf-8")
            
            # Reset file pointer for potential future use
            uploaded_file.seek(0)
            
            logger.info(f"Successfully encoded uploaded file: {uploaded_file.name}")
            return base64_string
            
        except Exception as e:
            logger.error(f"Error encoding uploaded file {uploaded_file.name}: {str(e)}")
            return None
    
    @staticmethod
    def get_image_info(image_path: str) -> Optional[dict]:
        """
        Get basic information about an image
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary with image info or None if error occurs
        """
        try:
            with Image.open(image_path) as img:
                return {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode,
                    'size_bytes': os.path.getsize(image_path)
                }
        except Exception as e:
            logger.error(f"Error getting image info for {image_path}: {str(e)}")
            return None
    
    @staticmethod
    def resize_image_if_needed(image_path: str, max_width: int = 1920, max_height: int = 1080) -> Optional[str]:
        """
        Resize image if it exceeds maximum dimensions
        
        Args:
            image_path: Path to the original image
            max_width: Maximum allowed width
            max_height: Maximum allowed height
            
        Returns:
            Path to resized image (original if no resize needed) or None if error
        """
        try:
            with Image.open(image_path) as img:
                # Check if resize is needed
                if img.width <= max_width and img.height <= max_height:
                    return image_path
                
                # Calculate new dimensions maintaining aspect ratio
                ratio = min(max_width / img.width, max_height / img.height)
                new_width = int(img.width * ratio)
                new_height = int(img.height * ratio)
                
                # Resize image
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Generate new filename
                base_name, ext = os.path.splitext(image_path)
                resized_path = f"{base_name}_resized{ext}"
                
                # Save resized image
                resized_img.save(resized_path, quality=85)
                
                logger.info(f"Image resized from {img.width}x{img.height} to {new_width}x{new_height}")
                return resized_path
                
        except Exception as e:
            logger.error(f"Error resizing image {image_path}: {str(e)}")
            return None
    
    @staticmethod
    def convert_to_jpeg(image_path: str) -> Optional[str]:
        """
        Convert image to JPEG format for better compatibility
        
        Args:
            image_path: Path to the original image
            
        Returns:
            Path to JPEG image or None if error occurs
        """
        try:
            with Image.open(image_path) as img:
                # Convert RGBA to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                
                # Generate new filename
                base_name = os.path.splitext(image_path)[0]
                jpeg_path = f"{base_name}.jpg"
                
                # Save as JPEG
                img.save(jpeg_path, 'JPEG', quality=85, optimize=True)
                
                logger.info(f"Image converted to JPEG: {jpeg_path}")
                return jpeg_path
                
        except Exception as e:
            logger.error(f"Error converting image to JPEG {image_path}: {str(e)}")
            return None
    
    @staticmethod
    def prepare_image_for_api(image_path: str) -> Optional[str]:
        """
        Prepare image for API submission: resize if needed and convert to JPEG
        
        Args:
            image_path: Path to the original image
            
        Returns:
            Path to prepared image or None if error occurs
        """
        try:
            # First resize if needed
            resized_path = ImageProcessor.resize_image_if_needed(image_path)
            if not resized_path:
                return None
            
            # Then convert to JPEG
            jpeg_path = ImageProcessor.convert_to_jpeg(resized_path)
            
            # Clean up temporary resized file if it's different from original
            if resized_path != image_path and resized_path != jpeg_path:
                try:
                    os.remove(resized_path)
                except OSError:
                    pass
            
            return jpeg_path
            
        except Exception as e:
            logger.error(f"Error preparing image for API {image_path}: {str(e)}")
            return None
    
    @staticmethod
    def downscale_for_detection(image_path: str, min_plate_height: int = 30,
                                plate_height_fraction: float = 0.05) -> Optional[str]:
        """
        Downscale image for Phase 1 detection, maintaining aspect ratio.
        
        Scales so that a plate occupying plate_height_fraction of the image height
        is at least min_plate_height pixels tall in the downscaled result.
        
        Args:
            image_path: Path to the original image
            min_plate_height: Minimum plate height in pixels after downscaling
            plate_height_fraction: Assumed plate height as fraction of image height
                (0.05 = plate is 5% of image height, conservative for small/distant plates)
            
        Returns:
            Path to downscaled image or None if error occurs
        """
        try:
            with Image.open(image_path) as img:
                min_image_height = min_plate_height / plate_height_fraction
                aspect = img.width / img.height
                max_dimension = min_image_height * max(aspect, 1.0)
                max_dimension = max(max_dimension, min_image_height)
                
                if img.width <= max_dimension and img.height <= max_dimension:
                    return image_path
                
                ratio = min(max_dimension / img.width, max_dimension / img.height)
                new_width = int(img.width * ratio)
                new_height = int(img.height * ratio)
                
                logger.info(
                    f"Downscaling image from {img.width}x{img.height} to "
                    f"{new_width}x{new_height} for detection "
                    f"(min_plate_height={min_plate_height}, "
                    f"plate_height_fraction={plate_height_fraction})"
                )
                
                downscaled_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                base_name, ext = os.path.splitext(image_path)
                downscaled_path = f"{base_name}_downscale{ext}"
                
                downscaled_img.save(downscaled_path, quality=85)
                
                return downscaled_path
                
        except Exception as e:
            logger.error(f"Error downscaling image {image_path}: {str(e)}")
            return None
    
    @staticmethod
    def crop_region(image_path: str, x1: int, y1: int, x2: int, y2: int, 
                   padding_pct: float = 0.1) -> Optional[Tuple[str, int, int]]:
        """
        Crop a region from the image with optional padding.
        
        Args:
            image_path: Path to the original image
            x1, y1, x2, y2: Bounding box coordinates
            padding_pct: Percentage of box size to add as padding (0.0 to 1.0)
            
        Returns:
            Tuple of (crop_path, crop_offset_x, crop_offset_y) or None if error
        """
        try:
            with Image.open(image_path) as img:
                # Calculate padding
                box_width = x2 - x1
                box_height = y2 - y1
                padding_x = int(box_width * padding_pct)
                padding_y = int(box_height * padding_pct)
                
                # Apply padding
                crop_x1 = max(0, x1 - padding_x)
                crop_y1 = max(0, y1 - padding_y)
                crop_x2 = min(img.width, x2 + padding_x)
                crop_y2 = min(img.height, y2 + padding_y)
                
                logger.info(f"Cropping region: ({crop_x1},{crop_y1}) to ({crop_x2},{crop_y2}) with padding {padding_pct}")
                
                # Crop the image
                cropped_img = img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
                
                # Generate new filename
                base_name, ext = os.path.splitext(image_path)
                crop_path = f"{base_name}_crop_{x1}_{y1}{ext}"
                
                # Save cropped image
                cropped_img.save(crop_path, quality=95)
                
                return (crop_path, crop_x1, crop_y1)
                
        except Exception as e:
            logger.error(f"Error cropping region from {image_path}: {str(e)}")
            return None
