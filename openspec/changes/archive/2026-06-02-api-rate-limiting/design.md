## Context

The Open LPR demo system is a publicly accessible Django REST API backed by a Qwen3-VL vision-language model for license plate recognition. Currently there is no request throttling — any client can make unlimited API calls, consuming GPU inference resources and potentially making the service unavailable.

The system uses Django 5.2 with Django REST Framework (DRF) for API views. All API endpoints are under `/api/v1/`. The health check endpoints (`/api/v1/health-light/` and `/health/`) are lightweight and should not be rate limited.

## Goals / Non-Goals

**Goals:**
- Protect the demo system from API abuse with per-IP rate limiting
- Default to 1 request per 30 seconds per IP on all API endpoints except health checks
- Make rate limiting fully configurable via environment variables (rate, period, enable/disable)
- Return standard HTTP 429 responses with rate limit headers when the limit is exceeded
- Work with the existing Django/DRF stack without external services (Redis, etc.)

**Non-Goals:**
- Per-user or per-API-key rate limiting (no authentication system exists)
- Distributed rate limiting across multiple Django instances (single-server deployment)
- Rate limiting on static assets or the SPA frontend
- CDN-level rate limiting (Cloudflare WAF rules, etc.)

## Decisions

### 1. Use DRF `AnonRateThrottle` for rate limiting

**Decision**: Use Django REST Framework's built-in `AnonRateThrottle` class.

**Rationale**: DRF provides built-in throttling with per-IP anonymous rate limiting. It uses the Django cache framework (defaulting to LocMem cache for single-server deployments). No additional dependencies needed — DRF is already a project dependency.

**Alternatives considered**:
- `django-ratelimit` (third-party decorator-based): More flexible but adds a dependency for functionality DRF already provides.
- Custom middleware: Full control but reinvents what DRF throttling already handles (IP extraction, cache-based tracking, 429 responses, headers).
- Nginx/Traefik rate limiting: Would work at the reverse proxy level but loses the ability to dynamically configure via Django settings/env vars, and the SPA health indicator wouldn't receive 429s with a useful JSON body.

### 2. Cache backend: LocMem cache (default)

**Decision**: Use Django's `LocMemCache` for rate limit state. No configuration changes needed — DRF throttling uses the default cache.

**Rationale**: The demo runs a single Gunicorn worker. LocMem cache is process-local, which is sufficient. No Redis/memcached dependency needed.

### 3. Configuration via environment variables

**Decision**: Three new environment variables:
- `RATE_LIMIT_ENABLE` (bool, default `True`) — master toggle
- `RATE_LIMIT_RATE` (string, default `"2/min"`) — DRF throttle rate format (maps to roughly 1 request per 30 seconds)
- `RATE_LIMIT_EXCLUDE_PATHS` (comma-separated, default `"/health/,/api/v1/health-light/"`) — paths excluded from rate limiting

The DRF rate format (`"2/min"`, `"10/hour"`, etc.) is well-understood and maps directly to `DEFAULT_THROTTLE_RATES`. Using `"2/min"` as default gives ~1 request per 30 seconds with a small burst tolerance.

### 4. Exclude health endpoints

**Decision**: Health check endpoints (`/health/`, `/api/v1/health-light/`) are excluded from rate limiting so the SPA health indicator continues polling every 30 seconds without being throttled.

**Implementation**: Override `AnonRateThrottle.get_cache_key()` to check against excluded paths, or use a custom throttle class that skips excluded paths.

### 5. Response format

**Decision**: When rate limited, return HTTP 429 with:
- JSON body: `{"detail": "Request was throttled. Expected available in <n> seconds."}`
- Headers: `Retry-After: <seconds>`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

DRF's default 429 response already includes the JSON body and `Retry-After` header. Custom headers are added via a small wrapper or middleware if needed.

## Risks / Trade-offs

- **LocMem cache is per-process**: If Gunicorn workers increase, rate limits apply per-worker, effectively multiplying the allowed rate. → Acceptable for demo. If multi-worker deployment is needed later, switch to Redis cache.
- **IP behind proxy**: If behind Cloudflare/traefik, `REMOTE_ADDR` may be the proxy IP. → Django's `SECURE_PROXY_SSL_HEADER` and `USE_X_FORWARDED_HOST` settings handle this. The existing deployment already uses Traefik which passes `X-Forwarded-For`.
- **Rate limit too aggressive for legitimate use**: 2 requests/minute may frustrate legitimate users wanting to process multiple plates. → Configurable via env var; users can increase or disable. The SPA uploads one image at a time, so 2/min is reasonable for the demo.
