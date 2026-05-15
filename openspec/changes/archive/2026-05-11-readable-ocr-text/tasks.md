## 1. Font Size Computation

- [x] 1.1 Add a `_compute_font_size(self, image_height: int) -> int` method to `BoundingBoxVisualizer` that returns `image_height * 0.02`, clamped to a minimum of 16 and maximum of 64.
- [x] 1.2 In `__init__`, call `_compute_font_size` with the loaded image's height and store the result as `self.font_size`.
- [x] 2.1 Replace the current font-loading block in `__init__` with a loop that tries multiple common TrueType font paths (`/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`, `/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf`, `arial.ttf`, etc.) at `self.font_size`.
- [x] 2.2 If no TrueType font is found, fall back to `ImageFont.load_default(size=self.font_size)` (Pillow >= 10.0) or `ImageFont.load_default()` for older versions, and log a warning.

## 3. Label Rendering

- [x] 3.1 Verify that `draw_bounding_box` already uses `draw.textbbox` to measure the label text dynamically — confirm the background rectangle and text position adapt to the new font size without hard-coded offsets.
- [x] 3.2 Ensure the label padding (currently 4px) is retained for all font sizes.

## 4. Cleanup

- [x] 4.1 Remove the unused `FONT_SIZES` class constant since font sizing is now dynamic.
- [x] 4.2 Remove the `font` parameter fallback logic that references `self.font or (len(label) * 8, 16)` — the dynamic `textbbox` call handles measurement.
