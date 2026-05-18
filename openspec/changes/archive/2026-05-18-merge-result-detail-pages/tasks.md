## 1. View & URL Changes

- [x] 1.1 Enrich `image_detail` view context: add `detection_results`, `plate_count`, `ocr_count`, `first_ocr_text` via `WebResponseHelper.get_image_context()` alongside existing `processing_logs`
- [x] 1.2 Add permanent redirect from `/result/<image_id>/` to `/image/<image_id>/` in `urls.py` using `HttpResponsePermanentRedirect`
- [x] 1.3 Remove `result_view` function from `web_views.py`
- [x] 1.4 Remove `result` URL pattern and `result_view` import from `urls.py`
- [x] 1.5 Update `upload_image` redirect URL in `web_views.py` from `lpr_app:result` to `lpr_app:image_detail`

## 2. URL Reference Migration

- [x] 2.1 Update `lpr_app/views.py` upload redirect from `lpr_app:result` to `lpr_app:image_detail`
- [x] 2.2 Update `templates/lpr_app/upload.html` "View Results" links from `lpr_app:result` to `lpr_app:image_detail`
- [x] 2.3 Update `templates/lpr_app/image_list.html` "View Results" link from `lpr_app:result` to `lpr_app:image_detail`
- [x] 2.4 Update `lpr_app/admin.py` view-on-site link from `lpr_app:result` to `lpr_app:image_detail`

## 3. Template Merge

- [x] 3.1 Rewrite `image_detail.html` to include all sections: Image Info, Image Comparison (side-by-side), Detection Summary, Detection Details accordion, Raw API Response, Processing Logs
- [x] 3.2 Add `{% load duration_format %}` template tag
- [x] 3.3 Use `col-lg-12` full-width layout instead of `col-lg-8 mx-auto`
- [x] 3.4 Add processing failed alert and no-detections fallback from `results.html`
- [x] 3.5 Unify dark-mode CSS to use CSS custom properties only (no hardcoded hex colors)
- [x] 3.6 Consolidate JavaScript: accordion chevron toggle + clipboard copy + fullscreen preview on all `.img-fluid` elements
- [x] 3.7 Delete `templates/lpr_app/results.html`

## 4. Testing

- [x] 4.1 Verify merged page renders correctly for completed images (all sections visible)
- [x] 4.2 Verify merged page renders correctly for failed images (no detection sections, error shown)
- [x] 4.3 Verify merged page renders correctly for pending images (info alert, no detection sections)
- [x] 4.4 Verify `/result/<id>/` redirects to `/image/<id>/` with 301 status
- [x] 4.5 Verify upload flow redirects to `/image/<id>/`
- [x] 4.6 Verify dark mode renders correctly (no hardcoded color remnants)
- [x] 4.7 Verify fullscreen preview, accordion chevrons, and clipboard copy all work
- [x] 4.8 Verify image list "View Results" and "View Details" buttons both link to `/image/<id>/`
