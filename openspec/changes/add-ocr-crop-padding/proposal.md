## Why

Phase 2 of the LPR pipeline crops detected license plates from the original image before running OCR, but the current padding is a fixed 10% of the bounding box dimensions. This percentage-based approach provides too little context on small plates and too much on large ones. A fixed pixel-based padding (defaulting to 25px) gives the OCR model consistent surrounding context, improving recognition accuracy especially on tightly-cropped or edge-positioned plates.

## What Changes

- Replace the percentage-based padding (`padding_pct=0.1`) in the Phase 2 crop step with a configurable fixed-pixel padding (default 25px)
- Each side of the bounding box receives up to the configured pixels of padding, clamped to image boundaries (i.e., if less than the configured amount is available, use as much as available)
- Add a configurable setting (`OCR_CROP_PADDING_PX`) to control the padding amount without code changes
- Update `ImageProcessor.crop_region()` to accept a pixel-based padding parameter alongside the existing percentage-based one

## Capabilities

### New Capabilities
- `ocr-crop-padding`: Configurable fixed-pixel padding for Phase 2 OCR crop regions, with boundary clamping

### Modified Capabilities
<!-- No existing specs are modified -->

## Impact

- `lpr_app/services/image_processor.py` — `crop_region()` method signature and padding logic
- `lpr_app/services/image_processing_service.py` — Phase 2 crop call site, passing pixel padding
- `lpr_project/settings.py` — New `OCR_CROP_PADDING_PX` setting
- No API or database changes; backward-compatible default value
