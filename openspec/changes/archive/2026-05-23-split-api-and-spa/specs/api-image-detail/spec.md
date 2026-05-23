## ADDED Requirements

### Requirement: Image detail API endpoint
The backend SHALL expose a `GET /api/v1/images/<id>/` endpoint returning full details for a single image.

#### Scenario: Successful detail retrieval
- **WHEN** a GET request is made to `/api/v1/images/<id>/` with a valid image ID
- **THEN** the backend SHALL return a JSON response containing the image's full metadata, detection results (plates and OCR data), processing logs, original and processed image URLs, and file size information

#### Scenario: Image not found
- **WHEN** a GET request is made with an image ID that does not exist
- **THEN** the backend SHALL return a 404 JSON response with an error message

### Requirement: Image detail response format
The detail response SHALL include all fields needed to render the image detail view in the SPA.

#### Scenario: Complete detail response
- **WHEN** the image detail API returns a successful response
- **THEN** the response SHALL include: `id`, `filename`, `processing_status`, `upload_timestamp`, `processing_timestamp`, `original_image_url`, `processed_image_url`, `error_message`, `detections` (array of plate + OCR data with coordinates and confidence), `processing_logs` (array of log entries), and `api_response` (raw JSON from the OCR pipeline)
