## ADDED Requirements

### Requirement: SPA application structure
The system SHALL provide a standalone Next.js single-page UI application in a `single-page-ui/` directory with its own `package.json`, App Router structure, React components, and Tailwind CSS — independent of Django templates.

#### Scenario: SPA served independently
- **WHEN** the SPA application is built (`next build`) and served (via `next start` or static export with nginx)
- **THEN** the application SHALL render the home page with an upload form

#### Scenario: Client-side routing
- **WHEN** the user navigates between pages (home, image list, image detail)
- **THEN** the SPA SHALL handle navigation via Next.js App Router file-based routing (`/`, `/images`, `/image/:id`) without full page reloads

### Requirement: Image upload
The SPA SHALL provide a file upload interface that submits images to the backend API and displays processing results.

#### Scenario: Successful upload via SPA
- **WHEN** the user selects or drags an image file and submits
- **THEN** the SPA SHALL POST the image to `/api/v1/ocr/` on the configured backend URL, display a loading indicator, and redirect to the image detail view on success

#### Scenario: Upload error handling
- **WHEN** the upload API returns an error
- **THEN** the SPA SHALL display the error message to the user and allow retry

### Requirement: Image list view
The SPA SHALL display a paginated list of processed images with search and filtering.

#### Scenario: Browsing images
- **WHEN** the user navigates to the image list view
- **THEN** the SPA SHALL fetch images from the API and render them as a paginated card grid showing thumbnails, filenames, status, and timestamps

#### Scenario: Searching and filtering
- **WHEN** the user enters a search query or selects filter criteria (date range, status)
- **THEN** the SPA SHALL pass the filters as query parameters to the API and update the displayed results

#### Scenario: Pagination
- **WHEN** there are more images than one page can display
- **THEN** the SPA SHALL render pagination controls and fetch the requested page from the API

### Requirement: Image detail view
The SPA SHALL display detailed information for a single image including original/processed images, detection results, and OCR text.

#### Scenario: Viewing image details
- **WHEN** the user navigates to the detail view for a specific image
- **THEN** the SPA SHALL fetch image details from the API and render original and processed images side by side, detection summary, and OCR results

#### Scenario: Download from detail view
- **WHEN** the user clicks a download button on the detail view
- **THEN** the SPA SHALL initiate a download of the requested image file (original or processed) via the backend download endpoint

### Requirement: Configurable backend URL
The SPA SHALL allow the backend API URL to be configured at deployment time.

#### Scenario: Default backend URL
- **WHEN** no custom backend URL is configured
- **THEN** the SPA SHALL default to the same origin (relative API paths)

#### Scenario: Custom backend URL
- **WHEN** a `NEXT_PUBLIC_API_BASE_URL` environment variable is set
- **THEN** the SPA SHALL use that URL as the base for all API requests

### Requirement: Light and dark theme
The SPA SHALL support light and dark themes, matching the existing UI's theming behavior.

#### Scenario: Theme toggle
- **WHEN** the user clicks the theme toggle button
- **THEN** the SPA SHALL switch between light and dark themes and persist the preference in localStorage

#### Scenario: System preference detection
- **WHEN** the SPA loads for the first time with no saved theme preference
- **THEN** the SPA SHALL detect the system's `prefers-color-scheme` and apply the matching theme

### Requirement: Health check link
The SPA SHALL provide a link to the backend health check endpoint.

#### Scenario: Health check navigation
- **WHEN** the user clicks the health check link in the navigation
- **THEN** the SPA SHALL open the backend's `/health/` endpoint in a new browser tab
