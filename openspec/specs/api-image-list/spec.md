## ADDED Requirements

### Requirement: Paginated image list API endpoint
The backend SHALL expose a `GET /api/v1/images/` endpoint returning a paginated, filterable list of uploaded images.

#### Scenario: Default listing
- **WHEN** a GET request is made to `/api/v1/images/` with no query parameters
- **THEN** the backend SHALL return a JSON response with a paginated list of images ordered by upload timestamp (newest first), including `results`, `count`, `next`, and `previous` pagination fields

#### Scenario: Search by filename
- **WHEN** a GET request includes a `query` query parameter
- **THEN** the backend SHALL filter images where the filename contains the query string (case-insensitive)

#### Scenario: Filter by date range
- **WHEN** GET requests include `date_from` and/or `date_to` query parameters (ISO date format)
- **THEN** the backend SHALL filter images by upload timestamp within the specified date range

#### Scenario: Filter by processing status
- **WHEN** a GET request includes a `status` query parameter with value `pending`, `processing`, `completed`, or `failed`
- **THEN** the backend SHALL filter images matching that processing status

#### Scenario: Pagination parameters
- **WHEN** a GET request includes `page` and/or `page_size` query parameters
- **THEN** the backend SHALL return the requested page with up to `page_size` results (default 12, max 100)

### Requirement: Image list response format
Each image in the list response SHALL include `id`, `filename`, `processing_status`, `upload_timestamp`, `processing_timestamp`, `original_image_url`, `processed_image_url`, `plate_count`, `ocr_count`, and `first_ocr_text`.

#### Scenario: Image list item fields
- **WHEN** the image list API returns results
- **THEN** each item SHALL contain `id` (int), `filename` (string), `processing_status` (string), `upload_timestamp` (ISO 8601), `processing_timestamp` (ISO 8601 or null), `original_image_url` (absolute URL path), `processed_image_url` (absolute URL path or null), `plate_count` (int), `ocr_count` (int), and `first_ocr_text` (string or null)

#### Scenario: Completed image with detections
- **WHEN** a completed image has one or more plate detections
- **THEN** `plate_count` SHALL be the number of detected plates, `ocr_count` SHALL be the number of OCR text results, and `first_ocr_text` SHALL be the text of the first OCR result (or null if no OCR results)

#### Scenario: Image with no detections
- **WHEN** an image has no detections (pending, processing, failed, or completed with 0 results)
- **THEN** `plate_count` SHALL be 0, `ocr_count` SHALL be 0, and `first_ocr_text` SHALL be null
