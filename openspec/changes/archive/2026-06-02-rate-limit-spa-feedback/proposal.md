## Why

When the rate limit is hit on image submission, the SPA shows a generic error or silently fails. Users have no idea why their upload was rejected or when they can try again. This creates a poor experience — especially for the demo system where `2/min` rate limiting is active.

## What Changes

- The SPA will detect HTTP 429 responses from the backend and display a user-friendly toast/notification explaining the rate limit and when they can retry
- The backend already returns `Retry-After` and `X-RateLimit-Reset` headers on 429 responses — the SPA will read these to show a countdown or wait time
- A reusable error handling pattern will be added to the SPA API client to surface rate limit errors distinctly from other failures

## Capabilities

### New Capabilities
- `rate-limit-spa-feedback`: Frontend handling of 429 rate limit responses with user-facing feedback

### Modified Capabilities
- `api-rate-limiting`: The 429 response body will include a user-friendly message field suitable for direct display in the SPA

## Impact

- **SPA frontend** (`single-page-ui/src/lib/api.ts`, upload component): New error handling for 429, toast/notification UI
- **Backend** (`lpr_app/middleware/rate_limit.py`): Minor — ensure the 429 JSON body includes a display-friendly message
- **No API breaking changes** — only adding/reading existing response fields
