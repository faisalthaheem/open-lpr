## 1. Error Path Cleanup in API View

- [x] 1.1 In `lpr_app/views/api_views.py`, add canary cleanup in the `else` block (processing result failure, ~line 105-122): after recording metrics and before returning the error response, call `ImageProcessingService._handle_canary_cleanup(uploaded_image, save_image=False, comparison_path=None)` when `is_canary` is true and `save_image` is false
- [x] 1.2 In `lpr_app/views/api_views.py`, add canary cleanup in the `except` block (unhandled exception, ~line 124-143): after recording metrics and before returning the error response, call `ImageProcessingService._handle_canary_cleanup(uploaded_image, save_image=False, comparison_path=None)` when `is_canary` is true, `save_image` is false, and `uploaded_image` exists (it may not if the exception occurred before record creation)

## 2. Error Response Updates

- [x] 2.1 In `lpr_app/views/api_views.py`, update the `else` block error response for canary failures: set `image_id=None` in the error response after cleanup (since the DB record is deleted)
- [x] 2.2 In `lpr_app/views/api_views.py`, update the `except` block error response for canary failures: set `image_id=None` in the error response after cleanup

## 3. Verification

- [x] 3.1 Verify that failed canary images do not appear in `GET /api/v1/images/` after cleanup by testing the endpoint
- [x] 3.2 Verify that canary failure metrics (`lpr_canary_requests_total{status="failed"}`, `lpr_canary_processing_duration_seconds`) are still recorded at `GET /metrics/` after cleanup runs
- [x] 3.3 Verify that successful canary images continue to be cleaned up as before (no regression)
