## ADDED Requirements

### Requirement: SPA displays user-friendly feedback on rate-limited uploads
The SPA SHALL detect HTTP 429 responses from the upload endpoint and display a distinct, user-friendly message informing the user that their request was rate-limited and when they can retry.

#### Scenario: User hits rate limit on upload
- **WHEN** a user submits an image upload and the backend returns HTTP 429
- **THEN** the SPA displays a message indicating the upload was rate-limited, including the number of seconds until they can retry, styled distinctly from error messages (e.g., amber/yellow instead of red)

#### Scenario: User hits rate limit with Retry-After header
- **WHEN** a user submits an image upload and the backend returns HTTP 429 with a `Retry-After` header value of `30`
- **THEN** the SPA displays a message like "Too many requests. Please wait 30 seconds and try again."

### Requirement: API client classifies rate limit errors distinctly
The SPA API client (`api.ts`) SHALL classify HTTP 429 responses as a distinct error type carrying the retry-after duration, separate from other API errors.

#### Scenario: uploadImage receives 429
- **WHEN** `uploadImage()` receives an HTTP 429 response
- **THEN** it throws a `RateLimitError` with a `retryAfter` property containing the number of seconds from the `Retry-After` response header (or the `X-RateLimit-Reset` header as fallback, or 60 as default)

#### Scenario: uploadImage receives non-429 error
- **WHEN** `uploadImage()` receives an HTTP 500 or other non-429 error
- **THEN** it throws a generic `Error` as before (no `RateLimitError`)

### Requirement: Rate limit feedback does not block further uploads
After a rate limit message is displayed, the upload form SHALL remain usable so the user can retry after the indicated wait time.

#### Scenario: Upload form remains usable after rate limit
- **WHEN** a user receives a rate limit message
- **THEN** the upload form returns to the `idle` or `selected` state and the user can select a new file or retry
