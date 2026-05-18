## Context

The home page (`upload.html`) shows recent uploads as Bootstrap cards with `card-img-top` thumbnail images. The fullscreen preview overlay and `openFullscreenPreview()` function are already defined in `base.html` and shared across the detail and list pages. The image list page (`image_list.html`) already uses the same pattern — `.result-card .card-img-top` selector with click handlers.

## Goals / Non-Goals

**Goals:**
- Enable fullscreen image preview on home page thumbnails
- Reuse the existing `openFullscreenPreview()` from `base.html`
- Match the UX pattern already established on the image list page

**Non-Goals:**
- Adding new views, URLs, or templates
- Changing the card layout or thumbnail sizing
- Modifying the upload form or processing pipeline

## Decisions

### Decision 1: Reuse the image list page's click handler pattern

**Choice:** Copy the same JS pattern from `image_list.html` that targets `.result-card .card-img-top`.

**Rationale:** Consistency — the image list page already does exactly this. The selector matches the same card structure used on the home page.

### Decision 2: Add hover visual cue

**Choice:** Add `cursor: pointer` and title "Click to preview" via JavaScript, matching the detail page pattern.

**Rationale:** Users need a visual affordance that images are clickable. This is the same approach used everywhere else.

## Risks / Trade-offs

- **[Minimal risk]** This is a small, purely additive JS change with no backend impact.
