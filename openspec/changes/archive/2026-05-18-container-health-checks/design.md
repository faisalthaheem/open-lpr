## Context

The docker-compose.yaml defines 8 services across profiles. Three llamacpp inference services and lpr-app already have health checks. Four core monitoring and utility services do not: prometheus, grafana, blackbox-exporter, and lpr-canary. All four expose HTTP endpoints that can be used for health probing.

## Goals / Non-Goals

**Goals:**
- Add health checks to all 4 services missing them.
- Use each service's native health/metrics endpoint where available.
- Keep health check parameters consistent with existing services (interval, timeout, retries, start_period).

**Non-Goals:**
- Adding `depends_on` with health condition between services.
- Changing existing health checks on lpr-app or llamacpp services.
- Adding health checks to services that aren't part of the standard deployment profiles.

## Decisions

**1. Use native HTTP health endpoints**

Each service already exposes an endpoint suitable for health checking:

| Service | Endpoint | Notes |
|---|---|---|
| prometheus | `/-/healthy` | Returns 200 when Prometheus is ready |
| grafana | `/api/health` | Returns 200 with JSON `{"database": "ok", ...}` |
| blackbox-exporter | `http://localhost:9115` | Root endpoint returns 200 |
| lpr-canary | `http://localhost:9100/metrics` | Prometheus metrics endpoint returns 200 when serving |

**2. Use `wget` for HTTP probes over `curl`**

The Alpine-based images used by prometheus, grafana, and blackbox-exporter may not have `curl` installed, but `wget` is typically available. Use `wget --spider --quiet` for lightweight HTTP status checks that don't download the response body.

**3. Match existing health check parameters**

Use the same timing parameters as existing health checks: `interval: 30s`, `timeout: 10s`, `retries: 3`, `start_period: 40s`.

## Risks / Trade-offs

- **[Health check endpoint may differ by image version]** → Mitigation: Use well-documented stable endpoints (`/-/healthy`, `/api/health`) that are present across major versions.
- **[lpr-canary may not expose /metrics if prometheus client hasn't started]** → Mitigation: The `start_period: 40s` gives the service time to initialize before health checks begin counting retries.
