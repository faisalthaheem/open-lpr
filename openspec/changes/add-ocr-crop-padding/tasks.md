## 1. Settings

- [x] 1.1 Add `OCR_CROP_PADDING_PX` setting to `lpr_project/settings.py` with default value `25`, loaded via `config()` from `python-decouple` (int type)

## 2. Image Processor

- [x] 2.1 Add optional `padding_px` parameter to `ImageProcessor.crop_region()` in `lpr_app/services/image_processor.py` — when provided, compute padding as the fixed pixel value per side instead of percentage-based, and clamp each side independently to image boundaries
- [x] 2.2 Update the method's docstring to document the new `padding_px` parameter and its precedence over `padding_pct`

## 3. Pipeline Integration

- [x] 3.1 Update the Phase 2 crop call in `lpr_app/services/image_processing_service.py` to import the `OCR_CROP_PADDING_PX` setting and pass it as `padding_px` to `crop_region()` instead of `padding_pct=0.1`

## 4. Verification

- [x] 4.1 Run `python manage.py runserver` and test with an uploaded image to confirm Phase 2 crops include the configured pixel padding
- [x] 4.2 Test edge case: upload an image with a plate near the boundary to verify padding is clamped correctly
