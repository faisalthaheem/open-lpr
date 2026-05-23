## Why

The current monolith serves both server-rendered HTML pages and a REST API from a single Django process. This coupling makes it impossible to scale the GPU-bound OCR pipeline independently from the UI, prevents deploying the frontend as a lightweight static site or CDN-hosted SPA, and blocks using alternative frontend frameworks without touching the backend. Splitting into two services — a headless API backend and a standalone Next.js single-page UI — enables independent deployment, scaling, and evolution of each layer.

## What Changes

- **BREAKING**: The Django backend will no longer serve HTML templates or web views — all UI interaction moves to a separate Next.js SPA application
- Create a new `single-page-ui/` directory containing a Next.js frontend app with App Router, React components, and Tailwind CSS
- The Django backend becomes a pure API-only service, serving only REST endpoints (`/api/v1/ocr/`, `/health/`, `/metrics/`, `/api/v1/images/`, `/api/v1/images/<id>/`, `/api/v1/download/<id>/<type>/`)
- Add new read-only API endpoints for listing images, retrieving image details, and downloading files (currently only available via server-rendered views)
- Add CORS support to the Django backend so the SPA can call the API from a different origin
- Update Docker Compose to run the SPA as a separate service (Node.js container) alongside the API backend
- The SPA replicates all current UI functionality: upload, image list with search/filter/pagination, image detail with detection results, download, health check link

## Capabilities

### New Capabilities
- `spa-frontend`: Standalone Next.js single-page UI application with App Router, React components, and API integration
- `api-image-list`: REST API endpoint for listing images with search, filter, and pagination
- `api-image-detail`: REST API endpoint for retrieving a single image's details and detection results
- `api-cors`: CORS configuration allowing cross-origin requests from the SPA frontend

### Modified Capabilities

## Impact

- **New directory**: `single-page-ui/` with its own `package.json`, Next.js App Router structure, React components, and Tailwind CSS
- **Backend API changes**: `lpr_app/views/api_views.py` gains new list/detail endpoints; `lpr_app/urls.py` adds API routes
- **Backend removal**: `lpr_app/views/web_views.py`, `lpr_app/forms.py`, template rendering, and template-related code become unused (backend becomes API-only)
- **Docker**: New SPA service in `docker-compose.yaml`; existing `lpr-app` service becomes API-only
- **CORS**: `lpr_project/settings.py` gains CORS configuration (via `django-cors-headers`)
- **Templates**: Existing Django templates remain in the repo but are no longer served by default (can be removed later)
