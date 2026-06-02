## MODIFIED Requirements

### Requirement: Rate limiting is configurable via environment variables
The system SHALL read rate limiting configuration from four environment variables:
- `RATE_LIMIT_ENABLE` (bool, default `True`) — enables or disables rate limiting entirely
- `RATE_LIMIT_RATE` (string, default `"2/min"`) — the throttle rate in `num/period` format
- `RATE_LIMIT_EXCLUDE_PATHS` (comma-separated paths, default `"/health/,/api/v1/health-light/"`) — paths excluded from rate limiting
- `RATE_LIMIT_INCLUDE_PATHS` (comma-separated paths, default `"/api/v1/ocr/"`) — paths to rate limit; all other paths are exempt

#### Scenario: Rate limiting disabled
- **WHEN** `RATE_LIMIT_ENABLE` is set to `False`
- **THEN** no rate limiting is applied to any endpoint

#### Scenario: Custom rate configured
- **WHEN** `RATE_LIMIT_RATE` is set to `"10/hour"`
- **THEN** the system allows 10 requests per hour per IP before throttling

#### Scenario: Include paths limits scope
- **WHEN** `RATE_LIMIT_INCLUDE_PATHS` is set to `"/api/v1/ocr/"`
- **THEN** only requests to `/api/v1/ocr/` are rate limited; requests to all other paths are not rate limited

#### Scenario: Non-included path not rate limited
- **WHEN** a client sends 10 rapid requests to `/api/v1/config/` and `RATE_LIMIT_INCLUDE_PATHS` is set to `"/api/v1/ocr/"`
- **THEN** all requests are processed normally without rate limiting
