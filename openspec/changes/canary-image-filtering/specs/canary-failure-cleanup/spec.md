## ADDED Requirements

### Requirement: Failed canary image cleanup
When a canary image fails during processing, the system SHALL delete the `UploadedImage` database record and all associated files (original image, processed image, comparison image), identical to the cleanup performed for successful canary images with `save_image=false`.

#### Scenario: Canary image fails during AI API call
- **WHEN** a canary request is processed and the AI API call fails (timeout, error response, invalid JSON)
- **THEN** the system SHALL record failure metrics (`lpr_canary_requests_total{status="failed"}`, `lpr_processing_errors_total`) and then delete the `UploadedImage` record and all associated image files

#### Scenario: Canary image fails during detection parsing
- **WHEN** a canary request is processed and the detection response cannot be parsed
- **THEN** the system SHALL record failure metrics and then delete the `UploadedImage` record and all associated image files

#### Scenario: Canary image fails during OCR processing
- **WHEN** a canary request is processed and the OCR step fails
- **THEN** the system SHALL record failure metrics and then delete the `UploadedImage` record and all associated image files

#### Scenario: Failed canary image does not appear in image list
- **WHEN** a canary image fails processing and cleanup completes
- **THEN** the image SHALL NOT appear in the `GET /api/v1/images/` listing or `GET /api/v1/images/{id}/` detail endpoint

### Requirement: Canary failure metrics preservation
All canary failure metrics SHALL be recorded before the database record and files are deleted, ensuring no metric data is lost during cleanup.

#### Scenario: Metrics recorded before deletion
- **WHEN** a canary image fails and cleanup is performed
- **THEN** the system SHALL increment `lpr_canary_requests_total{status="failed"}`, record the processing duration in `lpr_canary_processing_duration_seconds`, and increment relevant error counters BEFORE deleting the database record

#### Scenario: Processing duration tracked for failed canary
- **WHEN** a canary image fails after partial processing
- **THEN** the system SHALL record the elapsed time in `lpr_canary_processing_duration_seconds` histogram before cleanup

### Requirement: Canary error response format
When a canary image fails and is cleaned up, the API response SHALL indicate it was a canary request and that the image was not saved, without exposing internal error details beyond the error message.

#### Scenario: Failed canary response
- **WHEN** a canary request fails processing and cleanup completes
- **THEN** the response SHALL include `canary_request: true`, `image_saved: false`, `image_id: null`, and the relevant error information
