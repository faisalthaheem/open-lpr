## ADDED Requirements

### Requirement: Windowed desktop pagination

The image list page SHALL use windowed pagination for desktop view that shows a bounded set of page numbers with ellipsis indicators. The pagination SHALL display:
- First page always
- Last page always (when total pages > 1)
- Current page
- 2 pages before and 2 pages after the current page
- Ellipsis (`...`) between non-contiguous page ranges
- Previous/Next navigation buttons

The pagination SHALL NOT render hardcoded `elif` chains or show more than 9 page buttons at a time (first + ellipsis + 2 before + current + 2 after + ellipsis + last).

#### Scenario: User on page 1 of 50
- **WHEN** the user is on page 1 of 50 total pages
- **THEN** the pagination shows pages: 1, 2, 3, ..., 50

#### Scenario: User on page 25 of 50
- **WHEN** the user is on page 25 of 50 total pages
- **THEN** the pagination shows pages: 1, ..., 23, 24, 25, 26, 27, ..., 50

#### Scenario: User on page 50 of 50
- **WHEN** the user is on the last page (50 of 50)
- **THEN** the pagination shows pages: 1, ..., 48, 49, 50

#### Scenario: User on page 3 of 5
- **WHEN** there are only 5 total pages and the user is on page 3
- **THEN** the pagination shows pages: 1, 2, 3, 4, 5 (no ellipsis needed)

#### Scenario: Single page of results
- **WHEN** there is only 1 page of results
- **THEN** the pagination controls are hidden entirely

### Requirement: Bounded mobile pagination

The mobile pagination SHALL use the same windowed logic as desktop pagination, rendering a horizontal scrolling strip of bounded page numbers with ellipsis. The mobile pagination SHALL NOT render all pages.

#### Scenario: Mobile user on page 25 of 50
- **WHEN** a mobile user views the pagination strip on page 25 of 50
- **THEN** the same windowed page numbers appear as desktop: 1, ..., 23, 24, 25, 26, 27, ..., 50

#### Scenario: Mobile pagination has ARIA label
- **WHEN** the mobile pagination is rendered
- **THEN** the container has `role="navigation"` and `aria-label="Image pagination"`

### Requirement: Shared pagination partial template

The windowed pagination logic SHALL be implemented in a shared partial template (`templates/lpr_app/_pagination.html`) that accepts `page_obj` as context and renders both desktop and mobile variants. The `image_list.html` template SHALL include this partial instead of inline pagination logic.

#### Scenario: Pagination partial is reusable
- **WHEN** any template includes `{% include "lpr_app/_pagination.html" %}` with a `page_obj` context variable
- **THEN** the pagination renders correctly with windowed page numbers
