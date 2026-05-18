## ADDED Requirements

### Requirement: Unified image detail page

The system SHALL display all image information and processing results on a single page at `/image/<image_id>/` that combines the features of both the former Results and Image Detail pages.

The page SHALL include the following sections in order:
1. Image Information card (filename, size, status badge, timestamps, error message, retry count, processed image preview, download buttons)
2. Image Comparison card (side-by-side original vs processed images with download buttons)
3. Detection Summary card (plate count, OCR count, total detections as stat cards)
4. Detection Details accordion (per-detection drilldown with confidence, bounding box coordinates, OCR text)
5. Raw API Response accordion (full JSON response with copy-to-clipboard)
6. Processing Logs table (timestamp, status badge, message, formatted duration)

The Image Comparison card SHALL only display when the image has a processed image file.
The Detection Details and Detection Summary cards SHALL only display when processing status is `completed`.

#### Scenario: Viewing a successfully processed image
- **WHEN** a user navigates to `/image/<image_id>/` for an image with `processing_status='completed'`
- **THEN** the page displays all six sections with populated data

#### Scenario: Viewing a failed processing attempt
- **WHEN** a user navigates to `/image/<image_id>/` for an image with `processing_status='failed'`
- **THEN** the page displays the Image Information card with error message, Image Comparison card (if processed image exists), and Processing Logs, but does not display Detection Summary or Detection Details

#### Scenario: Viewing a pending image
- **WHEN** a user navigates to `/image/<image_id>/` for an image with `processing_status='pending'`
- **THEN** the page displays the Image Information card with a pending status badge and an info alert indicating the image has not been processed

#### Scenario: Image comparison with processed image
- **WHEN** a completed image has both original and processed image files
- **THEN** the Image Comparison card shows both images side-by-side with individual download buttons

### Requirement: Result URL redirect

The system SHALL redirect requests to `/result/<image_id>/` to `/image/<image_id>/` with a 301 (permanent) HTTP redirect.

#### Scenario: Old result URL redirects
- **WHEN** a user navigates to `/result/<image_id>/`
- **THEN** the system responds with a 301 redirect to `/image/<image_id>/`

#### Scenario: Old result URL with nonexistent image
- **WHEN** a user navigates to `/result/99999/` and no image with that ID exists
- **THEN** the redirect still occurs (the detail view handles the 404)

### Requirement: URL reference migration

All references to the `lpr_app:result` URL name SHALL be replaced with `lpr_app:image_detail`. This includes:
- `lpr_app/views/web_views.py` — upload redirect URL
- `lpr_app/views.py` — upload redirect URL
- `templates/lpr_app/upload.html` — "View Results" links
- `templates/lpr_app/image_list.html` — "View Results" links
- `lpr_app/admin.py` — admin view-on-site link

#### Scenario: Upload redirects to detail page
- **WHEN** an image upload completes successfully via the web interface
- **THEN** the JavaScript redirect URL uses `lpr_app:image_detail` instead of `lpr_app:result`

#### Scenario: Image list links to detail page
- **WHEN** a user clicks "View Results" on an image in the list page
- **THEN** the link navigates to `/image/<image_id>/` (not `/result/<image_id>/`)

### Requirement: Unified dark mode CSS

The merged template SHALL use CSS custom properties (`var(--bg-tertiary)`, `var(--text-primary)`, etc.) for all dark-mode styling, not hardcoded hex colors.

#### Scenario: Dark mode code and pre elements
- **WHEN** the page is viewed in dark mode
- **THEN** all `<code>`, `<pre>`, `<table>`, and `<td>` elements use CSS custom properties for background and text colors

### Requirement: Consolidated JavaScript

The merged template SHALL include all JavaScript functionality in a single `extra_js` block:
- Accordion chevron toggle (from results.html)
- Clipboard copy with toast notification (from image_detail.html)
- Fullscreen image preview on all `.img-fluid` elements (unified selector)

#### Scenario: Accordion chevron toggles
- **WHEN** a user expands or collapses a detection accordion item
- **THEN** the chevron icon rotates to indicate expanded/collapsed state

#### Scenario: Copy API response to clipboard
- **WHEN** a user clicks the "Copy" button in the API Response section
- **THEN** the raw JSON text is copied to the clipboard and a success toast appears

#### Scenario: Fullscreen image preview
- **WHEN** a user clicks any image in the detail page
- **THEN** the fullscreen preview overlay opens (using the shared `openFullscreenPreview()` from `base.html`)

## REMOVED Requirements

### Requirement: Separate results page

**Reason**: The Results page is merged into the unified Image Detail page.
**Migration**: All `/result/<id>/` links redirect to `/image/<id>/` via 301 permanent redirect.
