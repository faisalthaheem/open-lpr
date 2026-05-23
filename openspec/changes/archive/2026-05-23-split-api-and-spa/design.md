## Context

The application is a monolithic Django 4.2 project that serves server-rendered HTML templates (Bootstrap 5.3, inline JS/CSS) alongside REST API endpoints from a single process. The frontend has no build pipeline — all JS and CSS lives inline in Django templates under `templates/`. The only static assets are favicons. The backend uses Gunicorn, SQLite, and Docker Compose with profile-based services.

Current URL routing splits into web views (`web_views.py` — home, upload, image list, image detail) and API views (`api_views.py` — `/api/v1/ocr/`, `/health/`, `/metrics/`). Web views rely on Django forms, template rendering, and `FileService` for downloads.

## Goals / Non-Goals

**Goals:**
- Separate the frontend into a standalone Next.js SPA that can be served independently
- Make the Django backend a pure API service (JSON-only, no template rendering)
- Add read-only API endpoints to expose image listing, detail, and download currently only only available via HTML views
- Add CORS support so the SPA can call the API from a different origin/port
- Update Docker Compose to run both services independently

**Non-Goals:**
- Rewriting the backend in a different framework — Django stays
- Adding authentication or user management
- Changing the OCR pipeline, detection logic, or AI model integration
- Removing the existing Django templates immediately (they remain in the repo but are no longer routed)
- Adding WebSocket support or real-time features
- Using Next.js server-side features (SSR, ISR, server components) — the SPA will use client-side rendering only, running as a static export or standalone Node server

## Decisions

### 1. Next.js with App Router
**Decision**: Build the SPA using Next.js with the App Router.
**Rationale**: Next.js is the most widely adopted React framework with excellent developer experience, file-based routing, built-in image optimization, and a large ecosystem. The App Router is the modern standard. Using React components provides better state management, composability, and maintainability than vanilla JS for a multi-view application with forms, pagination, and complex data display.
**Alternative considered**: Vanilla JS — rejected due to poor maintainability as the UI grows.

### 2. Client-side rendering only
**Decision**: Use Next.js purely as a client-side SPA. All pages will use `"use client"` directive. No server components, SSR, or ISR.
**Rationale**: The backend is a separate Django API. There is no need for server-side rendering in the frontend — all data comes from API calls. This keeps the SPA simple and deployable as a static export or lightweight Node server.

### 3. Tailwind CSS for styling
**Decision**: Use Tailwind CSS for styling, replacing the inline Bootstrap CSS from the Django templates.
**Rationale**: Tailwind is the default styling solution in Next.js. It provides utility-first CSS that maps well to the existing Bootstrap-based layout. Avoids duplicating the inline CSS from Django templates. Ships only the CSS actually used.
**Alternative considered**: Port Bootstrap CSS directly — rejected because it fights against Next.js conventions and Tailwind's purge optimization.

### 4. Hash-based routing
**Decision**: Configure Next.js to use hash-based routing (or deploy as a static export with `output: 'export'`).
**Rationale**: Static export produces plain HTML/CSS/JS files that can be served by any static file server (nginx, CDN). No server-side routing needed. Clean deployment story for Docker.
**Alternative considered**: Next.js standalone server — adds Node.js runtime overhead for a simple 4-page app.

### 5. `django-cors-headers` for CORS
**Decision**: Add the `django-cors-headers` package for CORS support.
**Rationale**: Well-maintained, battle-tested Django package. Simple configuration via settings. Handles preflight requests automatically.
**Alternative considered**: Manual CORS middleware — rejected because it's error-prone (preflight handling, credential edge cases).

### 6. Directory structure: `single-page-ui/`
**Decision**: Place the Next.js SPA in a top-level `single-page-ui/` directory alongside `lpr_project/` and `lpr_app/`.
**Rationale**: Clear separation from the Django backend. Each service has its own directory, Dockerfile, and deployment lifecycle.
**Structure**:
```
single-page-ui/
  package.json
  next.config.js
  tailwind.config.js
  postcss.config.js
  tsconfig.json
  public/
    favicon.ico
    favicon.svg
  src/
    app/
      layout.tsx        # Root layout with nav, theme provider
      page.tsx           # Home / upload page
      images/
        page.tsx         # Image list with search/filter/pagination
      image/
        [id]/
          page.tsx       # Image detail view
    components/
      Navbar.tsx
      ThemeToggle.tsx
      ImageCard.tsx
      Pagination.tsx
      SearchForm.tsx
      DetectionDetail.tsx
      UploadForm.tsx
    lib/
      api.ts             # API client with configurable BASE_URL
    hooks/
      useTheme.ts
```

### 7. New API endpoints
**Decision**: Add three new read-only endpoints under `/api/v1/`:
- `GET /api/v1/images/` — paginated list with search/filter
- `GET /api/v1/images/<id>/` — full detail with detections
- `GET /api/v1/download/<id>/<type>/` — file download (reuses existing `FileService`)

The existing `/api/v1/ocr/` POST endpoint continues unchanged.

**Rationale**: The SPA needs the same data the web views currently render server-side. These endpoints expose that data as JSON.

### 8. Docker Compose SPA service
**Decision**: Add a `spa` service to Docker Compose using a multi-stage Next.js Dockerfile that builds and serves the static export via `nginx:alpine`, with a proxy pass for API requests.
**Rationale**: Nginx is the standard for serving static files in production. It can proxy `/api/` requests to the backend, avoiding CORS issues in the Docker deployment. The CORS config remains useful for local development.

## Risks / Trade-offs

- **Risk**: Next.js adds a Node.js build dependency and heavier `node_modules` → Mitigation: Multi-stage Docker build keeps the production image lean (nginx + static files only).
- **Risk**: Tailwind CSS differs from Bootstrap, so the UI won't be pixel-identical → Mitigation: Focus on functional parity, not visual parity. Tailwind makes it easy to replicate the layout.
- **Risk**: Porting inline template JS/CSS to React components may introduce subtle bugs → Mitigation: Port incrementally, testing each view against the original behavior.
- **Risk**: Duplicate CSS/styling logic between Django templates and SPA during transition → Mitigation: Accept temporary duplication; templates will eventually be removed.
