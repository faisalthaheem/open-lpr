## ADDED Requirements

### Requirement: Keyboard accessibility for fullscreen preview

All previewable images SHALL have `tabindex="0"`, `role="button"`, and a `keydown` event listener that triggers the fullscreen preview on Enter or Space key press. This enables keyboard-only users to access the fullscreen preview.

#### Scenario: Open preview with Enter key
- **WHEN** a previewable image has keyboard focus and the user presses Enter
- **THEN** the fullscreen preview overlay SHALL open

#### Scenario: Open preview with Space key
- **WHEN** a previewable image has keyboard focus and the user presses Space
- **THEN** the fullscreen preview overlay SHALL open

#### Scenario: Previewable images are focusable
- **WHEN** the user presses Tab to navigate through the page
- **THEN** previewable images SHALL receive focus with a visible focus indicator

### Requirement: Dynamic alt text for fullscreen preview

The `openFullscreenPreview()` function SHALL dynamically update the `alt` attribute of the fullscreen preview image to include descriptive context (e.g., "Full size preview of <filename>" or "Full size preview of processed image").

#### Scenario: Alt text reflects image context
- **WHEN** a user opens the fullscreen preview for an image
- **THEN** the preview image `alt` attribute SHALL contain descriptive text indicating what image is being previewed
