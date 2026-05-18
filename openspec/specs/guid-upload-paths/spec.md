## ADDED Requirements

### Requirement: GUID-prefixed upload filenames
The `upload_to_uploads` callable SHALL generate a storage path that includes a random unique prefix before the original filename, in the format `uploads/YYYY/MM/DD/<uuid8>_<original_basename>`.

#### Scenario: Two files with the same name uploaded on the same day
- **WHEN** two different images both named `plate.jpg` are uploaded
- **THEN** each SHALL be stored at a different path under `uploads/YYYY/MM/DD/`, each with a distinct GUID prefix

#### Scenario: Original extension is preserved
- **WHEN** a file named `photo.png` is uploaded
- **THEN** the stored filename SHALL end with `.png`

#### Scenario: File with no extension
- **WHEN** a file named `image` with no extension is uploaded
- **THEN** the stored filename SHALL use the GUID prefix followed by the original name without modification

### Requirement: GUID-prefixed processed filenames
The `upload_to_processed` callable SHALL generate a storage path in the format `processed/YYYY/MM/DD/<uuid8>_<original_basename>`.

#### Scenario: Processed image path is unique
- **WHEN** an image is processed and saved to the processed directory
- **THEN** the processed image filename SHALL contain a GUID prefix matching the pattern used for uploads

### Requirement: Original filename preserved for display
The `UploadedImage.filename` field SHALL continue to store the original user-supplied filename, unchanged by the GUID prefix in the storage path.

#### Scenario: API response shows original name
- **WHEN** an image is uploaded with filename `my-car.jpg`
- **THEN** the API response `filename` field SHALL contain `my-car.jpg`

#### Scenario: Download uses original filename
- **WHEN** a user downloads an uploaded image via `FileService.download_image`
- **THEN** the `Content-Disposition` header SHALL use the original user-supplied filename

### Requirement: Processed and comparison image filenames derive from GUID-based original
When `image_processing_service.py` or the monolithic `views.py` generates processed (`processed_*`) or comparison (`comparison_*`) output filenames, they SHALL derive the base name from the GUID-prefixed on-disk filename to avoid collisions.

#### Scenario: Processed output filename is collision-free
- **WHEN** two images with the same original name are both processed
- **THEN** their processed output files SHALL have distinct paths
