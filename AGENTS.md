# AGENTS.md

## Project Overview

Django 4.2 web app for license plate recognition using Qwen3-VL vision-language model via an OpenAI-compatible API. Python 3.8+, SQLite by default.

## Commands

```bash
python manage.py runserver              # Dev server (port 8000)
python manage.py test                   # Django test runner (no formal test suite exists yet)
python manage.py makemigrations lpr_app # Create migrations after model changes
python manage.py migrate                # Apply migrations
python manage.py collectstatic --noinput # Collect static files (required before Docker deploy)
python test_api.py /path/to/image.jpg   # Manual API integration test (requires running server)
```

There is no linter, formatter, or typecheck configured.

## Architecture

- **`lpr_project/`** — Django project config (`settings.py`, `urls.py`, `wsgi.py`)
- **`lpr_app/`** — The sole Django app containing all business logic
  - `models.py` — `UploadedImage` and `ProcessingLog` models
  - `views.py` — Legacy monolithic views (still referenced by `urls.py` import)
  - `views/` — Refactored view subpackage: `web_views.py`, `api_views.py`, `file_views.py`
  - `services/` — Business logic layer
    - `qwen_client.py` — OpenAI-compatible client for Qwen3-VL, prompt templates, coordinate conversion
    - `image_processor.py` / `image_processing_service.py` — Image handling
    - `bbox_visualizer.py` — Bounding box drawing
    - `api_service.py`, `file_service.py` — Service layer
  - `utils/` — Helpers: `validators.py`, `response_helpers.py`, `metrics_helpers.py`
  - `management/commands/` — `setup_project`, `inspect_image`
- **`canary/`** — Separate canary monitoring service (its own Dockerfile)
- **`blackbox/`** — Blackbox exporter config for Prometheus probing

## Key Patterns & Gotchas

- Settings use `python-decouple` (`config()` calls in `settings.py`), not raw `os.environ`. Env vars are loaded from `.env` or `.env.llamacpp`.
- Two env file modes: `.env` for external API, `.env.llamacpp` for bundled LlamaCpp inference. Docker Compose reads `.env.llamacpp` by default.
- The AI client (`QwenVLClient`) wraps the `openai` Python SDK. It calls any OpenAI-compatible endpoint (LlamaCpp, vLLM, remote API).
- Detection uses a two-phase pipeline: Phase 1 detects plate bounding boxes, Phase 2 runs OCR on cropped regions. Prompts are in `qwen_client.py`.
- Bounding box coordinates arrive in Qwen2VL 0-1000 normalized range and must be converted via `convert_from_qwen2vl_format()`.
- `UploadedImage` media is organized into `uploads/YYYY/MM/DD/` and `processed/YYYY/MM/DD/` subdirectories.
- `views.py` (monolithic) and `views/` (subpackage) both exist. `urls.py` imports from the subpackage.
- `upload_to` path helpers in `models.py` generate date-partitioned upload paths.

## Docker

Profile-based Docker Compose (deprecated individual compose files must not be used):

```bash
docker compose --profile core --profile cpu up -d          # CPU inference
docker compose --profile core --profile nvidia-cuda up -d  # NVIDIA GPU
docker compose --profile core --profile amd-vulkan up -d   # AMD Vulkan GPU
docker compose --profile core up -d                        # External API only
```

- Images published to `ghcr.io/faisalthaheem/open-lpr`
- CI: `.github/workflows/docker-publish.yml` builds multi-arch (amd64/arm64) on push to main and version tags
- Container runs as `django` user via `gosu` (see `docker-entrypoint.sh`)
- `docker-entrypoint.sh` runs migrate + collectstatic + optional createsuperuser on every start

## Environment Variables

Key variables (see `.env.example` and `.env.llamacpp.example` for full list):

- `QWEN_API_KEY`, `QWEN_BASE_URL`, `QWEN_MODEL` — AI model connection
- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` — Django core
- `DATABASE_PATH` — SQLite path (default: project root `db.sqlite3`)
- `MEDIA_PATH` — Media storage (default: `./media`, Docker: `./container-media`)
- `UPLOAD_FILE_MAX_SIZE` — Default 250KB in settings.py (10MB in Docker compose)
