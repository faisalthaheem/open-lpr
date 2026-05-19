## Context

A comprehensive UI/UX audit identified 5 critical bugs and ~15 high/medium/low issues across all templates. The app is a single-page Django app with templates extending `base.html`. Key files: `base.html` (shared overlay, CSS, JS), `upload.html` (home/upload), `image_detail.html` (merged detail/results), `image_list.html` (history with pagination), `forms.py` (search form), and a missing `error.html`.

Current state:
- `error.html` does not exist — crashes on error paths
- `handleAjaxError` uses wrong DOM selector — errors silently fail
- Desktop pagination uses 10 hardcoded `elif` blocks — no backward windowing
- Mobile pagination renders all pages — unusable with many records
- `ImageSearchForm.__init__` overwrites `<select>` widget class with `form-control`
- JS hardcodes 250KB max file size instead of reading from Django settings
- Dark mode `code` CSS duplicated across 3 templates
- `LPRSettingsForm` is dead code
- `pprint` filter renders Python repr, not JSON
- Fullscreen preview lacks keyboard accessibility (Enter/Space)
- Image detail has duplicate filename and redundant chevron JS

## Goals / Non-Goals

**Goals:**
- Fix all 5 critical bugs
- Fix high-impact UX issues (hardcoded file size, empty state, form widget)
- Clean up duplicated CSS, dead code, and redundant JS
- Improve accessibility (keyboard nav, alt text, ARIA labels)
- Establish patterns for reusable CSS classes

**Non-Goals:**
- Adding delete functionality (out of scope per user request)
- Redesigning the layout or changing the visual design language
- Adding new features (loading skeletons, meta tags, elapsed timer)
- Moving theme toggle into navbar

## Decisions

### 1. Pagination: Template tag vs inline template logic
**Decision**: Implement windowed pagination as a reusable Jinja-style template inclusion tag (`{% include "lpr_app/_pagination.html" %}`).

**Rationale**: Desktop pagination has 50+ lines of broken `elif` chains. A shared partial keeps both desktop and mobile consistent and testable. The inclusion tag receives `page_obj` and renders a bounded window (2 pages before/after current, first/last always shown, ellipsis for gaps).

**Alternatives considered**:
- Custom template tag (Python function) — more testable but overkill for pure display logic
- JavaScript pagination — adds client complexity, breaks SEO/ accessibility

### 2. JSON rendering for API response: Template filter
**Decision**: Create a `json_format` template filter in `lpr_app/templatetags/` that uses `json.dumps(data, indent=2)` with `force_escape`.

**Rationale**: `pprint` outputs Python repr (`True`, `None`, single quotes). A custom filter gives proper JSON. `api_response` is stored as a JSONField, so `json.dumps` works directly.

**Alternatives considered**:
- `|json_script` — only outputs `<script>` tags, not displayable
- View-side serialization — couples display to view logic

### 3. Error page: Simple template extending base
**Decision**: Create `error.html` extending `base.html` with a card showing error title, message, and a back link.

**Rationale**: Minimal, consistent with existing page patterns. The view already passes `error_title` and `error_message` context variables.

### 4. Centralized CSS classes in base.html
**Decision**: Add `.card-img-fixed` class to `base.html` shared styles, remove inline `style="height: 200px; object-fit: cover;"` from all templates. Remove duplicate dark mode `code`/`pre code` blocks from child templates.

**Rationale**: Single source of truth for shared styles. Dark mode code styles already exist in `base.html` — the copies in `upload.html` and `image_detail.html` are pure duplication.

### 5. Keyboard accessibility for fullscreen preview
**Decision**: Add `tabindex="0"`, `role="button"`, `aria-label`, and `keydown` handler (Enter/Space) to previewable images. Update `openFullscreenPreview()` to set dynamic `alt` text.

**Rationale**: Minimal change to existing overlay. Focus trap would require significant refactoring — deferred.

## Risks / Trade-offs

- **Pagination partial may not cover edge cases** → Test with 0, 1, 2, 5, and 100+ pages
- **`json_format` filter on non-JSONField** → Filter should handle `None` and non-dict values gracefully
- **Removing chevron JS may reveal CSS bug** → Verify CSS rotation works for all accordion states before removing JS
- **`UPLOAD_FILE_MAX_SIZE` as template variable** → Already used in template for display text; using raw int for JS is safe since it's a bytes integer
