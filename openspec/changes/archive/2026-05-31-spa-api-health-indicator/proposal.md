## Why

Users have no visibility into backend API availability from the SPA. When the AI model service is down, uploads fail after a long timeout with a confusing error. Users need a real-time health indicator and the upload form should be disabled when the backend is unavailable. A historical availability graph over the last 3 days gives users and operators confidence in system reliability.

## What Changes

- Add a backend health status indicator (icon + text) to the SPA navbar/header that polls the `/health/` endpoint and shows healthy/degraded/unhealthy state
- Disable the upload form (drag-and-drop zone + button) when the backend API is unhealthy
- Add a lightweight `/api/v1/health-light/` backend endpoint that checks only database connectivity (not the expensive AI model inference call) for frequent SPA polling
- Add an availability graph to the home page showing backend health over the last 3 days, sourced from Prometheus metrics via a new backend API endpoint that proxies Prometheus range queries
- Add a charting library dependency to the SPA (e.g., recharts)

## Capabilities

### New Capabilities

- `spa-health-indicator`: Real-time backend health status indicator in the SPA navbar with polling, and upload form disabling when unhealthy
- `spa-availability-graph`: Historical availability graph on the SPA home page showing backend uptime over the last 3 days, using Prometheus data via a backend proxy endpoint
- `backend-health-light`: Lightweight backend health endpoint that checks only database connectivity without expensive AI model inference, suitable for frequent SPA polling

### Modified Capabilities

(No existing specs are being modified at the requirement level)

## Impact

- **SPA frontend** (`single-page-ui/src/`): New components (HealthIndicator, AvailabilityGraph), modified UploadForm (disabled state), modified layout (navbar), new API functions in `lib/api.ts`, new charting dependency
- **Backend** (`lpr_app/views/api_views.py`, `lpr_app/urls.py`): New lightweight health endpoint, new Prometheus proxy endpoint
- **Dependencies**: New npm package for charting in SPA (recharts), no new Python dependencies
