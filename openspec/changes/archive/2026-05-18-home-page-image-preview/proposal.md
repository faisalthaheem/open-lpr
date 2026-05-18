## Why

The home page displays recent uploads as cards with thumbnail images, but clicking those images does nothing. Users must click the small "View" button to navigate to the detail page just to see the image at full size. The fullscreen preview overlay already exists in `base.html` (shared across all pages) — it just needs to be wired up on the home page thumbnails.

## What Changes

- Add click-to-preview JavaScript to the recent uploads card images on the home page (`upload.html`)
- Clicking a thumbnail in the "Recent Uploads" section opens the shared fullscreen preview overlay (same as the detail and list pages)
- Images show a pointer cursor and hover scale effect to indicate they are clickable
- No new templates, views, or URLs needed — purely a frontend enhancement

## Capabilities

### New Capabilities

### Modified Capabilities

## Impact

- `templates/lpr_app/upload.html` — Add JavaScript in `extra_js` block to attach click handlers to `.result-card .card-img-top` images
