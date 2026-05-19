## ADDED Requirements

### Requirement: Error page template

The system SHALL provide an `error.html` template at `templates/lpr_app/error.html` that extends `base.html` and displays error information in a styled card.

The template SHALL accept `error_title` and `error_message` context variables and render them in a Bootstrap card with:
- A card header containing the error title with an alert icon
- A card body containing the error message
- A "Go Back" link/button that uses `javascript:history.back()`

The template SHALL work correctly in both light and dark modes using existing CSS custom properties.

#### Scenario: Error page renders for invalid image ID
- **WHEN** a user navigates to `/image/99999/` and no image with that ID exists
- **THEN** the system renders `error.html` with an appropriate error title and message

#### Scenario: Error page in dark mode
- **WHEN** the user is in dark mode and an error page is displayed
- **THEN** the error card renders with proper dark mode colors using CSS custom properties

#### Scenario: Error page back navigation
- **WHEN** the error page is displayed
- **THEN** a "Go Back" button is visible and navigates to the previous page when clicked

### Requirement: AJAX error handler selector fix

The `handleAjaxError` function in `base.html` SHALL use the correct DOM selector (`main.container` or `main`) to find the container element for inserting error alerts. The current selector `main .container` returns `null` because `<main>` is itself the container with no nested `.container`.

#### Scenario: AJAX error displays visible alert
- **WHEN** an AJAX request fails (e.g., upload error, processing failure)
- **THEN** a visible Bootstrap danger alert SHALL appear at the top of the main content area with the error message
