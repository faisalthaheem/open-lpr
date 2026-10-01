import json
import logging
import time
from functools import lru_cache
from typing import Any

from django.conf import settings
from openai import OpenAI

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

        if not self.api_key:
            raise ValueError("QWEN_API_KEY is not configured in settings")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        logger.info(f"QwenVLClient initialized with model: {self.model}")

    def analyze_image(self, base64_image: str, prompt: str) -> str | None:
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

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ]

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=4096,
                temperature=0.1,  # Low temperature for consistent results
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
                model=self.model, messages=[{"role": "user", "content": test_prompt}], max_tokens=10
            )

            return response.choices[0].message.content is not None

        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False

    def analyze_images_batch(self, base64_images: list[str], prompt: str) -> list[str | None]:
        """
        Send multiple images with prompt to Qwen3-VL for analysis

        Each image is sent independently so that a failure on one plate crop does not
        discard results already obtained for the others. A failed position is reported
        as ``None`` in the returned list.

        Args:
            base64_images: List of base64 encoded image strings
            prompt: Text prompt for the model

        Returns:
            List of model response texts, same length as ``base64_images``, with ``None``
            in positions whose request failed.
        """
        start_time = time.time()

        results: list[str | None] = []
        failures = 0

        for base64_image in base64_images:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ]

            try:
                response = self.client.chat.completions.create(
                    model=self.model, messages=messages, max_tokens=4096, temperature=0.1
                )
                results.append(response.choices[0].message.content)
            except Exception as e:
                failures += 1
                logger.error(f"Batch Qwen3-VL API call failed for one image: {str(e)}")
                results.append(None)

        duration = (time.time() - start_time) * 1000
        logger.info(
            f"Batch API call finished in {duration:.2f}ms: "
            f"{len(base64_images) - failures}/{len(base64_images)} succeeded"
        )

        return results


# Detection-only prompt template (Phase 1)
DETECTION_PROMPT = """Detect license plates in the attached image and respond with a JSON document with the
following structure. Analyze the actual image content and provide real detection results.
DO NOT copy example data - analyze the image and provide actual results.

{
    "filename": "[actual filename of the image]",
    "detections": [
        {
            "plate": {
                "confidence": 0.95,
                "coordinates": {
                    "x1": 100,
                    "y1": 200,
                    "x2": 400,
                    "y2": 300
                }
            }
        }
    ]
}

IMPORTANT INSTRUCTIONS:
1. Analyze the ACTUAL image provided
2. Detect ALL license plates in the image
3. Do NOT extract text - only detect license plate bounding boxes
4. Provide REAL coordinates that match the image content
5. Use the actual filename from the image
6. If no license plates are found, return an empty detections array: "detections": []
7. Be precise with coordinates - they should accurately bound the license plates"""


# OCR-only prompt template (Phase 2)
OCR_PROMPT = """Perform OCR on the attached image and respond with a JSON document with the following
structure. Analyze the actual image content and provide real results.
DO NOT copy example data - analyze the image and provide actual results.

{
    "text": "[actual license plate text you detect]",
    "confidence": 0.95,
    "coordinates": {
        "x1": 10,
        "y1": 10,
        "x2": 290,
        "y2": 90
    }
}

IMPORTANT INSTRUCTIONS:
1. Analyze the ACTUAL image provided
2. Extract the ACTUAL text from the license plate
3. Provide REAL coordinates that bound the detected text within the image
4. If no text is found, return an empty string for "text" and 0 for "confidence"
5. Be precise with coordinates - they should accurately bound the text"""


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


@lru_cache(maxsize=1)
def get_qwen_client() -> QwenVLClient:
    """
    Get a shared Qwen3-VL client instance.

    The client owns an httpx connection pool, so constructing one per request would
    pay for TCP/TLS setup on every OCR call and health check. A single instance is
    reused per process instead.

    ``lru_cache`` only stores successful returns, so a construction failure (for
    example a missing API key) raises on first call and is retried on the next call
    rather than being cached as a broken client.

    Returns:
        QwenVLClient instance
    """
    return QwenVLClient()


def reset_qwen_client() -> None:
    """
    Discard the cached client so the next call constructs a fresh one.

    Used by tests that need to change client configuration, and after settings that
    the client reads at construction time change.
    """
    get_qwen_client.cache_clear()


def _extract_json_text(response_text: str) -> str:
    """
    Extract the JSON payload from a model response.

    Models wrap JSON in markdown code fences of varying quality. This handles a
    ```` ```json ```` fence, a bare ```` ``` ```` fence, a bare JSON body, and the
    case where an opening fence is never closed.

    Args:
        response_text: Raw response text from the API

    Returns:
        The candidate JSON text, stripped of surrounding whitespace.
    """
    text = response_text.strip()

    if "```json" in text:
        start = text.find("```json") + len("```json")
    elif "```" in text:
        start = text.find("```") + 3
    else:
        return text

    end = text.find("```", start)
    if end == -1:
        # Unterminated fence: the payload runs to the end of the response. Taking
        # text[start:-1] here would silently drop the final character.
        return text[start:].strip()

    return text[start:end].strip()


