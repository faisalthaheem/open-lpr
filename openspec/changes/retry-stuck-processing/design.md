## Context

Processing is synchronous — `ImageProcessingService.process_uploaded_image()` runs within the HTTP request. The `UploadedImage` model tracks status via `processing_status` with states: `pending`, `processing`, `completed`, `failed`. There is no task queue, no retry mechanism, and no timeout recovery. If the server crashes or the Qwen3-VL API hangs, images stay stuck in `processing` indefinitely.

`ProcessingLog` records each processing event per image, and the UI already renders `error_message` on the image detail and results pages.

## Goals / Non-Goals

**Goals:**
- Detect images stuck in `processing` or `pending` state beyond a configurable timeout.
- Automatically retry processing up to a configurable number of times.
- Mark images as `failed` with a descriptive message when retries are exhausted.
- Display retry count and exhaustion messages in the UI.
- Log every retry attempt to `ProcessingLog`.

**Non-Goals:**
- Adding a task queue (Celery, etc.).
- Adding a manual "Retry" button in the UI.
- Setting timeouts on the Qwen3-VL API client itself.
- Retrying images already in `completed` or `failed` state.

## Decisions

**1. Management command triggered by cron**

Use `python manage.py retry_stuck_images` as the retry mechanism, intended to be called by cron or a systemd timer every 1–2 minutes. This is the standard Django pattern for periodic tasks and requires no new dependencies.

Alternatives considered:
- *Django middleware checking on every request*: Adds latency, unreliable, ties background work to user traffic.
- *Celery Beat*: Adds infrastructure complexity for a single periodic task.

**2. Track retries on the model, not in logs**

Add `retry_count` (PositiveIntegerField) and `max_retries` (PositiveIntegerField) directly to `UploadedImage`. This makes the retry state queryable without joining `ProcessingLog` and survives log purges. `max_retries` is set from `settings.MAX_RETRIES` at creation time so each image captures the policy in effect when it was uploaded.

**3. Reset status before reprocessing**

When retrying, set `processing_status = 'pending'`, increment `retry_count`, and call the existing `ImageProcessingService.process_uploaded_image()`. This reuses the full three-phase pipeline (detection → OCR → visualize) without duplicating logic.

**4. Configurable via python-decouple**

`PROCESSING_TIMEOUT_MINUTES` (default 5) and `MAX_RETRIES` (default 2) follow the existing pattern in `settings.py` using `config()` from `python-decouple`.

**5. Error message format on exhaustion**

When retries are exhausted, set `error_message` to `"Processing failed after {retry_count} attempts. Last error: {original_error}"`. The UI already displays `error_message`, so this requires minimal template changes.

## Risks / Trade-offs

- **[Retry runs synchronously within the management command]** → Mitigation: The command processes one image at a time. If the API call hangs, it blocks that invocation — the next cron run picks up other stuck images. Document that `PROCESSING_TIMEOUT_MINUTES` should exceed typical API response time.
- **[Original uploaded image file deleted or corrupted]** → Mitigation: If the file is missing, the retry will fail fast with a clear error message and the image gets marked failed. No data corruption risk.
- **[Migration adds new non-nullable fields]** → Mitigation: Both `retry_count` and `max_retries` have defaults (0 and `settings.MAX_RETRIES` respectively), so the migration is safe for existing rows.
