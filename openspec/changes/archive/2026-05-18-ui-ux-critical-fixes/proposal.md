## Why

A systematic UI/UX audit revealed 5 critical bugs (broken pagination, missing error template, silently-failing error handler, broken form widget), several high-impact issues (hardcoded 250KB client-side limit, no empty state), and pervasive inconsistencies (duplicated dark mode CSS, dead code, accessibility gaps). These degrade usability and in some cases break core functionality.

## What Changes

- Create missing `error.html` template to prevent crashes on invalid image ID requests
- Fix `handleAjaxError` selector in `base.html` that silently fails on all AJAX errors
- Rewrite desktop pagination to use proper windowed pagination with ellipsis (pages 2-N are currently unreachable)
- Fix mobile pagination to show a bounded window instead of rendering all pages
- Fix `ImageSearchForm.__init__` to use `form-select` class for the status dropdown
- Replace hardcoded 250KB JS validation with the actual Django settings value
- Add empty state for recent uploads on the home page
- Remove duplicated dark mode CSS blocks from `upload.html` and `image_detail.html`
- Replace inline card image styles with a shared CSS class
- Remove dead `LPRSettingsForm` and unused Bootstrap validation JS
- Fix duplicate filename display in image detail header
- Remove redundant accordion chevron JS (CSS already handles it)
- Add keyboard accessibility for fullscreen image preview
- Fix `pprint` filter to use JSON rendering for API response display
- Add `loading="lazy"` to card images
- Standardize `alt` text across all images
- Add `aria-label` to mobile pagination

## Capabilities

### New Capabilities
- `error-page`: Proper error page template for graceful error handling
- `windowed-pagination`: Proper windowed pagination with ellipsis for desktop and mobile

### Modified Capabilities
- `fullscreen-image-preview`: Add keyboard accessibility (Enter/Space), focus trap, dynamic alt text
- `merge-result-detail-pages`: Fix duplicate filename, remove redundant chevron JS, fix pprint

## Impact

- Templates: `base.html`, `upload.html`, `image_detail.html`, `image_list.html`, new `error.html`
- Forms: `lpr_app/forms.py` (fix `ImageSearchForm`, remove dead `LPRSettingsForm`)
- Views: `web_views.py` (pass settings to upload context)
- Templatetags: New `json_filter` template filter for safe JSON rendering
- CSS: Centralize dark mode code styles and card image styles in `base.html`
- Tests: New tests for error page, pagination, form widget class
