## Context

The SPA frontend uses a single `ImageCard` component on both the homepage (9 recent uploads) and the all-images page (paginated grid). Each card currently shows: a thumbnail, the original filename, a raw status string badge, and an absolute `toLocaleString()` timestamp. The backend's image list endpoint (`_serialize_image_summary`) returns only core fields — it does not include plate/OCR counts despite the model having `get_plate_count()`, `get_total_ocr_count()`, and `get_first_ocr_text()` methods.

## Goals / Non-Goals

**Goals:**
- Give users at-a-glance processing results on image cards (plate count, OCR text)
- Replace unhelpful filename with a clear "View Details" navigation link
- Show relative timestamps ("5 minutes ago") with PST timezone indicator
- Extend the list API with plate/OCR summary fields (non-breaking)

**Non-Goals:**
- Replacing the existing detail page or its full timestamp display
- Adding external date libraries (dayjs, date-fns, etc.) — use a lightweight inline utility
- Changing the card thumbnail/preview behavior
- Modifying non-card status displays (e.g., the detail page status badge)

## Decisions

### 1. Backend fields added to list serializer
Add `plate_count` (int), `ocr_count` (int), and `first_ocr_text` (string or null) to `_serialize_image_summary()`. These leverage existing model methods. This avoids extra N+1 queries since the model methods read from the stored `detections` JSON field on the same row.

**Alternative considered**: Adding full `detections` to the list response — rejected as unnecessarily large for a list view.

### 2. Relative time formatting — inline utility
Implement a pure function `formatRelativeTime(isoString: string): string` in a new `single-page-ui/src/lib/relative-time.ts` file. No external dependencies. It calculates the difference from `Date.now()` and returns strings like "just now", "5 minutes ago", "2 hours ago", "3 days ago", or falls back to "on <date>" for dates older than 30 days. The "PST" suffix is appended outside this function in the component.

**Alternative considered**: Installing `date-fns` or `dayjs` — rejected to avoid dependency bloat for a single utility.

### 3. Card layout restructure
Replace the current card footer (filename + status + timestamp) with:
- **Row 1**: Result summary (replaces status badge for completed images)
  - Completed with results: "1 plate, 1 OCR" or actual OCR text if single plate+OCR
  - Completed with 0 results: "0 plates detected"
  - Pending/processing/failed: keep existing colored status badge
- **Row 2**: "View Details" link (replaces filename) + relative timestamp with "PST"

The entire card bottom area remains a `<Link>` to the detail page.

### 4. Timezone handling
All backend timestamps are UTC (Django default with `USE_TZ=True`). The frontend converts to PST for display using `toLocaleString('en-US', { timeZone: 'America/Los_Angeles' })` for the detail page, but for cards we use relative time which is timezone-agnostic. The "PST" label is a static suffix for user awareness.

## Risks / Trade-offs

- **N+1 query risk**: `get_plate_count()` and `get_total_ocr_count()` read from a JSON field on each row. Since the data is on the same model instance (no joins), this is a simple attribute access, not a query. Low risk.
- **PST vs PDT**: The static "PST" label is technically inaccurate during Pacific Daylight Time. Acceptable trade-off for simplicity; could be enhanced later with dynamic PDT/PST detection.
- **No i18n for relative time**: The relative time strings are hardcoded English. Acceptable for current scope.
