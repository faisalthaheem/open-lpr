## 1. Backend API Changes

- [x] 1.1 Add `plate_count`, `ocr_count`, and `first_ocr_text` fields to `_serialize_image_summary()` in `lpr_app/views/api_views.py`, using existing model methods `get_plate_count()`, `get_total_ocr_count()`, and `get_first_ocr_text()`
- [x] 1.2 Update `ImageSummary` TypeScript interface in `single-page-ui/src/lib/api.ts` to include `plate_count: number`, `ocr_count: number`, and `first_ocr_text: string | null`
- [x] 1.3 Update mock data in `single-page-ui/src/lib/mock-data.ts` to include the new fields

## 2. Relative Time Utility

- [x] 2.1 Create `single-page-ui/src/lib/relative-time.ts` with a `formatRelativeTime(isoString: string): string` function handling: "just now" (<60s), "X minute(s) ago", "X hour(s) ago", "X day(s) ago", and "on <date>" fallback (30+ days)

## 3. ImageCard Component Update

- [x] 3.1 Replace the filename display with a "View Details" link navigating to `/image/<id>`
- [x] 3.2 Replace the status badge with result summary for completed images: show OCR text if single plate+OCR, show "<n> plates, <m> OCR" for multiple, show "0 plates detected" for zero results; keep color-coded status badge for pending/processing/failed
- [x] 3.3 Replace absolute timestamp with relative time + " · PST" suffix using the `formatRelativeTime` utility

## 4. Storybook Updates

- [x] 4.1 Update `ImageCard.stories.tsx` to reflect new card layout (result summary, View Details link, relative time)
