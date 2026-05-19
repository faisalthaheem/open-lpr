## MODIFIED Requirements

### Requirement: Unified image detail page

The system SHALL display all image information and processing results on a single page at `/image/<image_id>/` that combines the features of both the former Results and Image Detail pages.

The page SHALL include the following sections in order:
1. Image Information card (filename, size, status badge, timestamps, error message, retry count — NO duplicate filename display)
2. Image Comparison card (side-by-side original vs processed images with download buttons)
3. Detection Summary card (plate count, OCR count, total detections as stat cards)
4. Detection Details accordion (per-detection drilldown with confidence, bounding box coordinates, OCR text — chevron toggle handled by CSS only, no JS class swapping)
5. Raw API Response accordion (full JSON response rendered as valid JSON via `json_format` filter with copy-to-clipboard)
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

#### Scenario: No duplicate filename in header
- **WHEN** the Image Information card is rendered
- **THEN** the filename SHALL appear exactly once in the card header (not duplicated)

#### Scenario: API response renders as valid JSON
- **WHEN** the Raw API Response section is rendered
- **THEN** the content SHALL display as properly formatted JSON (double quotes, `true`/`false`/`null`) not Python repr

#### Scenario: Accordion chevron handled by CSS only
- **WHEN** a user expands or collapses a detection accordion item
- **THEN** the chevron icon SHALL rotate via CSS `transform: rotate(180deg)` with no JavaScript class manipulation

### Requirement: Consolidated JavaScript

The merged template SHALL include all JavaScript functionality in a single `extra_js` block:
- Clipboard copy with toast notification (from image_detail.html)
- Fullscreen image preview on all `.img-fluid` elements (unified selector)

The accordion chevron toggle JavaScript SHALL be removed — CSS `transform` handles the visual state.

#### Scenario: Copy API response to clipboard
- **WHEN** a user clicks the "Copy" button in the API Response section
- **THEN** the properly formatted JSON text is copied to the clipboard and a success toast appears

#### Scenario: Fullscreen image preview
- **WHEN** a user clicks any image in the detail page
- **THEN** the fullscreen preview overlay opens (using the shared `openFullscreenPreview()` from `base.html`)
