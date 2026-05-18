## ADDED Requirements

### Requirement: Fullscreen image preview overlay
The system SHALL provide a fullscreen overlay that displays images at maximum size when clicked. The overlay SHALL cover the entire viewport (`100vw` x `100vh`) with a dark background and display the image centered using `object-fit: contain`.

#### Scenario: User clicks an image on the results page
- **WHEN** a user clicks any image on the results page
- **THEN** a fullscreen overlay SHALL appear showing the image scaled to fill the viewport while preserving aspect ratio

#### Scenario: User clicks an image on the image detail page
- **WHEN** a user clicks the original or processed image on the image detail page
- **THEN** a fullscreen overlay SHALL appear showing the image at maximum size

#### Scenario: User clicks an image on the image list page
- **WHEN** a user clicks a card image in the image history list
- **THEN** a fullscreen overlay SHALL appear showing the full-size image

### Requirement: Close the fullscreen preview
The fullscreen preview SHALL be dismissible by clicking the overlay background, pressing the Escape key, or clicking a close button in the top-right corner.

#### Scenario: Close by clicking background
- **WHEN** the fullscreen preview is open and the user clicks the dark background (not the image)
- **THEN** the preview SHALL close

#### Scenario: Close by pressing Escape
- **WHEN** the fullscreen preview is open and the user presses the Escape key
- **THEN** the preview SHALL close

#### Scenario: Close button
- **WHEN** the fullscreen preview is open
- **THEN** a close button SHALL be visible in the top-right corner

### Requirement: Shared implementation across pages
The fullscreen preview overlay HTML, CSS, and JavaScript SHALL be defined in the base template (`base.html`) so all pages inherit the behavior. Individual page templates SHALL only attach click handlers to their images.

#### Scenario: Preview works on all pages without duplication
- **WHEN** the base template is loaded on any page
- **THEN** the fullscreen preview overlay, styles, and JavaScript SHALL be available

### Requirement: Dark mode compatible
The fullscreen preview overlay SHALL use the existing theme CSS variables so it renders correctly in both light and dark mode.

#### Scenario: Preview in dark mode
- **WHEN** the user is in dark mode and opens the fullscreen preview
- **THEN** the overlay background SHALL be dark and the close button SHALL be visible
