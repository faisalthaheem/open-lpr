## ADDED Requirements

### Requirement: Health status indicator in navbar
The SPA SHALL display a health status indicator in the navbar/header that shows the current backend health state with a visual icon and text label.

#### Scenario: Backend is healthy
- **WHEN** the backend health check returns a healthy status
- **THEN** the indicator SHALL show a green icon with "Service Up" text

#### Scenario: Backend is unhealthy
- **WHEN** the backend health check returns an unhealthy status or the request fails
- **THEN** the indicator SHALL show a red icon with "Service Down" text

#### Scenario: Health check pending
- **WHEN** the initial health check has not yet completed
- **THEN** the indicator SHALL show a gray/yellow icon with "Checking..." text

### Requirement: Periodic health polling
The SPA SHALL poll the backend health endpoint at a regular interval to maintain an up-to-date status.

#### Scenario: Automatic polling
- **WHEN** the SPA is loaded and running
- **THEN** it SHALL poll the lightweight health endpoint every 30 seconds

#### Scenario: Polling uses lightweight endpoint
- **WHEN** the SPA performs a health check poll
- **THEN** it SHALL call `/api/v1/health-light/` (not the full `/health/` endpoint)

### Requirement: Upload form disabled when unhealthy
The SPA SHALL disable the upload form when the backend health status is unhealthy.

#### Scenario: Upload disabled during outage
- **WHEN** the health status is unhealthy
- **THEN** the upload form drag-and-drop zone and upload button SHALL be visually disabled and SHALL NOT accept file uploads

#### Scenario: Upload re-enabled when healthy
- **WHEN** the health status transitions from unhealthy to healthy
- **THEN** the upload form SHALL return to its normal interactive state

#### Scenario: In-progress upload not interrupted
- **WHEN** an upload is already in progress and the health status becomes unhealthy
- **THEN** the in-progress upload SHALL continue without interruption
