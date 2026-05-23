## Context

The LPR pipeline uses a two-phase approach: Phase 1 detects license plate bounding boxes, Phase 2 crops those regions and runs OCR. Currently, `ImageProcessor.crop_region()` in `image_processor.py` adds padding as a percentage of the bounding box size (default 10%). The Phase 2 caller in `image_processing_service.py` invokes this with `padding_pct=0.1`.

The change replaces this percentage-based padding with a fixed-pixel approach for Phase 2 crops, controlled by a Django setting. The existing percentage-based API must remain available for any other callers.

## Goals / Non-Goals

**Goals:**
- Provide consistent, predictable context around cropped plates for OCR
- Make padding configurable via Django settings without code changes
- Clamp padding to image boundaries gracefully

**Non-Goals:**
- Changing Phase 1 detection behavior
- Changing the OCR prompt or response parsing
- Modifying the bounding box visualizer
- Adding per-side configurable padding amounts

## Decisions

### 1. Fixed-pixel padding over percentage-based
**Decision**: Use absolute pixel values (default 25px) instead of a percentage of box size.
**Rationale**: A percentage gives variable context — small plates get ~10px, large plates get ~50px. A fixed pixel value provides consistent surrounding context to the OCR model regardless of plate size.
**Alternative considered**: Keep percentage but increase it — rejected because it still varies with box size.

### 2. Parameter addition to existing `crop_region()` method
**Decision**: Add an optional `padding_px` parameter to `crop_region()`. When provided, it takes precedence over `padding_pct`.
**Rationale**: Minimal API change, backward-compatible. Existing callers that use `padding_pct` continue to work unchanged.
**Alternative considered**: Create a separate method — rejected to avoid duplication.

### 3. Django setting for configuration
**Decision**: Add `OCR_CROP_PADDING_PX` to `settings.py` with default value `25`.
**Rationale**: Follows the existing pattern of configurable parameters in settings (e.g., `UPLOAD_FILE_MAX_SIZE`). Can be overridden via environment variable using `python-decouple`.

### 4. Per-side boundary clamping
**Decision**: Each side is independently clamped using `max(0, ...)` and `min(img.width/height, ...)`.
**Rationale**: This is already the pattern used by the current percentage-based implementation. Plates near edges get whatever padding is available.

## Risks / Trade-offs

- **Risk**: 25px default may not be optimal for all image resolutions → Mitigation: configurable via setting, easy to tune without code changes.
- **Risk**: Very small images where 25px exceeds box dimensions → Mitigation: clamping ensures crop region never exceeds image boundaries; the crop will simply be the full image if the box plus padding covers everything.
