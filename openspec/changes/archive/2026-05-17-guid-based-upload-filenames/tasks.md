## 1. Update `upload_to` callables in models.py

- [x] 1.1 Modify `upload_to_uploads` to return `uploads/YYYY/MM/DD/<uuid8>_<original_basename>` instead of `uploads/YYYY/MM/DD/<filename>`
- [x] 1.2 Modify `upload_to_processed` to return `processed/YYYY/MM/DD/<uuid8>_<original_basename>` instead of `processed/YYYY/MM/DD/<filename>`

## 2. Update processed/comparison filename generation in image_processing_service.py

- [x] 2.1 Update the `processed_{uploaded_image.filename}` pattern to derive the base name from the GUID-prefixed on-disk name (`original_image.name`) instead of the `filename` field
- [x] 2.2 Update the `comparison_{uploaded_image.filename}` pattern the same way

## 3. Update processed/comparison filename generation in monolithic views.py

- [x] 3.1 Update the `processed_{uploaded_image.filename}` pattern in `views.py` to derive from `original_image.name` like the service
- [x] 3.2 Update the `comparison_{uploaded_image.filename}` pattern in `views.py` the same way

## 4. Verify download and display paths

- [x] 4.1 Confirm `FileService.download_image` uses `uploaded_image.filename` (original name) for `Content-Disposition` — update if needed
- [x] 4.2 Confirm API response `filename` field in `ApiService.format_success_response` uses the original name — update if needed
- [x] 4.3 Confirm web view templates and detail pages display `uploaded_image.filename` (original name) — update if needed

## 5. Testing

- [x] 5.1 Write a unit test that uploads two files with the same name and verifies they get distinct storage paths
- [x] 5.2 Write a unit test verifying the `filename` field retains the original user-supplied name
- [x] 5.3 Write a unit test verifying download `Content-Disposition` uses the original filename
- [x] 5.4 Write a unit test verifying the file extension is preserved in the GUID-prefixed path
