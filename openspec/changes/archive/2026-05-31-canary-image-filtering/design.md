## Context

The system has a canary monitoring service (`canary/`) that periodically sends test images to `/api/v1/ocr/` with `save_image=false` and the `X-Canary-Request` header. On the **success path**, the existing code in `ImageProcessingService._handle_canary_cleanup()` deletes the database record and all associated files, leaving no trace. However, on the **failure path** (e.g., AI API timeout, invalid response, processing error), the `UploadedImage` record remains in the database with `processing_status=failed` and its files persist on disk. These failed canary images then appear in the SPA gallery.

Current failure handling flow (simplified):
1. `api_views.py` catches exceptions from `process_uploaded_image()`
2. Sets `processing_status=failed` and `error_message` on the `UploadedImage` record
3. Records error metrics
4. Returns error response — **no canary-specific cleanup**

## Goals / Non-Goals

**Goals:**
- Failed canary images SHALL be cleaned up identically to successful canary images (DB record deleted, files deleted)
- Canary failure metrics SHALL be recorded before cleanup so operators can monitor system health
- The cleanup approach SHALL reuse the existing `_handle_canary_cleanup()` method

**Non-Goals:**
- Changing the canary request identification mechanism (header-based detection stays as-is)
- Adding a `source` field to `UploadedImage` to track canary vs. user uploads
- Modifying the SPA frontend (no changes needed — canary images simply won't exist in listings)
- Changing the canary service itself

## Decisions

### Decision 1: Reuse `_handle_canary_cleanup()` on the failure path

The existing `_handle_canary_cleanup()` method already handles file deletion and DB record removal. Instead of duplicating cleanup logic, the error handler in `api_views.py` (or `api_service.py`) will call this same method after recording failure metrics.

**Alternative considered**: Adding a `source` field to `UploadedImage` and filtering in the list API query. Rejected because it requires a migration, changes the data model, and still leaves orphaned files on disk. Cleanup is simpler and more complete.

### Decision 2: Ensure metrics are recorded before record deletion

The current error path already records `lpr_processing_errors_total` and `lpr_canary_requests_total{status="failed"}`. The cleanup will happen after all metrics calls, so no metrics are lost. The `_handle_canary_cleanup()` method will be called after the metrics recording block, not before.

### Decision 3: Cleanup location — in the error handler of the API view

The cleanup will be triggered in the `except` block of the OCR endpoint handler in `api_views.py`, after the existing error-handling logic (status update, error message, metrics). This keeps the cleanup at the same architectural layer as the success-path cleanup.

## Risks / Trade-offs

- **[No audit trail for failed canary images]** → Accepted trade-off. Canary images are ephemeral by design. Metrics provide the monitoring trail (`lpr_canary_requests_total{status="failed"}`, error counters).
- **[Race condition if cleanup fails]** → Low risk. File deletion errors are already handled gracefully in `_handle_canary_cleanup()` with try/except blocks. If the DB record deletion fails, the record remains but will have `failed` status — same as current behavior.
- **[Metrics accuracy]** → Mitigated by ensuring all metric recordings happen before the cleanup call. The `MetricsHelper` methods write to Prometheus counters in-memory, not to the DB record, so deleting the `UploadedImage` row does not affect already-recorded metrics.
