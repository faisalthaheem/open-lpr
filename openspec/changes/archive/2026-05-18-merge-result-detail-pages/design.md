## Context

The application has two nearly identical pages for viewing a processed image:

1. **Results page** (`/result/<id>/`) — Shows image comparison, detection details accordion, detection summary stats. Served by `result_view` using `results.html`.
2. **Image Detail page** (`/image/<id>/`) — Shows image metadata table, raw API response, processing logs, detection summary stats. Served by `image_detail` using `image_detail.html`.

Both pages display the same original/processed images, download buttons, status badges, and detection summaries. The duplication has led to inconsistent dark-mode CSS (hardcoded hex vs CSS custom properties), duplicated JavaScript (different fullscreen preview selectors), and maintenance overhead.

The `result` URL name is referenced in 7 places across the codebase (views, templates, admin).

## Goals / Non-Goals

**Goals:**
- Merge both pages into a single `image_detail.html` template retaining all features from both
- Remove `result_view` and the `result` URL pattern
- Redirect `/result/<id>/` to `/image/<id>/` for backward compatibility
- Update all `lpr_app:result` URL references to `lpr_app:image_detail`
- Unify dark-mode CSS to use CSS custom properties consistently
- Consolidate all JavaScript into a single `extra_js` block

**Non-Goals:**
- Redesigning the page layout or visual style
- Changing the data model or adding new features
- Modifying the API endpoints

## Decisions

### Decision 1: Keep `image_detail.html` as the surviving template

**Choice:** Merge everything into `image_detail.html`, delete `results.html`.

**Rationale:** The detail page already has richer features (processing logs, raw API response, duration formatting). It uses CSS custom properties for dark mode instead of hardcoded hex colors. The URL `/image/<id>/` is more semantically appropriate for a combined page.

**Alternative considered:** Create a brand-new template. Rejected because `image_detail.html` already has the better CSS approach and more features.

### Decision 2: Use `col-lg-12` full-width layout

**Choice:** Switch from `col-lg-8 mx-auto` (current detail) to `col-lg-12` (from results) for the merged page.

**Rationale:** The combined content (image comparison + detection accordion + logs + API response) needs horizontal space. The narrow centered layout would cause excessive vertical scrolling.

### Decision 3: Section ordering in the merged template

**Choice:** Order sections as: Image Info + Comparison → Detection Summary → Detection Details Accordion → Raw API Response → Processing Logs.

**Rationale:** Places the most visually important content (images and detections) above the fold, with debugging data (API response, logs) below. Matches the natural user flow from the results page.

### Decision 4: Context enrichment in `image_detail` view

**Choice:** Add `detection_results`, `plate_count`, `ocr_count`, `first_ocr_text` to the `image_detail` view context using `WebResponseHelper.get_image_context()`.

**Rationale:** Currently `results.html` receives these as separate context variables while `image_detail.html` calls model methods in-template. Passing them explicitly is cleaner and avoids duplicate template logic.

### Decision 5: Permanent redirect for `/result/<id>/`

**Choice:** Use Django's `HttpResponsePermanentRedirect` for the old URL.

**Rationale:** Preserves bookmarks and external links. A 301 redirect is appropriate since the old URL is permanently replaced.

### Decision 6: Rename URL from `image_detail` to just `detail`

**Choice:** Keep the URL name as `image_detail` to minimize changes.

**Rationale:** Renaming would require updating even more references. The current name is clear enough.

## Risks / Trade-offs

- **[Risk: Template complexity]** The merged template will be longer than either individual template. → Mitigation: Sections are clearly separated with comments and Bootstrap cards. The template is still a single cohesive page.
- **[Risk: Broken links]** External links to `/result/<id>/` could break if redirect is removed later. → Mitigation: The permanent redirect ensures backward compatibility.
- **[Risk: Missing feature during merge]** A feature from one page could be accidentally dropped. → Mitigation: Tasks include a checklist comparing all features from both templates.
