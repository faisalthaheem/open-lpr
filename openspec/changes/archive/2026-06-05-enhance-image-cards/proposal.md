## Why

Image cards on the homepage and all-images page show only a raw status string ("completed", "failed", etc.), the original filename, and an absolute timestamp. This is unhelpful: "completed" doesn't convey how many plates were detected or OCR texts extracted, the filename is noise, and the full date-time is hard to scan. Users need at-a-glance insight into processing results and quick navigation to details.

## What Changes

- Replace the generic status badge with a result summary showing plate count and OCR text count (e.g. "1 plate, 1 OCR" or "0 plates" for completed images; keep error status as-is for failed/pending images).
- When there is exactly one plate and one OCR result, display the actual OCR text inline instead of just the count.
- Replace the filename display with a "View Details" link that navigates to the image detail page.
- Replace the absolute timestamp with a relative time string (e.g. "5 minutes ago", "2 hours ago", "3 days ago") and append "PST" timezone indicator. The full absolute timestamp moves to the detail page only.
- Extend the backend image list serializer (`_serialize_image_summary`) to include `plate_count`, `ocr_count`, and `first_ocr_text` so cards have the data without fetching detail.
- Update the `ImageSummary` TypeScript interface to include the new fields.

## Capabilities

### New Capabilities
- `relative-time-display`: Utility for formatting timestamps as relative time strings (e.g. "5 minutes ago") with PST timezone label
- `card-result-summary`: Card-level display of plate/OCR counts and first OCR text instead of raw status

### Modified Capabilities
- `api-image-list`: Add `plate_count`, `ocr_count`, and `first_ocr_text` fields to the image list API response

## Impact

- **Backend**: `lpr_app/views/api_views.py` — `_serialize_image_summary()` needs three new fields
- **Frontend**: `single-page-ui/src/components/ImageCard.tsx` — major rework of card layout
- **Frontend**: `single-page-ui/src/lib/api.ts` — `ImageSummary` interface update
- **Frontend**: New utility function for relative time formatting (no external library; lightweight inline implementation)
- **API**: Non-breaking addition of optional fields to the list response
- **Storybook**: `ImageCard.stories.tsx` and `mock-data.ts` need updates for new fields
