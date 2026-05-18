## Why

The `BoundingBoxVisualizer` draws OCR text labels on images using TrueType fonts. The current font search list only includes Latin-only fonts (DejaVu, Liberation, Ubuntu). When OCR returns non-Latin text (Arabic, Japanese, Chinese, etc.), the glyphs render as boxes or missing characters because no Unicode-capable font is loaded.

Additionally, the Docker image (`python:3.11-slim`) installs **no fonts at all** — even the existing font paths won't work in the container. The visualizer silently falls back to PIL's built-in default bitmap font, which has extremely limited character coverage.

## What Changes

- Install `fonts-noto` in the Docker image to provide Unicode coverage.
- Update the font search path in `bbox_visualizer.py` to prioritize Noto Sans, which covers Latin, Arabic, CJK, Hebrew, and many other scripts.
- Update `AGENTS.md` to reflect the Docker font dependency.

## Capabilities

### New Capabilities

### Modified Capabilities

## Impact

- `Dockerfile` — add `fonts-noto` to apt-get install
- `lpr_app/services/bbox_visualizer.py` — update font path list to prioritize Noto
- `AGENTS.md` — note the font dependency
