## Why

Uploaded files retain their original filename on disk. When two users upload files with the same name (e.g. `plate.jpg`), Django silently overwrites the earlier file under the same date-partitioned path, causing data loss. GUID-based filenames guarantee uniqueness without requiring filesystem-level conflict resolution.

## What Changes

- The `upload_to_uploads` and `upload_to_processed` callables in `models.py` will generate filenames using a UUID4 prefix while preserving the original file extension (e.g. `a1b2c3d4-...-plate.jpg`).
- The `UploadedImage.filename` field will continue to store the user-supplied original name for display purposes — only the on-disk path changes.
- Processed/comparison output filenames in `image_processing_service.py` and `views.py` will use the GUID-based original filename as their base, avoiding collisions in the `processed/` directory.
- The `FileService.download_image` response `Content-Disposition` header will serve the file with the original user-facing `filename`, so API consumers see no change.

## Capabilities

### New Capabilities
- `guid-upload-paths`: Upload and processed file paths use UUID4-prefixed filenames to guarantee uniqueness on disk while preserving the original filename for display/download.

### Modified Capabilities
<!-- No existing capability requirements change -->

## Impact

- `lpr_app/models.py` — `upload_to_uploads`, `upload_to_processed` callables
- `lpr_app/services/image_processing_service.py` — processed/comparison filename generation
- `lpr_app/views.py` (monolithic) — processed/comparison filename generation
- `lpr_app/views/web_views.py` — web upload path
- `lpr_app/services/api_service.py` — API upload record creation
- `lpr_app/services/file_service.py` — download filename handling
- Database migration not required (schema unchanged; only `upload_to` callable logic changes)
- Existing uploaded files remain accessible — no data migration needed
