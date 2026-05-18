## Context

The `UploadedImage` model stores uploaded files under `media/uploads/YYYY/MM/DD/<original_filename>` via the `upload_to_uploads` callable. The processed images follow the same pattern under `processed/`. Today the original filename from the HTTP request is used verbatim. If two uploads share the same filename on the same day, the second overwrites the first on disk while both database rows point to the same path — leading to silent data corruption.

## Goals / Non-Goals

**Goals:**
- Guarantee on-disk filename uniqueness for every upload, regardless of user-supplied names.
- Preserve the user-facing original filename for display, download headers, and API responses.
- Keep the date-partitioned directory structure (`uploads/YYYY/MM/DD/`, `processed/YYYY/MM/DD/`).
- Avoid database schema changes or data migrations.

**Non-Goals:**
- Migrating or renaming existing uploaded files.
- Changing how the `filename` field is displayed or used in prompts.
- Adding deduplication or content-addressable storage.

## Decisions

### 1. UUID4 prefix in `upload_to` callables
Inject `uuid4().hex[:8]` (or full UUID string) plus original extension into the path returned by `upload_to_uploads` and `upload_to_processed`.

**Why UUID over `get_available_name`?** Django's `FileSystemStorage.get_available_name` appends `_1`, `_2`, etc., but this only triggers when the file already exists. A UUID prevents the collision from ever occurring and is deterministic without filesystem access. Using the first 8 hex chars keeps paths readable while still providing 4 billion unique values per day-folder — more than sufficient.

**Decision**: Use `uuid.uuid4().hex[:8]` + `_` + sanitized original basename, preserving extension. Example: `a1b2c3d4_plate.jpg`.

### 2. `filename` field unchanged
The `UploadedImage.filename` CharField already stores the original name and is set in `save()`. It will continue to do so. Only `original_image.name` (the storage path) changes. Download `Content-Disposition` headers already use `self.filename`, so no change needed there.

### 3. Processed image naming
Currently `image_processing_service.py` constructs `processed_{uploaded_image.filename}`. After the change, `original_image.name` on disk is GUID-prefixed but `filename` is still the original. Processed filenames should derive from the GUID-based disk name to stay collision-free. Specifically, the processed filename will use `processed_{guid_prefix}_{original_basename}` pattern.

### 4. Comparison image naming follows same pattern
`comparison_{guid_prefix}_{original_basename}` — same rationale as processed images.

## Risks / Trade-offs

- **[Path length]** GUID prefix adds ~9 chars per filename. Max path stays well within OS limits (255 chars). → No mitigation needed.
- **[Backward compatibility for downloads]** `FileService.download_image` uses `uploaded_image.filename` for the `Content-Disposition` header, which remains the original name. → No impact.
- **[Existing files]** Files uploaded before this change keep their original paths in the DB. Since `upload_to` is only called at write time, old records remain valid. → No migration needed.
