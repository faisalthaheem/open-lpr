## 1. Django Settings & Configuration

- [x] 1.1 Add `RATE_LIMIT_ENABLE`, `RATE_LIMIT_RATE`, and `RATE_LIMIT_EXCLUDE_PATHS` settings to `lpr_project/settings.py` using `python-decouple` `config()` with appropriate defaults
- [x] 1.2 Conditionally add DRF throttle classes to `REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES']` and `REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']` based on `RATE_LIMIT_ENABLE`
- [x] 1.3 Add the three new env vars to `.env.example`, `.env.llamacpp.example`, and `docker-compose.yaml`

## 2. Custom Throttle Implementation

- [x] 2.1 Create a custom throttle class (e.g., `ExcludableAnonRateThrottle`) in `lpr_app/services/` or `lpr_app/utils/` that extends `AnonRateThrottle` and skips rate limiting for paths matching `RATE_LIMIT_EXCLUDE_PATHS`
- [x] 2.2 Register the custom throttle class in DRF settings instead of the default `AnonRateThrottle`

## 3. Rate Limit Headers

- [x] 3.1 Ensure 429 responses include `Retry-After` header (DRF default behavior — verify)
- [x] 3.2 Add `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` headers to all API responses when rate limiting is enabled (via custom throttle class or middleware)

## 4. Tests

- [x] 4.1 Write tests for: requests within rate limit succeed with rate limit headers
- [x] 4.2 Write tests for: requests exceeding rate limit receive 429 with `Retry-After` header
- [x] 4.3 Write tests for: health endpoints are not rate limited
- [x] 4.4 Write tests for: `RATE_LIMIT_ENABLE=False` disables all rate limiting
- [x] 4.5 Write tests for: custom `RATE_LIMIT_RATE` is respected

## 5. Documentation

- [x] 5.1 Update `AGENTS.md` Environment Variables section with the three new env vars
- [x] 5.2 Verify the SPA handles 429 responses gracefully (shows error message to user)
