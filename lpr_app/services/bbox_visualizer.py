import logging
import os
from typing import Dict, Any, List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings

logger = logging.getLogger(__name__)


class BoundingBoxVisualizer:
    """
    Service for drawing bounding boxes on images based on LPR detection results
    """
    
    # Colors for different types of detections
    COLORS = {
        'plate': (255, 0, 0),      # Red for license plates
        'ocr': (0, 255, 0),        # Green for OCR text
        'text': (0, 0, 255),        # Blue for general text
    }
    
    # Default font sizes
    FONT_SIZES = {
        'small': 12,
        'medium': 16,
        'large': 20,
    }
    
    def __init__(self, image_path: str):
        """
        Initialize the visualizer with an image path
        
        Args:
            image_path: Path to the image file
        """
        self.image_path = image_path
        self.image = None
        self.draw = None
        self.font = None
        
        try:
            self.image = Image.open(image_path)
            self.draw = ImageDraw.Draw(self.image)
            
            # Try to load a font, fallback to default if not available
            try:
                self.font = ImageFont.truetype("arial.ttf", 14)
            except (OSError, IOError):
                try:
                    # Try system fonts
                    self.font = ImageFont.load_default()
                except:
                    self.font = None
                    
            logger.info(f"Initialized visualizer for image: {image_path}")
            
        except Exception as e:
            logger.error(f"Error loading image {image_path}: {str(e)}")
            raise
    
    def draw_bounding_box(self, x1: Optional[int] = None, y1: Optional[int] = None, width: Optional[int] = None, height: Optional[int] = None,
                          x2: Optional[int] = None, y2: Optional[int] = None, color: Tuple[int, int, int] = (255, 0, 0),
                          thickness: int = 2, label: str = "") -> None:
        """
        Draw a single bounding box on the image
        
        Args:
            x1, y1: Top-left corner coordinates (for x1,y1,x2,y2 format)
            x2, y2: Bottom-right corner coordinates (for x1,y1,x2,y2 format)
            width, height: Box dimensions (for x,y,w,h format - deprecated)
            color: RGB color tuple
            thickness: Line thickness
            label: Optional label to display above the box
        """
        if not self.draw:
            return
        
        # Handle both coordinate formats
        if x1 is not None and y1 is not None and x2 is not None and y2 is not None:
            # New x1,y1,x2,y2 format
            rect_coords = [x1, y1, x2, y2]
            x, y = x1, y1  # For label positioning
        elif x1 is not None and y1 is not None and width is not None and height is not None:
            # Legacy x,y,w,h format
            rect_coords = [x1, y1, x1 + width, y1 + height]
        else:
            logger.warning("Invalid coordinates provided to draw_bounding_box")
            return
        
        # Draw the rectangle
        self.draw.rectangle(
            rect_coords,
            outline=color,
            width=thickness
        )
        
        # Draw label if provided
        if label and self.font:
            # Calculate text size
            try:
                bbox = self.draw.textbbox((0, 0), label, font=self.font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
            except:
                # Fallback for older PIL versions
                text_width, text_height = self.draw.textsize(label, font=self.font) if self.font else (len(label) * 8, 16)
            
            # Draw background for text
            label_y = max(0, y - text_height - 4)
            self.draw.rectangle(
                [x, label_y, x + text_width + 4, label_y + text_height + 4],
                fill=color
            )
            
            # Draw text
            self.draw.text(
                (x + 2, label_y + 2),
                label,
                fill=(255, 255, 255),  # White text
                font=self.font
            )
    
    def draw_plate_detection(self, plate_data: Dict[str, Any]) -> None:
        """
        Draw a license plate detection with its OCR results
        
        Args:
            plate_data: Dictionary containing plate and OCR information
        """
        if 'plate' not in plate_data:
            return
        
        plate_info = plate_data['plate']
        coords = plate_info.get('coordinates', {})
        confidence = plate_info.get('confidence', 0)
        
        # Extract coordinates - handle both old and new formats
        if all(key in coords for key in ['x1', 'y1', 'x2', 'y2']):
            # New x1,y1,x2,y2 format
            x1 = int(coords.get('x1', 0))
            y1 = int(coords.get('y1', 0))
            x2 = int(coords.get('x2', 0))
            y2 = int(coords.get('y2', 0))
            
            # Draw plate bounding box
            label = f"Plate ({confidence:.2f})"
            self.draw_bounding_box(
                x1=x1, y1=y1, x2=x2, y2=y2,
                color=self.COLORS['plate'],
                thickness=3,
                label=label
            )
        else:
            # Legacy x,y,w,h format
            x = int(coords.get('x', 0))
            y = int(coords.get('y', 0))
            width = int(coords.get('w', 0))
            height = int(coords.get('h', 0))
            
            # Draw plate bounding box
            label = f"Plate ({confidence:.2f})"
            self.draw_bounding_box(
                x1=x, y1=y, width=width, height=height,
                color=self.COLORS['plate'],
                thickness=3,
                label=label
            )
        
        # Draw OCR results if available
        if 'ocr' in plate_data:
            self.draw_ocr_results(plate_data['ocr'])
    
    def draw_ocr_results(self, ocr_data: List[Dict[str, Any]]) -> None:
        """
        Draw OCR text detections
        
        Args:
            ocr_data: List of OCR detection dictionaries
        """
        logger.info(f"DEBUG: OCR data type: {type(ocr_data)}")
        logger.info(f"DEBUG: OCR data content: {ocr_data}")
        
        for ocr_item in ocr_data:
            if not isinstance(ocr_item, dict):
                logger.warning(f"Skipping non-dict OCR item: {ocr_item}")
                continue
            
            # Handle new API format: {'text': 'value', 'confidence': 0.95, 'coordinates': {...}}
            if 'text' in ocr_item:
                ocr_text = ocr_item.get('text', '')
                coords = ocr_item.get('coordinates', {})
                confidence = ocr_item.get('confidence', 0)
            else:
                # Handle old format: {'text_value': {'confidence': 0.95, 'coordinates': {...}}}
                ocr_text = list(ocr_item.keys())[0] if ocr_item else ""
                ocr_info = ocr_item.get(ocr_text, {}) if ocr_text else {}
                coords = ocr_info.get('coordinates', {})
                confidence = ocr_info.get('confidence', 0)
            
            logger.info(f"DEBUG: Processing OCR text: '{ocr_text}' at coords: {coords}")
            
            # Extract coordinates - handle both old and new formats
            if all(key in coords for key in ['x1', 'y1', 'x2', 'y2']):
                # New x1,y1,x2,y2 format
                x1 = int(coords.get('x1', 0))
                y1 = int(coords.get('y1', 0))
                x2 = int(coords.get('x2', 0))
                y2 = int(coords.get('y2', 0))
                
                # Draw OCR bounding box
                label = f"{ocr_text} ({confidence:.2f})"
                self.draw_bounding_box(
                    x1=x1, y1=y1, x2=x2, y2=y2,
                    color=self.COLORS['ocr'],
                    thickness=2,
                    label=label
                )
            else:
                # Legacy x,y,w,h format
                x = int(coords.get('x', 0))
                y = int(coords.get('y', 0))
                width = int(coords.get('w', 0))
                height = int(coords.get('h', 0))
                
                # Draw OCR bounding box
                label = f"{ocr_text} ({confidence:.2f})"
                self.draw_bounding_box(
                    x1=x, y1=y, width=width, height=height,
                    color=self.COLORS['ocr'],
                    thickness=2,
                    label=label
                )
    
    def visualize_lpr_results(self, lpr_data: Dict[str, Any]) -> None:
        """
        Visualize complete LPR detection results
        
        Args:
            lpr_data: Complete LPR response data
        """
        if not lpr_data or 'detections' not in lpr_data:
            logger.warning("No detections found in LPR data")
            return
        
        detections = lpr_data['detections']
        
        # Add diagnostic logging
        logger.info(f"DEBUG: detections type: {type(detections)}")
        logger.info(f"DEBUG: detections content: {detections}")
        
        # Handle both list and dictionary formats
        if isinstance(detections, list):
            # Process as list
            for i, detection_data in enumerate(detections):
                try:
                    logger.info(f"DEBUG: Processing detection {i}: {detection_data}")
                    self.draw_plate_detection(detection_data)
                except Exception as e:
                    logger.error(f"Error drawing detection {i}: {str(e)}")
        elif isinstance(detections, dict):
            # Process as dictionary (original format)
            for detection_key, detection_data in detections.items():
                try:
                    logger.info(f"DEBUG: Processing detection {detection_key}: {detection_data}")
                    self.draw_plate_detection(detection_data)
                except Exception as e:
                    logger.error(f"Error drawing detection {detection_key}: {str(e)}")
        else:
            logger.error(f"Unexpected detections format: {type(detections)}")
            return
        
        detection_count = len(detections) if isinstance(detections, (list, dict)) else 0
        logger.info(f"Visualized {detection_count} detections")
    
    def save_result(self, output_path: str, quality: int = 95) -> bool:
        """
        Save the annotated image
        
        Args:
            output_path: Path to save the result
            quality: JPEG quality (1-100)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save the image
            if self.image.mode in ('RGBA', 'LA', 'P'):
                # Convert to RGB for JPEG compatibility
                rgb_image = Image.new('RGB', self.image.size, (255, 255, 255))
                if self.image.mode == 'P':
                    self.image = self.image.convert('RGBA')
                rgb_image.paste(self.image, mask=self.image.split()[-1] if self.image.mode == 'RGBA' else None)
                rgb_image.save(output_path, 'JPEG', quality=quality)
            else:
                self.image.save(output_path, 'JPEG', quality=quality)
            
            logger.info(f"Saved annotated image to: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving annotated image: {str(e)}")
            return False
    
    def get_image_size(self) -> Tuple[int, int]:
        """
        Get the current image dimensions
        
        Returns:
            Tuple of (width, height)
        """
        if self.image:
            return (self.image.width, self.image.height)
        return (0, 0)


def visualize_lpr_on_image(image_path: str, lpr_data: Dict[str, Any], 
                        output_path: str) -> bool:
    """
    Convenience function to visualize LPR results on an image
    
    Args:
        image_path: Path to the original image
        lpr_data: LPR detection results
        output_path: Path to save the annotated image
        
    Returns:
        True if successful, False otherwise
    """
    try:
        visualizer = BoundingBoxVisualizer(image_path)
        visualizer.visualize_lpr_results(lpr_data)
        return visualizer.save_result(output_path)
        
    except Exception as e:
        logger.error(f"Error in visualize_lpr_on_image: {str(e)}")
        return False


def create_side_by_side_comparison(original_path: str, annotated_path: str, 
                            output_path: str) -> bool:
    """
    Create a side-by-side comparison of original and annotated images
    
    Args:
        original_path: Path to original image
        annotated_path: Path to annotated image
        output_path: Path to save the comparison
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Open both images
        with Image.open(original_path) as original_img, \
             Image.open(annotated_path) as annotated_img:
            
            # Get dimensions
            orig_width, orig_height = original_img.size
            ann_width, ann_height = annotated_img.size
            
            # Calculate new dimensions (same height, double width)
            new_height = max(orig_height, ann_height)
            new_width = orig_width + ann_width
            
            # Create new image
            comparison_img = Image.new('RGB', (new_width, new_height), (255, 255, 255))
            
            # Paste original on the left
            x_offset = 0
            y_offset = (new_height - orig_height) // 2
            comparison_img.paste(original_img, (x_offset, y_offset))
            
            # Paste annotated on the right
            x_offset = orig_width
            y_offset = (new_height - ann_height) // 2
            comparison_img.paste(annotated_img, (x_offset, y_offset))
            
            # Save comparison
            comparison_img.save(output_path, 'JPEG', quality=90)
            
            logger.info(f"Created side-by-side comparison: {output_path}")
            return True
            
    except Exception as e:
        logger.error(f"Error creating side-by-side comparison: {str(e)}")
        return False