## Context

`BoundingBoxVisualizer` (in `lpr_app/services/bbox_visualizer.py`) draws license plate bounding boxes and OCR text labels on processed images. The font is loaded once in `__init__` at a hardcoded 14px size (or PIL's 10px default bitmap font). On modern camera images (often 1920×1080 or larger), these labels are illegible — sometimes only a few pixels tall when displayed.

The class has no awareness of image dimensions when selecting font size. The label background rectangle and text positioning assume a fixed-size font, so any font size change must also update those calculations.

## Goals / Non-Goals

**Goals:**
- OCR annotation text SHALL be legible regardless of source image resolution.
- Font size SHALL scale proportionally to image dimensions.
- Solution SHALL work across environments (with or without TrueType fonts installed).

**Non-Goals:**
- Configurable font size overrides or per-request font sizing.
- Changing bounding box line thickness or colors.
- Replacing the PIL/Pillow drawing approach with a different rendering library.

## Decisions

**1. Scale font size based on image height**

Compute font size as `image_height * scale_factor` (e.g. 2%). This ties readability to the vertical dimension, which is the primary constraint for text legibility. Clamp to a minimum of 16px so even tiny images get readable text.

Alternatives considered:
- *Fixed lookup table by resolution tier*: More predictable but requires maintenance as resolutions change. Proportional scaling adapts automatically.
- *Scale by diagonal*: Slightly more robust across aspect ratios, but adds complexity for negligible benefit on typical landscape camera images.

**2. Try multiple TrueType font paths, fall back to PIL default**

Search a prioritized list of common font paths (`/usr/share/fonts/...`, DejaVu Sans, Liberation Sans, etc.) at the computed size. If none are found, use `ImageFont.load_default(size=...)` (Pillow >= 10.0 supports a size parameter for the default font). For older Pillow, use the default font as-is — it won't scale but is the best available fallback.

Alternatives considered:
- *Bundle a .ttf file*: Adds a binary asset to the repo. Unnecessary when most Linux environments and Docker images include at least one TTF font.
- *Require a font package*: Too strict a dependency for a visual annotation feature.

**3. Compute font size once in `__init__`, store on the instance**

The image dimensions are known at construction time, so computing the font once avoids recalculating it on every `draw_bounding_box` call. If the label background rect needs adjustment, it already queries `textbbox` per label, so it adapts automatically to whatever font size is loaded.

## Risks / Trade-offs

- **[PIL default font won't scale on Pillow < 10.0]** → Mitigation: Document the minimum Pillow version; the Docker image already uses a recent Pillow. Unscaled default font is still better than the current 14px hardcoded approach since the bounding box geometry still benefits.
- **[Very large images produce very large font sizes]** → Mitigation: Cap maximum font size at a reasonable upper bound (e.g. 64px) to prevent labels from overwhelming the image.
