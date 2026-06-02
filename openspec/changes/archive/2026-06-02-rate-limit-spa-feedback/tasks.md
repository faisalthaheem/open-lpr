## 1. API Client — Rate Limit Error Classification

- [x] 1.1 Add `RateLimitError` class to `single-page-ui/src/lib/api.ts` with a `retryAfter` property (number of seconds)
- [x] 1.2 Update `uploadImage()` to detect HTTP 429, read `Retry-After` header (fallback to `X-RateLimit-Reset`, default 60), and throw `RateLimitError` instead of generic `Error`
- [x] 1.3 Update `uploadImage()` to read the `detail` field from the 429 JSON body for the error message

## 2. Upload Form — Rate Limit Handling

- [x] 2.1 Update `UploadForm.tsx` to catch `RateLimitError` specifically in the upload handler
- [x] 2.2 Pass a structured rate limit message to `onError` (e.g., `"Too many requests. Please wait {retryAfter} seconds and try again."`) when `RateLimitError` is caught
- [x] 2.3 Ensure the form returns to `selected` state (not stuck in `uploading`) after a rate limit error so the user can retry

## 3. Parent Page — Distinct Rate Limit Display

- [x] 3.1 Update `page.tsx` to detect rate limit errors and display them in an amber/yellow banner instead of the red error banner
- [x] 3.2 Clear the rate limit banner when the user starts a new upload attempt
