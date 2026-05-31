## ADDED Requirements

### Requirement: Lightweight health endpoint
The backend SHALL expose a `GET /api/v1/health-light/` endpoint that checks only database connectivity and returns a JSON response with health status, without making any AI model inference calls.

#### Scenario: Database is healthy
- **WHEN** a GET request is made to `/api/v1/health-light/` and the database is reachable
- **THEN** the endpoint SHALL return HTTP 200 with `{status: "healthy", database_healthy: true, timestamp: "<ISO 8601>"}`

#### Scenario: Database is unhealthy
- **WHEN** a GET request is made to `/api/v1/health-light/` and the database is unreachable
- **THEN** the endpoint SHALL return HTTP 503 with `{status: "unhealthy", database_healthy: false, timestamp: "<ISO 8601>"}`

#### Scenario: No AI model call
- **WHEN** a GET request is made to `/api/v1/health-light/`
- **THEN** the endpoint SHALL NOT call any AI model inference endpoint (no `chat.completions.create` or equivalent)

### Requirement: Prometheus availability proxy endpoint
The backend SHALL expose a `GET /api/v1/availability/` endpoint that queries Prometheus for `lpr_api_health_status` data over a configurable time range and returns JSON-formatted time series data.

#### Scenario: Default 3-day availability
- **WHEN** a GET request is made to `/api/v1/availability/` with no query parameters
- **THEN** the endpoint SHALL query Prometheus for `avg_over_time(lpr_api_health_status[5m])` over the last 3 days and return a JSON array of `{timestamp: "<ISO 8601>", value: <float>}` data points

#### Scenario: Custom time range
- **WHEN** a GET request is made to `/api/v1/availability/?days=1`
- **THEN** the endpoint SHALL query Prometheus for the last 1 day of data

#### Scenario: Prometheus unavailable
- **WHEN** Prometheus is unreachable or returns an error
- **THEN** the endpoint SHALL return HTTP 503 with `{error: "Prometheus unavailable"}` and SHALL NOT return a 500 error or crash

### Requirement: Prometheus connection configuration
The Prometheus proxy endpoint SHALL use a configurable base URL for the Prometheus server, defaulting to `http://prometheus:9090`.

#### Scenario: Default Prometheus URL
- **WHEN** no `PROMETHEUS_URL` setting is provided
- **THEN** the endpoint SHALL connect to `http://prometheus:9090`

#### Scenario: Custom Prometheus URL
- **WHEN** `PROMETHEUS_URL` is set in Django settings
- **THEN** the endpoint SHALL use that URL for Prometheus API calls
