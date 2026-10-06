# api-image-list Specification

## Purpose
Covers the image listing API surface: the paginated, filterable list endpoint, its pagination parameter validation, and the per-item response format returned to consumers.

## Requirements

### Requirement: Paginated image list API endpoint
The backend SHALL expose a `GET /api/v1/images/` endpoint returning a paginated, filterable list of uploaded images. Numeric pagination parameters SHALL be validated and SHALL return `400` with a descriptive error message when malformed, rather than raising an unhandled exception.

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

#### Scenario: Non-integer pagination parameter is rejected
- **WHEN** a GET request includes `page` or `page_size` whose value cannot be parsed as an integer
- **THEN** the backend SHALL return a `400` status response with an error message naming the offending parameter, and SHALL NOT return a `500`

#### Scenario: Out-of-range pagination parameter is normalized
- **WHEN** a GET request includes `page` below `1` or `page_size` outside the range `1` to `100`
- **THEN** the backend SHALL clamp the value into the valid range rather than returning an error or an unhandled exception

#### Scenario: Existing pagination links preserve validated parameters
- **WHEN** the backend builds `next` and `previous` pagination URLs
- **THEN** the URLs SHALL carry the validated `page` and `page_size` values actually used for the response

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
