## Why

OCR text labels drawn on processed images use a fixed 14px font (or PIL's tiny default bitmap font), making them unreadable on anything but the smallest images. As camera resolutions increase, the rendered text becomes microscopic relative to the detected plate, undermining the visual feedback the annotations are meant to provide.

## What Changes

- Scale the annotation font size proportionally to the source image dimensions so labels remain legible at any resolution.
- Attempt to load a scalable TrueType font at the computed size; fall back gracefully when no TrueType font is available.
- Ensure the label background rectangle and text positioning account for the dynamic font size.

## Capabilities

### New Capabilities

- `dynamic-font-scaling`: Compute font size as a fraction of image dimensions, select a usable TrueType or default font at that size, and adjust label rendering (background rect, text position) accordingly.

### Modified Capabilities

## Impact

- `lpr_app/services/bbox_visualizer.py` — font loading logic, `draw_bounding_box` label rendering, `__init__` font selection.
- No API, model, or dependency changes.
- Processed images will have larger, more readable OCR annotations; no functional behavior change.
