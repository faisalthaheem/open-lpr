## Why

The demo system at openlpr.computedsynergy.com is publicly accessible and has no request throttling. A single user (or bot) can flood the API with uploads, consuming GPU inference resources and potentially making the service unavailable for others. Rate limiting is needed to prevent abuse.

## What Changes

- Add per-IP rate limiting to all REST API endpoints, defaulting to 1 request every 30 seconds
- Make rate limiting configurable via environment variables (requests per period, period duration)
- Allow rate limiting to be disabled entirely via an environment variable
- Add rate limit headers to API responses (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`)
- Return HTTP 429 with a JSON error body when the limit is exceeded
- Configure defaults in Docker Compose and `.env.example` / `.env.llamacpp.example`
- Health and light-health endpoints should be excluded from rate limiting

## Capabilities

### New Capabilities
- `api-rate-limiting`: Per-IP rate limiting on REST API endpoints with configurable thresholds, standard rate limit headers, and opt-out via environment variable

### Modified Capabilities

## Impact

- **Django backend**: New middleware or DRF throttle class, new settings, new dependency (`django-ratelimit` or DRF built-in throttling)
- **API responses**: All endpoints gain rate limit headers; limited requests receive 429 responses
- **Docker Compose / env files**: New environment variables for rate limit configuration
- **AGENTS.md**: Document new environment variables
- **Tests**: Unit tests for rate limiting behavior
