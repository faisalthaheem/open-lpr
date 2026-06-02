## Context

The backend enforces per-IP rate limiting on `POST /api/v1/ocr/` (default 2 req/min). When the limit is exceeded, the backend returns HTTP 429 with a JSON body `{ "detail": "Request was throttled. Expected available in X seconds." }` and headers `Retry-After` and `X-RateLimit-Reset`.

The SPA currently treats 429 like any other error — `api.ts` throws a generic `Error` with the `detail` string, and `page.tsx` shows it as a static red banner. There is no toast library installed.

## Goals / Non-Goals

**Goals:**
- Show a clear, user-friendly message when the upload is rate-limited (429)
- Display the retry wait time so the user knows when to try again
- Reuse the existing error banner pattern (no new dependencies)
- Make the 429 error visually distinct from other errors

**Non-Goals:**
- Adding a toast/notification library
- Countdown timers or auto-retry
- Rate limiting feedback for non-upload endpoints
- Changing the backend rate limit logic or response format

## Decisions

### 1. Use existing red banner with rate-limit-specific styling
No toast library needed. The existing error banner in `page.tsx` is sufficient — just needs a distinct message for 429. A subtle visual distinction (e.g., amber/yellow instead of red) communicates "wait" vs "error" without introducing new components.

**Alternatives considered:**
- `react-hot-toast` or `sonner`: Overkill for a single use case; adds a dependency
- Inline message in `UploadForm.tsx`: Would duplicate error display logic

### 2. Parse 429 response in `api.ts` and throw a typed error
Add a `RateLimitError` class that carries `retryAfter` seconds. The `UploadForm` catches this specifically and passes a structured message to `onError`. This keeps the API client as the single point for error classification.

### 3. Keep the backend response unchanged
The existing `detail` field is already human-readable. The `Retry-After` header already exists. No backend changes needed — the SPA just needs to read them.

## Risks / Trade-offs

- **Banner persists until next action** → Acceptable. The user will see it until they retry or navigate away. Could add auto-dismiss later if needed.
- **Clock skew between client and server** → We use the `Retry-After` header value (seconds) directly, so this is not an issue.
- **No countdown timer** → Shows static "try again in X seconds" message. Countdown would be nice but is out of scope for this change.
