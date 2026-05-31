## Context

The SPA frontend has no visibility into backend API health. When the AI model service is down, users experience long upload timeouts with no explanation. The existing `/health/` endpoint performs an expensive AI inference call (`chat.completions.create` with `max_tokens=10`) which makes it unsuitable for frequent SPA polling (every 10-30 seconds).

The system already has Prometheus scraping `lpr_api_health_status` every 15 seconds and Grafana visualizing it. However, the SPA cannot query Prometheus directly (it's on an internal network). A backend proxy endpoint is needed.

The SPA uses Next.js 16 with React 19, Tailwind CSS 4, and has no charting library installed.

## Goals / Non-Goals

**Goals:**
- Show real-time backend health status in the SPA header
- Disable uploads when the backend is unhealthy
- Display 3-day availability history on the home page
- Keep polling lightweight (no expensive AI calls from SPA health checks)

**Non-Goals:**
- Replacing or modifying the existing `/health/` endpoint (it remains for Prometheus/blackbox)
- Adding authentication to any new endpoints
- Modifying the Prometheus or Grafana setup
- Adding alerting or notification features

## Decisions

### Decision 1: New lightweight health endpoint instead of polling existing one

The existing `/health/` calls `chat.completions.create()` which costs real GPU/CPU time. The SPA will poll frequently (every 30s), so a lightweight endpoint that only checks database connectivity is needed.

**New endpoint**: `GET /api/v1/health-light/` — checks DB connectivity via `SELECT 1`, returns `{status, database_healthy, timestamp}` with HTTP 200 or 503. The SPA uses this for polling. The existing `/health/` continues to be used by Prometheus/blackbox for full-stack monitoring.

**Alternative considered**: Caching the full health check result (e.g., cache for 60s). Rejected because the SPA would still trigger expensive calls every cache expiry, and stale cached results are misleading.

### Decision 2: Backend proxy for Prometheus data instead of direct Prometheus access

Prometheus runs on an internal Docker network port (9090) not accessible from the browser. The backend will expose a proxy endpoint that queries Prometheus's HTTP API and returns formatted availability data.

**New endpoint**: `GET /api/v1/availability/?days=3` — backend queries Prometheus API at `http://prometheus:9090/api/v1/query_range` for `avg_over_time(lpr_api_health_status[5m])` over the requested time range, returns JSON array of `{timestamp, value}` data points.

**Alternative considered**: Adding Prometheus as a public endpoint. Rejected for security — Prometheus should not be exposed publicly. The backend proxy allows controlled access with the option to add rate limiting.

### Decision 3: recharts for charting

**recharts** is a React-native charting library built on D3. Chosen because:
- Declarative React component API fits the existing codebase style
- Small bundle size for the features needed (line chart)
- Well-maintained, widely used (25k+ GitHub stars)
- TypeScript support

**Alternative considered**: chart.js + react-chartjs-2. Rejected because it requires manual canvas management and has a more imperative API.

### Decision 4: Polling architecture — React context + interval

A `HealthContext` provider will poll `/api/v1/health-light/` every 30 seconds and expose `{status, lastChecked, isHealthy}` to all components. The provider wraps the app inside `AppInitializer`. The `UploadForm` consumes this context to disable uploads. A `HealthIndicator` component in the navbar shows the current status.

**Alternative considered**: Server-sent events (SSE) or WebSocket. Rejected — overkill for a health status that changes infrequently. Simple polling is sufficient and simpler to implement.

## Risks / Trade-offs

- **[Lightweight health doesn't catch AI model outages]** → Accepted. The SPA indicator shows database connectivity. The full health check (including AI model) is monitored by Prometheus/blackbox and visible in Grafana. Adding a separate "AI model status" indicator could be a future enhancement.
- **[Prometheus proxy endpoint availability]** → If Prometheus is down, the availability graph shows an error state. The health indicator (light endpoint) is independent and still works. Low risk since Prometheus runs in the same Docker network.
- **[Polling frequency]** → 30-second interval is a balance between responsiveness and server load. The lightweight endpoint does only a `SELECT 1` query — negligible cost even at high frequency.
- **[recharts bundle size]** → ~45KB gzipped. Acceptable for a single page app. The chart is only rendered on the home page, so it could be lazy-loaded if needed.
