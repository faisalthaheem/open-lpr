## 1. Model & Settings

- [ ] 1.1 Add `retry_count` (PositiveIntegerField, default=0) and `max_retries` (PositiveIntegerField, default=2) fields to `UploadedImage` in `models.py`.
- [ ] 1.2 Override `UploadedImage.save()` to set `max_retries` from `settings.MAX_RETRIES` on first save (when `pk` is None).
- [ ] 1.3 Add `PROCESSING_TIMEOUT_MINUTES` and `MAX_RETRIES` to `settings.py` using `python-decouple` `config()` with defaults 5 and 2.
- [ ] 1.4 Run `python manage.py makemigrations lpr_app` and verify the generated migration.
- [ ] 1.5 Add `PROCESSING_TIMEOUT_MINUTES` and `MAX_RETRIES` to `.env.example` and `.env.llamacpp.example` with comments.

## 2. Management Command

- [ ] 2.1 Create `lpr_app/management/commands/retry_stuck_images.py` with a `Command` class extending `BaseCommand`.
- [ ] 2.2 Implement `handle()` to query `UploadedImage` objects where `processing_status` in `('processing', 'pending')` and `upload_timestamp < now() - PROCESSING_TIMEOUT_MINUTES`.
- [ ] 2.3 For each stuck image where `retry_count < max_retries`: increment `retry_count`, create a `ProcessingLog` entry (status=`started`, message="Retry attempt {retry_count}/{max_retries}"), reset `processing_status` to `pending`, clear `error_message`, call `ImageProcessingService.process_uploaded_image()`, and handle exceptions by setting `failed` with error message.
- [ ] 2.4 For each stuck image where `retry_count >= max_retries` and `processing_status != 'failed'`: set `processing_status = 'failed'`, set `error_message = "Processing failed after {retry_count} attempts. Last error: {previous_error_message or 'unknown'}"`, create a `ProcessingLog` entry (status=`error`).
- [ ] 2.5 Add `--timeout` and `--max-retries` command-line options that override settings for ad-hoc use.

## 3. Processing Service Integration

- [ ] 3.1 In `ImageProcessingService.process_uploaded_image()`, ensure that when called for a retry, the method does not re-create the initial `ProcessingLog(status='started')` entry (it already exists from the retry command).

## 4. UI Updates

- [ ] 4.1 In `image_detail.html`, add a table row showing "Retry attempts: {retry_count}/{max_retries}" when `retry_count > 0`, placed near the status row.

## 5. Verification

- [ ] 5.1 Run `python manage.py migrate` and verify the migration applies cleanly.
- [ ] 5.2 Run `python manage.py retry_stuck_images --help` and verify command is registered and options appear.
