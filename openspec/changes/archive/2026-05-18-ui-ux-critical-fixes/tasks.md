## 1. Critical Bug Fixes

- [x] 1.1 Create `templates/lpr_app/error.html` extending `base.html` with error title/message card and back button
- [x] 1.2 Fix `handleAjaxError` selector in `base.html`: change `document.querySelector('main .container')` to `document.querySelector('main.container')`
- [x] 1.3 Fix `ImageSearchForm.__init__` in `forms.py`: check widget type before setting class, use `form-select` for select widgets
- [x] 1.4 Remove dead `LPRSettingsForm` class from `forms.py`

## 2. Windowed Pagination

- [x] 2.1 Create `templates/lpr_app/_pagination.html` partial with windowed pagination logic (first/last always shown, 2 pages before/after current, ellipsis for gaps, prev/next buttons, hidden when single page)
- [x] 2.2 Replace desktop pagination in `image_list.html` with `{% include "lpr_app/_pagination.html" %}`
- [x] 2.3 Replace mobile pagination in `image_list.html` with bounded windowed variant from the shared partial, add `role="navigation"` and `aria-label="Image pagination"` to mobile container

## 3. Upload Page Fixes

- [x] 3.1 Replace hardcoded `const maxSize = 250 * 1024` in `upload.html` with `const maxSize = {{ settings.UPLOAD_FILE_MAX_SIZE }}`
- [x] 3.2 Pass `UPLOAD_FILE_MAX_SIZE` as `settings` context variable in the upload view (`web_views.py`)
- [x] 3.3 Add empty state for recent uploads: `{% else %}` block with "Your recent uploads will appear here" message
- [x] 3.4 Remove unused Bootstrap validation JS block (`needs-validation`, `was-validated` handler) from `upload.html`

## 4. Image Detail Page Fixes

- [x] 4.1 Fix duplicate filename in image detail card header — remove the second filename display
- [x] 4.2 Remove redundant accordion chevron JS (CSS `transform: rotate(180deg)` already handles it)
- [x] 4.3 Create `json_format` template filter in `lpr_app/templatetags/` that renders JSON with `json.dumps(data, indent=2)` and handles `None`/non-dict values
- [x] 4.4 Replace `{{ uploaded_image.api_response|pprint }}` with `{{ uploaded_image.api_response|json_format }}` in `image_detail.html`

## 5. CSS Cleanup

- [x] 5.1 Add `.card-img-fixed` class to `base.html` shared styles (`height: 200px; object-fit: cover;`)
- [x] 5.2 Remove duplicate dark mode `code`/`pre code` CSS blocks from `upload.html`
- [x] 5.3 Remove duplicate dark mode `code`/`pre code` CSS blocks from `image_detail.html`
- [x] 5.4 Replace inline `style="height: 200px; object-fit: cover;"` with `card-img-fixed` class in `upload.html` and `image_list.html`

## 6. Accessibility Improvements

- [x] 6.1 Add `tabindex="0"`, `role="button"`, `aria-label`, and `keydown` handler (Enter/Space) to previewable images in `base.html`'s `openFullscreenPreview()` and attach logic
- [x] 6.2 Update `openFullscreenPreview()` to set dynamic `alt` text on the preview image
- [x] 6.3 Standardize `alt` text across all image templates: "Original uploaded image for {{ filename }}" and "Processed image with detected license plate bounding boxes"
- [x] 6.4 Add `loading="lazy"` to all card images in `upload.html` and `image_list.html`

## 7. Tests

- [x] 7.1 Add test: `error.html` renders with error title and message for invalid image ID
- [x] 7.2 Add test: `ImageSearchForm` renders `processing_status` with `form-select` class (not `form-control`)
- [x] 7.3 Add test: upload page contains empty state when no recent uploads exist
- [x] 7.4 Add test: upload view passes `UPLOAD_FILE_MAX_SIZE` in context
- [x] 7.5 Add test: pagination windowed correctly (page 25 of 50 shows bounded set)
- [x] 7.6 Run full test suite and verify all tests pass
