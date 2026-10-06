"""
Validation utilities for LPR application.

This module contains common validation functions used across the application.
"""

import logging
import mimetypes
from typing import Any

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)


def check_image_dimensions(image_file: Any) -> tuple[bool, str | None]:
    """Reject images whose declared dimensions exceed the pixel budget.

    The check reads only the header. ``Image.open`` parses the dimensions
    without decompressing pixel data, so this costs a few hundred bytes of I/O
    and refuses the image before it can allocate anything -- which is the only
    point at which refusing is cheap.

    Bounding file size alone does not bound memory: a PNG of one flat colour
    compresses by roughly 3000:1, so a sub-megabyte upload can declare 144
    megapixels and cost 430MB of RAM once decoded. Pillow has its own guard but
    it only warns under 178 megapixels, which is well past what a plate photo
    needs, and it is a warning rather than a rejection.

    Accepts a file-like object or an already-open ``PIL.Image.Image``. Callers
    on the decode path already hold one, and re-opening it is both wasteful and
    wrong: a PIL image is not file-like and has no ``read``, so calling
    ``Image.open`` on one raises AttributeError rather than returning a verdict.
    That reached production as a 500 on every upload, because the tests covering
    this function only ever passed file-like objects and never the call site
    added alongside them.

    Returns (is_valid, error_message).
    """
    if isinstance(image_file, Image.Image):
        # Already open, so .size came from the header and cost nothing to parse.
        # This path is exactly as cheap as the file-like one.
        width, height = image_file.size
    else:
        try:
            with Image.open(image_file) as img:
                width, height = img.size
        except UnidentifiedImageError:
            # Not an image at all. Left for the caller's existing validity check
            # to report, so the user sees one message about undecodable files
            # rather than two.
            return True, None
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            # A header this malformed is the caller's "invalid image" case too.
            logger.warning("Could not read image header for dimension check: %s", exc)
            return True, None

    max_pixels = settings.UPLOAD_IMAGE_MAX_PIXELS
    pixels = width * height

    if max_pixels and pixels > max_pixels:
        megapixels = pixels / 1_000_000
        limit_megapixels = max_pixels / 1_000_000
        return (
            False,
            f"Image too large: {width}x{height} ({megapixels:.1f} megapixels). "
            f"Maximum is {limit_megapixels:.0f} megapixels.",
        )

    return True, None


class FileValidator:
    """Utility class for file validation operations."""

    @staticmethod
    def validate_image_file(uploaded_file: UploadedFile) -> tuple[bool, str | None]:
        """
        Validate an uploaded image file.

        Args:
            uploaded_file: The uploaded file to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not uploaded_file:
            return False, "No file provided"

        # Check file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB in bytes
        if uploaded_file.size > max_size:
            return False, f"File too large. Maximum size is 10MB, got {uploaded_file.size / (1024 * 1024):.1f}MB"

        # Check file size is not empty
        if uploaded_file.size == 0:
            return False, "File is empty"

        # Reject oversized pixel dimensions from the header, before anything is
        # decompressed. See check_image_dimensions for why file size is not a
        # sufficient bound on memory.
        is_valid, dimension_error = check_image_dimensions(uploaded_file)
        if not is_valid:
            return False, dimension_error

        # Validate file type
        content_type = uploaded_file.content_type or mimetypes.guess_type(uploaded_file.name)[0]
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/bmp", "image/webp"]

        if content_type not in allowed_types:
            return False, f'Unsupported file type: {content_type}. Allowed types: {", ".join(allowed_types)}'

        # Check file extension matches content type
        allowed_extensions = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]
        file_extension = uploaded_file.name.lower().split(".")[-1]
        if f".{file_extension}" not in allowed_extensions:
            return (
                False,
                f'Invalid file extension: .{file_extension}. Allowed extensions: {", ".join(allowed_extensions)}',
            )

        return True, None

    @staticmethod
    def validate_image_id(image_id: Any) -> tuple[bool, str | None]:
        """
        Validate image ID parameter.

        Args:
            image_id: The image ID to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not image_id:
            return False, "Image ID is required"

        try:
            image_id = int(image_id)
            if image_id <= 0:
                return False, "Image ID must be a positive integer"
        except (ValueError, TypeError):
            return False, "Invalid image ID format"

        return True, None

    @staticmethod
    def validate_image_type(image_type: str) -> tuple[bool, str | None]:
        """
        Validate image type parameter.

        Args:
            image_type: The image type to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not image_type:
            return False, "Image type is required"

        valid_types = ["original", "processed"]
        if image_type not in valid_types:
            return False, f'Invalid image type: {image_type}. Valid types: {", ".join(valid_types)}'

        return True, None


class FormValidator:
    """Utility class for form validation operations."""

    @staticmethod
    def validate_search_params(params: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate search parameters for image list.

        Args:
            params: Dictionary of search parameters

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate date range if both dates are provided
        date_from = params.get("date_from")
        date_to = params.get("date_to")

        if date_from and date_to:
            if date_from > date_to:
                return False, "From date cannot be later than to date"

        # Validate status
        status = params.get("processing_status")
        if status:
            valid_statuses = ["", "pending", "processing", "completed", "failed"]
            if status not in valid_statuses:
                return False, f"Invalid processing status: {status}"

        # Validate query length
        query = params.get("query", "")
        if len(query) > 100:
            return False, "Search query is too long (maximum 100 characters)"

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
        actual_value = request.META.get(f"HTTP_{header_key}")

        return actual_value == canary_header_value

    @staticmethod
    def validate_pagination_params(page: Any, per_page: Any) -> tuple[int, int, str | None]:
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
