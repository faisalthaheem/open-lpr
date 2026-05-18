## ADDED Requirements

### Requirement: Home page image preview

The home page recent uploads section SHALL allow users to click on thumbnail images to open a fullscreen preview overlay, using the shared `openFullscreenPreview()` function from `base.html`.

#### Scenario: Click thumbnail to preview
- **WHEN** a user clicks on a thumbnail image in the "Recent Uploads" section of the home page
- **THEN** the fullscreen preview overlay opens showing the image at full size

#### Scenario: Close preview overlay
- **WHEN** the fullscreen preview is open and the user clicks the overlay background or close button or presses Escape
- **THEN** the preview overlay closes

#### Scenario: Visual affordance on hover
- **WHEN** a user hovers over a thumbnail image in the recent uploads section
- **THEN** the cursor changes to pointer and a tooltip shows "Click to preview"
