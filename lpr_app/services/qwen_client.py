import json
import logging
import time
from typing import Optional, Dict, Any
from openai import OpenAI, DefaultHttpxClient
from django.conf import settings

logger = logging.getLogger(__name__)


class QwenVLClient:
    """
    Client for interacting with Qwen3-VL API using OpenAI-compatible interface
    """
    
    def __init__(self):
        """Initialize the Qwen3-VL client"""
        self.api_key = settings.QWEN_API_KEY
        self.base_url = settings.QWEN_BASE_URL
        self.model = settings.QWEN_MODEL
        
        # Add diagnostic logging
        logger.info(f"DEBUG: API Key configured: {bool(self.api_key)}")
        logger.info(f"DEBUG: Base URL: {self.base_url}")
        logger.info(f"DEBUG: Model: {self.model}")
        
        if not self.api_key:
            raise ValueError("QWEN_API_KEY is not configured in settings")
        
        # Create httpx client to avoid proxies parameter issue
        # This fixes the compatibility issue between OpenAI and httpx
        http_client = DefaultHttpxClient()
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            http_client=http_client
        )
        
        logger.info(f"QwenVLClient initialized with model: {self.model}")
    
    def analyze_image(self, base64_image: str, prompt: str) -> Optional[str]:
        """
        Send image and prompt to Qwen3-VL for analysis
        
        Args:
            base64_image: Base64 encoded image string
            prompt: Text prompt for the model
            
        Returns:
            Model response text or None if error occurs
        """
        try:
            start_time = time.time()
            
            messages = [{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    },
                    {"type": "text", "text": prompt}
                ]
            }]
            
            logger.info(f"DEBUG: Sending request to Qwen3-VL API")
            logger.info(f"DEBUG: Base URL: {self.base_url}")
            logger.info(f"DEBUG: Model: {self.model}")
            logger.info(f"DEBUG: Full endpoint: {self.base_url}/chat/completions")
            logger.info(f"DEBUG: API Key present: {bool(self.api_key)}")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=4096,
                temperature=0.1  # Low temperature for consistent results
            )
            
            duration = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            result = response.choices[0].message.content
            logger.info(f"API call completed successfully in {duration:.2f}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"Error calling Qwen3-VL API: {str(e)}")
            return None
    
    def health_check(self) -> bool:
        """
        Check if the API is accessible
        
        Returns:
            True if API is accessible, False otherwise
        """
        try:
            # Send a simple test request
            test_prompt = "Hello, can you respond with 'OK'?"
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": test_prompt}],
                max_tokens=10
            )
            
            return response.choices[0].message.content is not None
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False


# LPR prompt template for license plate recognition
LPR_PROMPT = """Perform ocr on the attached image and respond with a JSON document with the following structure. Replace the sample values with actual bounding boxes for the image, scale back to the original image dimensions if necessary. IMPORTANT: be accurate, the coordinates of bounding boxes must be correct so that they can be verified using any measuring tools.
{
    "filename": "jeep.jpg",
    "detections": [
        "1234" : {
            "plate": {
                "confidence": 0.8,
                "coordinates": {
                    "x1": 1,
                    "y1": 2,
                    "x2": 20,
                    "y2": 10
                }
            },
            "ocr": [
            "123456": {
                "confidence": 0.8,
                "coordinates": {
                    "x1": 1,
                    "y1": 2,
                    "x2": 20,
                    "y2": 10
                }
            },
            "abcdef": {
                "confidence": 0.8,
                "coordinates": {
                    "x1": 1,
                    "y1": 2,
                    "x2": 20,
                    "y2": 10
                }
            }
            ]
            
        }
    ]
}"""


def convert_from_qwen2vl_format(bbox, original_h, original_w, resized_h=None, resized_w=None):
    """
    Convert coordinates from Qwen2VL format (0-1000) back to original image dimensions.
    This reverses the convert_to_qwen2vl_format function.
    
    Args:
        bbox: List of [x1, y1, x2, y2] coordinates in 0-1000 range
        original_h: Original image height
        original_w: Original image width
        resized_h: Height of image sent to API (if resized, defaults to original_h)
        resized_w: Width of image sent to API (if resized, defaults to original_w)
        
    Returns:
        List of [x1, y1, x2, y2] coordinates in original image dimensions
    """
    if resized_h is None:
        resized_h = original_h
    if resized_w is None:
        resized_w = original_w
    
    x1_norm, y1_norm, x2_norm, y2_norm = bbox
    
    # Convert from 0-1000 range directly to original image dimensions
    # The key insight is that the 0-1000 range represents the original image aspect ratio
    # regardless of the actual resized dimensions sent to the API
    x1_original = round(x1_norm / 1000 * original_w)
    y1_original = round(y1_norm / 1000 * original_h)
    x2_original = round(x2_norm / 1000 * original_w)
    y2_original = round(y2_norm / 1000 * original_h)
    
    # Ensure coordinates are within image bounds
    x1_original = max(0, min(x1_original, original_w))
    y1_original = max(0, min(y1_original, original_h))
    x2_original = max(0, min(x2_original, original_w))
    y2_original = max(0, min(y2_original, original_h))
    
    return [x1_original, y1_original, x2_original, y2_original]


