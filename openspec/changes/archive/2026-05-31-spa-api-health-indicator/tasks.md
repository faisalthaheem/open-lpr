## 1. Backend Endpoints

- [x] 1.1 Add `PROMETHEUS_URL` setting to `lpr_project/settings.py` with default `http://prometheus:9090` and `python-decouple` config
- [x] 1.2 Create `api_health_light` view in `lpr_app/views/api_views.py` that checks DB via `SELECT 1` and returns `{status, database_healthy, timestamp}` with HTTP 200 or 503
- [x] 1.3 Create `api_availability` view in `lpr_app/views/api_views.py` that queries Prometheus `api/v1/query_range` for `avg_over_time(lpr_api_health_status[5m])` and returns JSON `{timestamp, value}[]` array, accepts `?days=N` param (default 3)
- [x] 1.4 Add URL routes for both new endpoints in `lpr_app/urls.py`: `/api/v1/health-light/` and `/api/v1/availability/`
- [x] 1.5 Add `PROMETHEUS_URL` to `.env.example`, `.env.llamacpp.example`, and `docker-compose.yaml` environment section
- [x] 1.6 Write backend tests for both endpoints (healthy/unhealthy/prometheus-down scenarios)

## 2. SPA — Charting Dependency

- [x] 2.1 Install `recharts` npm package in `single-page-ui/` and verify it builds without errors

## 3. SPA — Health Polling Infrastructure

- [x] 3.1 Add `checkHealthLight()` and `getAvailability(days)` functions to `single-page-ui/src/lib/api.ts`
- [x] 3.2 Create `single-page-ui/src/components/HealthContext.tsx` — React context provider that polls `/api/v1/health-light/` every 30s and exposes `{isHealthy, status, lastChecked, isLoading}`

## 4. SPA — Health Indicator Component

- [x] 4.1 Create `single-page-ui/src/components/HealthIndicator.tsx` — displays green/red/gray icon + text label ("Service Up" / "Service Down" / "Checking...") consuming `HealthContext`
- [x] 4.2 Integrate `HealthIndicator` into the navbar section of `single-page-ui/src/app/layout.tsx`
- [x] 4.3 Wrap app content with `HealthContext.Provider` in `layout.tsx` (inside `AppInitializer`)

## 5. SPA — Upload Form Disable

- [x] 5.1 Add `disabled` prop to `UploadForm` component that visually disables the drag-and-drop zone and upload button, and prevents file selection
- [x] 5.2 Pass `disabled={!isHealthy}` from `HealthContext` to `UploadForm` in `single-page-ui/src/app/page.tsx`
- [x] 5.3 Ensure in-progress uploads are not interrupted when health status changes to unhealthy (only prevent new uploads)

## 6. SPA — Availability Graph

- [x] 6.1 Create `single-page-ui/src/components/AvailabilityGraph.tsx` — recharts `AreaChart` that fetches `/api/v1/availability/?days=3` and renders a line chart with time X-axis and percentage Y-axis, with dark mode support and error fallback
- [x] 6.2 Add `AvailabilityGraph` to the home page (`single-page-ui/src/app/page.tsx`) below the upload form section

## 7. Verification

- [x] 7.1 Verify health indicator shows green when backend is running and red when backend is stopped
- [x] 7.2 Verify upload form is disabled when health indicator shows unhealthy
- [x] 7.3 Verify availability graph renders data points when Prometheus has historical data
- [x] 7.4 Verify availability graph shows fallback message when Prometheus is unavailable
- [x] 7.5 Verify health indicator and graph support dark mode
