## Why

Canary images that fail processing currently leave behind `UploadedImage` records with `failed` status. These records appear in the SPA image gallery and pollute the user-facing experience. Failed canary images should be silently discarded (DB record + files deleted) while still reporting the failure through the existing Prometheus metrics pipeline so operators can monitor system health.

## What Changes

- After a canary image fails processing, automatically delete the database record and any associated files (same cleanup that already happens on success with `save_image=false`)
- Ensure failed canary processing still records metrics (`lpr_canary_requests_total{status="failed"}`, `lpr_canary_processing_duration_seconds`, error counters) before cleanup
- The SPA requires no changes — canary images will simply never appear in the gallery since they are deleted on both success and failure paths

## Capabilities

### New Capabilities

- `canary-failure-cleanup`: Automatic cleanup of canary images when processing fails, including file deletion and database record removal, while preserving metrics reporting

### Modified Capabilities

- `api-image-list`: No requirement changes (canary images are already invisible on the success path; this extends the same behavior to the failure path)

## Impact

- **Backend**: `lpr_app/services/image_processing_service.py` — error/failure path needs cleanup logic similar to `_handle_canary_cleanup()`
- **Backend**: `lpr_app/services/api_service.py` — error response formatting for canary failures
- **Metrics**: `lpr_app/utils/metrics_helpers.py` — ensure canary failure metrics are recorded before record deletion
- **No frontend changes**: SPA already has no concept of canary images; they simply won't appear in listings
- **No API contract changes**: The response for failed canary requests changes internally but maintains the same error response shape
