## Why

Images can get stuck in `processing` or `pending` state if the server crashes, the Qwen3-VL API hangs, or an unexpected error leaves the state machine in limbo. Once stuck, they stay that way forever — there is no retry or recovery mechanism. Users see a yellow "Processing" badge indefinitely with no feedback and no resolution.

## What Changes

- Add `retry_count` and `max_retries` fields to `UploadedImage` to track retry attempts per image.
- Add configurable settings: `PROCESSING_TIMEOUT_MINUTES` (default 5) and `MAX_RETRIES` (default 2).
- Create a management command `retry_stuck_images` that finds images stuck in `processing` or `pending` beyond the timeout, retries them up to `max_retries` times, and marks them `failed` with a descriptive message when retries are exhausted.
- Show retry count and exhausted-retry error messages on the image detail page.
- Log each retry attempt to `ProcessingLog` for traceability.

## Capabilities

### New Capabilities

- `stuck-image-retry`: Detects images stuck in `processing` or `pending` state beyond a configurable timeout, retries processing up to a configurable number of attempts, and marks them failed with a descriptive message when retries are exhausted.

### Modified Capabilities

## Impact

- `lpr_app/models.py` — new fields, new migration
- `lpr_project/settings.py` — new configurable settings
- `lpr_app/management/commands/retry_stuck_images.py` — new management command
- `lpr_app/services/image_processing_service.py` — handle retry context (reset state before reprocessing)
- `lpr_app/templates/lpr_app/image_detail.html` — display retry count and retry-exhausted messages
- `.env.example`, `.env.llamacpp.example` — document new env vars
- Database migration required
