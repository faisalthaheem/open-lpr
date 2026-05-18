## Why

Only 4 of the 8 services in `docker-compose.yaml` have health checks defined. The remaining 4 services (prometheus, grafana, blackbox-exporter, lpr-canary) have no health checks, meaning Docker Compose cannot determine if they're actually healthy — only if they're running. This makes it harder to detect service degradation and prevents `depends_on` with condition-based dependencies from working correctly.

## What Changes

- Add health checks to the 4 services that are missing them:
  - **prometheus**: HTTP check against its own `/-/healthy` endpoint
  - **grafana**: HTTP check against its own `/api/health` endpoint
  - **blackbox-exporter**: HTTP check against its own health endpoint
  - **lpr-canary**: HTTP check against its own metrics/prometheus endpoint

## Capabilities

### New Capabilities

### Modified Capabilities

## Impact

- `docker-compose.yaml` — add `healthcheck` blocks to 4 services
