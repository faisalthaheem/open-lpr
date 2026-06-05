## MODIFIED Requirements

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
