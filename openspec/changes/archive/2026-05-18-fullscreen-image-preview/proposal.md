## Why

The image preview modal on the results page uses Bootstrap's `modal-lg` class, which caps the dialog at ~800px wide. Users reviewing license plate detections on high-resolution images need to see fine detail, but the current modal wastes significant screen space with padding, headers, and fixed sizing — making the actual image area small and requiring scrolling/zooming externally.

## What Changes

- Replace the current `modal-lg` image preview with a fullscreen (or near-fullscreen) modal that maximizes the visible image area.
- The image should scale to fill available viewport space while maintaining aspect ratio.
- Minimal chrome: close button overlay (no header/footer consuming vertical space).
- Apply this fullscreen preview to all clickable images across the site (results page, image detail page, image list page).
- Support both light and dark mode.

## Capabilities

### New Capabilities
- `fullscreen-image-preview`: Clickable images open in a fullscreen modal that uses maximum viewport space to display the image as large as possible, with a minimal close button overlay.

### Modified Capabilities

## Impact

- `templates/lpr_app/results.html` — Replace current zoom modal JavaScript and CSS
- `templates/lpr_app/image_detail.html` — Add click-to-zoom behavior to original/processed images
- `templates/lpr_app/image_list.html` — Add click-to-zoom behavior to card images
- `templates/base.html` — Potentially add shared fullscreen preview CSS/JS
