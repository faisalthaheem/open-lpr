## ADDED Requirements

### Requirement: Rate limiting is enforced on all API endpoints
The system SHALL enforce per-IP rate limiting on all REST API endpoints under `/api/v1/` by default.

#### Scenario: Request within rate limit
- **WHEN** a client sends a request to any `/api/v1/` endpoint and has not exceeded the rate limit
- **THEN** the system processes the request normally and includes rate limit headers in the response

#### Scenario: Request exceeds rate limit
- **WHEN** a client sends a request to any `/api/v1/` endpoint and has exceeded the configured rate limit
- **THEN** the system returns HTTP 429 with a JSON body containing an error message and a `Retry-After` header

### Requirement: Rate limiting is configurable via environment variables
The system SHALL read rate limiting configuration from three environment variables:
- `RATE_LIMIT_ENABLE` (bool, default `True`) — enables or disables rate limiting entirely
- `RATE_LIMIT_RATE` (string, default `"2/min"`) — the throttle rate in DRF format
- `RATE_LIMIT_EXCLUDE_PATHS` (comma-separated paths, default `"/health/,/api/v1/health-light/"`) — paths excluded from rate limiting

#### Scenario: Rate limiting disabled
- **WHEN** `RATE_LIMIT_ENABLE` is set to `False`
- **THEN** no rate limiting is applied to any endpoint

#### Scenario: Custom rate configured
- **WHEN** `RATE_LIMIT_RATE` is set to `"10/hour"`
- **THEN** the system allows 10 requests per hour per IP before throttling

### Requirement: Health check endpoints are excluded from rate limiting
The system SHALL NOT apply rate limiting to health check endpoints (`/health/`, `/api/v1/health-light/`).

#### Scenario: Health check not rate limited
- **WHEN** a client sends repeated requests to `/api/v1/health-light/` exceeding the configured rate limit
- **THEN** the system processes all requests normally without returning 429

### Requirement: Rate limited responses include standard headers
The system SHALL include the following headers in all API responses when rate limiting is enabled:
- `Retry-After` — seconds until the client can make another request (on 429 responses only)
- `X-RateLimit-Limit` — the configured limit
- `X-RateLimit-Remaining` — remaining requests in the current window
- `X-RateLimit-Reset` — seconds until the rate limit window resets

#### Scenario: Rate limit headers present on successful response
- **WHEN** a client makes a successful request to an API endpoint
- **THEN** the response includes `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` headers

#### Scenario: Retry-After header on 429 response
- **WHEN** a client is rate limited and receives a 429 response
- **THEN** the response includes a `Retry-After` header with the number of seconds until the limit resets

### Requirement: Rate limit defaults are set in Docker Compose and env files
The system SHALL include default rate limiting configuration in `docker-compose.yaml`, `.env.example`, and `.env.llamacpp.example`.

#### Scenario: Docker deployment has rate limiting enabled by default
- **WHEN** the application is deployed via Docker Compose without overriding rate limit variables
- **THEN** rate limiting is enabled with a default rate of `"2/min"`

### Requirement: Rate limiting uses per-IP tracking
The system SHALL track rate limits per client IP address. Clients behind the same proxy are distinguished by `X-Forwarded-For` header when available.

#### Scenario: Different IPs have separate limits
- **WHEN** client A (IP 1.2.3.4) exceeds the rate limit
- **THEN** client B (IP 5.6.7.8) can still make requests normally
