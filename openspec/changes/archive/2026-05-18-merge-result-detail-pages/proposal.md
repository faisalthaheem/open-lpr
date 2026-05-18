## Why

The Results page (`/result/<id>/`) and Image Detail page (`/image/<id>/`) serve nearly identical content — original/processed images, detection summaries, download buttons, and status badges — but are split across two templates, two views, and two URL patterns. This duplication causes bugs to be fixed twice (e.g., dark mode styling inconsistencies, different click-to-preview selectors) and makes the codebase harder to maintain.

## What Changes

- Merge `results.html` and `image_detail.html` into a single unified template (`image_detail.html`) that includes all features from both pages.
- Remove the `result_view` view function and its URL pattern. The `image_detail` view becomes the sole page for viewing an uploaded image and its results.
- Redirect the old `/result/<id>/` URL to `/image/<id>/` to preserve any existing links/bookmarks.
- Consolidate the JavaScript: accordion chevron toggle + clipboard copy + fullscreen preview into one cohesive script.
- Unify the dark-mode CSS: use CSS custom properties (from `image_detail.html`) instead of hardcoded hex colors (from `results.html`).
- The merged page uses the wider `col-lg-12` layout (from `results.html`) to give detection details and image comparisons more room.

## Capabilities

### New Capabilities

### Modified Capabilities

## Impact

- `templates/lpr_app/image_detail.html` — Expanded to include all sections from `results.html` (image comparison, detection details accordion, processing failed alert)
- `templates/lpr_app/results.html` — Deleted
- `lpr_app/views/web_views.py` — Remove `result_view`, add redirect for old URL, enrich `image_detail` context with `detection_results`, `plate_count`, `ocr_count`
- `lpr_app/urls.py` — Remove `result` URL pattern, add redirect from `/result/<id>/` to `/image/<id>/`
- `templates/lpr_app/image_list.html` — Update "View Results" links from `lpr_app:result` to `lpr_app:image_detail`
- `templates/lpr_app/upload.html` — Update any "View Results" links similarly
- No database changes required