def get_qwen_client() -> QwenVLClient:
    """
    Get a configured Qwen3-VL client instance
    
    Returns:
        QwenVLClient instance
    """
    return QwenVLClient()


def parse_lpr_response(response_text: str, original_h: Optional[int] = None, original_w: Optional[int] = None,
                       resized_h: Optional[int] = None, resized_w: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Parse the LPR response from Qwen3-VL and scale coordinates back to original image dimensions
    
    Args:
        response_text: Raw response text from the API
        original_h: Original image height
        original_w: Original image width
        resized_h: Height of image sent to API (if resized)
        resized_w: Width of image sent to API (if resized)
        
    Returns:
        Parsed JSON data with scaled coordinates or None if parsing fails
    """
    try:
        # Try to extract JSON from the response
        # The response might contain markdown code blocks
        if '```json' in response_text:
            # Extract JSON from markdown code block
            start = response_text.find('```json') + 7
            end = response_text.find('```', start)
            json_text = response_text[start:end].strip()
        elif '```' in response_text:
            # Extract JSON from generic code block
            start = response_text.find('```') + 3
            end = response_text.find('```', start)
            json_text = response_text[start:end].strip()
        else:
            # Assume the entire response is JSON
            json_text = response_text.strip()
        
        # Parse the JSON
        parsed_data = json.loads(json_text)
        
        # Scale coordinates if image dimensions are provided
        if original_h is not None and original_w is not None:
            parsed_data = scale_coordinates_in_response(parsed_data, original_h, original_w, resized_h, resized_w)
        
        logger.info("Successfully parsed LPR response")
        return parsed_data
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {str(e)}")
        logger.debug(f"Response text: {response_text}")
        return None
    except Exception as e:
        logger.error(f"Error parsing LPR response: {str(e)}")
        return None


def scale_coordinates_in_response(data: Dict[str, Any], original_h: int, original_w: int,
                                 resized_h: Optional[int] = None, resized_w: Optional[int] = None) -> Dict[str, Any]:
    """
    Scale all coordinates in the LPR response from 0-1000 range to original image dimensions
    
    Args:
        data: Parsed LPR response data
        original_h: Original image height
        original_w: Original image width
        resized_h: Height of image sent to API (if resized)
        resized_w: Width of image sent to API (if resized)
        
    Returns:
        Data with scaled coordinates
    """
    if 'detections' not in data:
        return data
    
    detections = data['detections']
    
    # Handle both list and dictionary formats
    if isinstance(detections, list):
        for detection in detections:
            scale_detection_coordinates(detection, original_h, original_w, resized_h, resized_w)
    elif isinstance(detections, dict):
        for detection_key in detections:
            scale_detection_coordinates(detections[detection_key], original_h, original_w, resized_h, resized_w)
    
    return data


def scale_detection_coordinates(detection: Dict[str, Any], original_h: int, original_w: int,
                               resized_h: Optional[int] = None, resized_w: Optional[int] = None) -> None:
    """
    Scale coordinates for a single detection
    
    Args:
        detection: Detection data with coordinates
        original_h: Original image height
        original_w: Original image width
        resized_h: Height of image sent to API (if resized)
        resized_w: Width of image sent to API (if resized)
    """
    # Scale plate coordinates
    if 'plate' in detection and 'coordinates' in detection['plate']:
        coords = detection['plate']['coordinates']
        if all(key in coords for key in ['x1', 'y1', 'x2', 'y2']):
            bbox = [coords['x1'], coords['y1'], coords['x2'], coords['y2']]
            scaled_bbox = convert_from_qwen2vl_format(bbox, original_h, original_w, resized_h, resized_w)
            coords['x1'], coords['y1'], coords['x2'], coords['y2'] = scaled_bbox
    
    # Scale OCR coordinates
    if 'ocr' in detection:
        ocr_data = detection['ocr']
        if isinstance(ocr_data, list):
            for ocr_item in ocr_data:
                if isinstance(ocr_item, dict) and 'coordinates' in ocr_item:
                    coords = ocr_item['coordinates']
                    if all(key in coords for key in ['x1', 'y1', 'x2', 'y2']):
                        bbox = [coords['x1'], coords['y1'], coords['x2'], coords['y2']]
                        scaled_bbox = convert_from_qwen2vl_format(bbox, original_h, original_w, resized_h, resized_w)
                        coords['x1'], coords['y1'], coords['x2'], coords['y2'] = scaled_bbox
        elif isinstance(ocr_data, dict):
            for ocr_key in ocr_data:
                ocr_item = ocr_data[ocr_key]
                if isinstance(ocr_item, dict) and 'coordinates' in ocr_item:
                    coords = ocr_item['coordinates']
                    if all(key in coords for key in ['x1', 'y1', 'x2', 'y2']):
                        bbox = [coords['x1'], coords['y1'], coords['x2'], coords['y2']]
                        scaled_bbox = convert_from_qwen2vl_format(bbox, original_h, original_w, resized_h, resized_w)
                        coords['x1'], coords['y1'], coords['x2'], coords['y2'] = scaled_bbox