## 1. Add fullscreen preview overlay to base.html

- [x] 1.1 Add fullscreen overlay HTML snippet (a fixed-position `<div>` with `<img>` and close button) to `base.html` before the closing `</body>` tag
- [x] 1.2 Add fullscreen preview CSS to `base.html` (overlay covers viewport, image uses `object-fit: contain` + `max-width: 100vw` + `max-height: 100vh`, close button positioned top-right, dark mode compatible)
- [x] 1.3 Add `openFullscreenPreview(src)` and `closeFullscreenPreview()` JavaScript functions to `base.html`, including Escape key listener and click-on-background-to-close

## 2. Remove existing zoom modal from results.html

- [x] 2.1 Remove the image zoom JavaScript and inline modal creation code from `results.html`
- [x] 2.2 Remove the `.modal` CSS overrides from `results.html`
- [x] 2.3 Add click-to-preview behavior using `openFullscreenPreview()` for images in the image comparison section

## 3. Add click-to-preview on image detail page

- [x] 3.1 Add click handlers to original and processed images in `image_detail.html` that call `openFullscreenPreview(src)`

## 4. Add click-to-preview on image list page

- [x] 4.1 Add click handlers to card images in `image_list.html` that call `openFullscreenPreview(src)`

## 5. Verify dark mode compatibility

- [x] 5.1 Confirm the overlay background and close button are visible in both light and dark mode (use theme CSS variables)