def parse_lpr_response(
    response_text: str,
    original_h: int | None = None,
    original_w: int | None = None,
    resized_h: int | None = None,
    resized_w: int | None = None,
) -> dict[str, Any] | None:
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
        json_text = _extract_json_text(response_text)

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


def scale_coordinates_in_response(
    data: dict[str, Any], original_h: int, original_w: int, resized_h: int | None = None, resized_w: int | None = None
) -> dict[str, Any]:
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
    if "detections" not in data:
        return data

    detections = data["detections"]

    # `detections` is always a JSON array in the supported schema.
    if isinstance(detections, list):
        for detection in detections:
            scale_detection_coordinates(detection, original_h, original_w, resized_h, resized_w)

    return data


def scale_detection_coordinates(
    detection: dict[str, Any],
    original_h: int,
    original_w: int,
    resized_h: int | None = None,
    resized_w: int | None = None,
) -> None:
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
    if "plate" in detection and "coordinates" in detection["plate"]:
        coords = detection["plate"]["coordinates"]
        if all(key in coords for key in ["x1", "y1", "x2", "y2"]):
            bbox = [coords["x1"], coords["y1"], coords["x2"], coords["y2"]]
            scaled_bbox = convert_from_qwen2vl_format(bbox, original_h, original_w, resized_h, resized_w)
            coords["x1"], coords["y1"], coords["x2"], coords["y2"] = scaled_bbox

    # Scale OCR coordinates. `ocr` is a JSON array in the supported schema.
    for ocr_item in detection.get("ocr") or []:
        if isinstance(ocr_item, dict) and "coordinates" in ocr_item:
            coords = ocr_item["coordinates"]
            if all(key in coords for key in ["x1", "y1", "x2", "y2"]):
                bbox = [coords["x1"], coords["y1"], coords["x2"], coords["y2"]]
                scaled_bbox = convert_from_qwen2vl_format(bbox, original_h, original_w, resized_h, resized_w)
                coords["x1"], coords["y1"], coords["x2"], coords["y2"] = scaled_bbox


def parse_detection_response(
    response_text: str,
    original_h: int | None = None,
    original_w: int | None = None,
    resized_h: int | None = None,
    resized_w: int | None = None,
) -> dict[str, Any] | None:
    """
    Parse the detection response from Phase 1 (plate detection only, no OCR)

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
        json_text = _extract_json_text(response_text)

        # Parse the JSON
        parsed_data = json.loads(json_text)

        # Scale coordinates if image dimensions are provided
        if original_h is not None and original_w is not None:
            parsed_data = scale_coordinates_in_response(parsed_data, original_h, original_w, resized_h, resized_w)

        logger.info("Successfully parsed detection response")
        return parsed_data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse detection JSON response: {str(e)}")
        logger.debug(f"Response text: {response_text}")
        return None
    except Exception as e:
        logger.error(f"Error parsing detection response: {str(e)}")
        return None


def parse_ocr_response(
    response_text: str, crop_h: int, crop_w: int, crop_offset_x: int, crop_offset_y: int
) -> dict[str, Any] | None:
    """
    Parse the OCR response from Phase 2 and scale coordinates back to original image

    Args:
        response_text: Raw response text from the API
        crop_h: Height of the cropped image
        crop_w: Width of the cropped image
        crop_offset_x: X offset of crop in original image
        crop_offset_y: Y offset of crop in original image

    Returns:
        Parsed OCR data with coordinates scaled to original image or None if parsing fails
    """
    try:
        json_text = _extract_json_text(response_text)

        # Parse the JSON
        parsed_data = json.loads(json_text)

        # Scale coordinates from crop space to original image space
        if "coordinates" in parsed_data:
            coords = parsed_data["coordinates"]
            if all(key in coords for key in ["x1", "y1", "x2", "y2"]):
                # Convert from 0-1000 range to crop dimensions
                bbox = [coords["x1"], coords["y1"], coords["x2"], coords["y2"]]
                scaled_bbox = convert_from_qwen2vl_format(bbox, crop_h, crop_w)

                # Add crop offset to get coordinates in original image
                coords["x1"] = scaled_bbox[0] + crop_offset_x
                coords["y1"] = scaled_bbox[1] + crop_offset_y
                coords["x2"] = scaled_bbox[2] + crop_offset_x
                coords["y2"] = scaled_bbox[3] + crop_offset_y

        logger.info("Successfully parsed OCR response")
        return parsed_data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OCR JSON response: {str(e)}")
        logger.debug(f"Response text: {response_text}")
        return None
    except Exception as e:
        logger.error(f"Error parsing OCR response: {str(e)}")
        return None
