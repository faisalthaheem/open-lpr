## Context

The results page (`results.html`) has an image zoom feature using Bootstrap's `modal-lg` (~800px max). The image detail page (`image_detail.html`) and image list page (`image_list.html`) have no zoom at all. All three pages display images that users need to inspect closely for license plate details.

## Goals / Non-Goals

**Goals:**
- Maximize image display area when previewing — use the full browser viewport
- Minimal UI chrome (close button only, no header/footer wasting vertical pixels)
- Image scales to fill available space while preserving aspect ratio (`object-fit: contain`)
- Consistent preview behavior across all pages (results, detail, list)
- Works in both light and dark mode

**Non-Goals:**
- Pan/zoom controls within the preview (pinch-to-zoom, scroll zoom, drag)
- Image comparison side-by-side in fullscreen
- Thumbnail strip or carousel navigation

## Decisions

### 1. Shared fullscreen preview in `base.html`

Add a single fullscreen modal HTML snippet, CSS, and JS to `base.html` so all pages inherit it. Per-page JS only needs to attach click handlers that call `openFullscreenPreview(src)`.

**Why shared over per-page:** Three pages need this behavior. Duplicating modal HTML/JS in each template violates DRY and makes maintenance harder.

### 2. Pure CSS fullscreen overlay (not Bootstrap modal)

Use a fixed-position `<div>` overlay with `z-index: 9999` instead of Bootstrap's modal component. Bootstrap modals add padding, backdrop animations, and dialog sizing that fight against fullscreen behavior.

**Why not Bootstrap modal:** `modal-lg` is capped at 800px. `modal-fullscreen` exists in Bootstrap 5 but still includes header/footer padding and doesn't center the image optimally. A custom overlay gives full control with less code.

### 3. Click to open, Escape/click to close

- Click any `<img>` with class `img-fluid` → opens fullscreen preview
- Click overlay background or press Escape → closes preview
- Close button in top-right corner as visual affordance

### 4. Image sizing: `object-fit: contain` with `max-width: 100vw; max-height: 100vh`

The image fills the viewport while maintaining aspect ratio. No letterboxing CSS needed — the dark overlay background serves as letterbox fill.

## Risks / Trade-offs

- **[Touch devices]** No pinch-to-zoom — users on mobile must use browser-level zoom. → Acceptable for MVP; can add later if requested.
- **[Multiple images on list page]** All card images become clickable. → Intentional; improves UX for browsing history.
