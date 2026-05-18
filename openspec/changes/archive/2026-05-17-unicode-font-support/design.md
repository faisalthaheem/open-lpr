## Context

The `BoundingBoxVisualizer` in `bbox_visualizer.py` renders OCR text on images using PIL/Pillow's `ImageFont.truetype()`. It searches a hardcoded list of font paths and falls back to `ImageFont.load_default()` if none are found. The current font list only includes Latin-only fonts (DejaVu Sans, Liberation Sans, Ubuntu Sans). The Docker image (`python:3.11-slim`) does not install any font packages, so even these Latin fonts are unavailable in production.

## Goals / Non-Goals

**Goals:**
- Ensure OCR text renders correctly for Latin, Arabic, CJK (Japanese, Chinese, Korean), Hebrew, and other scripts in the Docker container.
- Fix the broken font rendering in Docker (currently falls back to a bitmap font with minimal glyph coverage).

**Non-Goals:**
- Right-to-left text layout for Arabic/Hebrew (PIL doesn't handle BiDi; text will render left-to-right but with correct glyphs).
- Font selection per script/language (use a single Unicode-capable font).
- Changing the visualization layout or bounding box logic.

## Decisions

**1. Install `fonts-noto` in the Docker image**

`fonts-noto` is the Debian/Ubuntu package for Google's Noto fonts, which provide broad Unicode coverage in a single font family. Adding it to the Dockerfile ensures the font is available in the container at a known path (`/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf`).

Alternatives considered:
- *Bundling a font file in the repo*: Adds a binary file to git, increases repo size. The Noto Sans Regular TTF is ~400KB. Viable but less maintainable than a package.
- *Downloading at build time*: Extra network dependency, slower builds, less reproducible.

**2. Prioritize Noto Sans in the font search path**

Move Noto Sans to the top of the `TTF_FONT_PATHS` list. Noto Sans Regular covers Latin, Arabic, CJK, and many other scripts in a single font file. If Noto is not available (e.g., dev environment without it installed), the existing fallback chain continues to DejaVu, Liberation, etc.

**3. Add Noto Sans CJK path as a fallback**

Noto Sans CJK (for Japanese/Chinese/Korean) is installed via the `fonts-noto-cjk` package at `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc` or `/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc`. Adding this path ensures CJK coverage even if the base Noto Sans font doesn't include CJK glyphs on some distributions.

## Risks / Trade-offs

- **[Docker image size increase]** → Mitigation: `fonts-noto` adds ~50MB. Acceptable for a server image that already includes Python, Pillow, and a model inference runtime.
- **[PIL doesn't handle RTL text layout]** → Mitigation: Arabic/Hebrew text will render with correct glyphs but left-to-right order. This is a PIL limitation, not a font limitation. Acceptable for now — the OCR text is still readable even if word order isn't correct for RTL.
- **[`.ttc` (TrueType Collection) files may not work with all Pillow versions]** → Mitigation: Pillow supports `.ttc` files with an `index` parameter. Add both `.ttf` and `.ttc` paths to cover different installations.
