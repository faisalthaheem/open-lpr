## 1. Docker Image

- [x] 1.1 Add `fonts-noto` and `fonts-noto-cjk` to the `apt-get install` line in the `Dockerfile`.

## 2. Font Configuration

- [x] 2.1 Update `TTF_FONT_PATHS` in `bbox_visualizer.py` to prioritize Noto Sans Regular (`/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf`) at the top, followed by Noto Sans CJK paths, then the existing Latin-only fonts.

## 3. Documentation

- [x] 3.1 Update `AGENTS.md` to note that `fonts-noto` and `fonts-noto-cjk` are required in the Docker image for Unicode text rendering.
