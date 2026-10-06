# AGENTS.md

## Project Overview

Django 5.2 LTS web app for license plate recognition using Qwen3-VL vision-language model via an OpenAI-compatible API. Python 3.10+, SQLite by default.

## Commands

```bash
python manage.py runserver              # Dev server (port 8000)
python manage.py test                   # Django test runner (212 tests in lpr_app/tests/)
python manage.py makemigrations lpr_app # Create migrations after model changes
python manage.py migrate                # Apply migrations
python manage.py collectstatic --noinput # Collect static files (required before Docker deploy)
python scripts/test_api.py /path/to/image.jpg   # Manual API integration test (requires running server)
```

### Lint, format, and coverage

```bash
pip install -r requirements-dev.txt    # ruff + coverage (dev-only, not in the production image)
ruff check .                           # Lint
ruff format .                          # Format
ruff format --check .                 # Verify formatting in CI
coverage run --source='lpr_app' manage.py test
coverage report                        # CI gate is --fail-under=70; current baseline is ~72%
```

- Config lives in `pyproject.toml` (`line-length = 120`, rules `E`, `F`, `I`, `B`, `UP`).
- `lpr_app/migrations/` is excluded from lint (generated code).
- There is no typechecker configured.
- CI (`.github/workflows/test.yml`) runs lint, format check, and tests with a coverage gate on every push and pull request.

### Manual diagnostic scripts

`scripts/` holds manual integration and diagnostic harnesses (`test_api.py`, `test_metrics.py`,
`test_setup.py`, `test-llamacpp-integration.py`). They are **not** unit tests and are deliberately
kept out of Django's test discovery — do not name a new unit test in a way that lands here.

## Architecture

- **`lpr_project/`** — Django project config (`settings.py`, `urls.py`, `wsgi.py`)
- **`lpr_app/`** — The sole Django app containing all business logic
  - `models.py` — `UploadedImage` and `ProcessingLog` models
  - `views/` — API-only view subpackage: `api_views.py`, `file_views.py`
  - `services/` — Business logic layer
    - `qwen_client.py` — OpenAI-compatible client for Qwen3-VL, prompt templates, coordinate conversion
    - `image_processor.py` / `image_processing_service.py` — Image handling
    - `bbox_visualizer.py` — Bounding box drawing
    - `api_service.py`, `file_service.py` — Service layer
  - `pipeline/` — Local ONNX plate pipeline: a configuration-declared graph of swappable stages
    - `graph.py` — Graph construction, validation, dependency-ordered and concurrent execution
    - `local_backend.py` — The `local` backend end to end: detect, rectify, recognise, validate, and emit the same detections collection the LLM backend emits
    - `stages/base.py` — `Stage` contract (declared inputs/outputs, lazy model loading)
    - `stages/detect.py` — YOLOX plate detector: letterboxing, decoding, NMS, coordinate mapping
    - `stages/rectify.py` — Classical perspective correction; accepts an axis-aligned box when no corner geometry exists
    - `stages/ocr.py` — PP-OCR CTC recogniser: preprocessing, greedy decode, charset profiles, row splitting, batched inference
    - `runtime/onnx.py` — ONNX Runtime session construction, provider resolution, signature validation
  - `ml/` — **Training only, never imported by the web app.** Datasets, detector training, ONNX export, benchmark, backend comparison. See `ml/requirements-train.txt`.
  - `utils/` — Helpers: `validators.py`, `response_helpers.py`, `metrics_helpers.py`
  - `management/commands/` — `setup_project`, `inspect_image`
- **`single-page-ui/`** — Next.js 16 SPA frontend (React 19, Tailwind CSS 4, Storybook 10)
- **`canary/`** — Separate canary monitoring service (its own Dockerfile)
- **`blackbox/`** — Blackbox exporter config for Prometheus probing

## Key Patterns & Gotchas

- Settings use `python-decouple` (`config()` calls in `settings.py`), not raw `os.environ`. Env vars are loaded from `.env` or `.env.llamacpp`.
- Two env file modes: `.env` for external API, `.env.llamacpp` for bundled LlamaCpp inference. Docker Compose reads `.env.llamacpp` by default.
- The AI client (`QwenVLClient`) wraps the `openai` Python SDK. It calls any OpenAI-compatible endpoint (LlamaCpp, vLLM, remote API).
- Detection uses a two-phase pipeline: Phase 1 detects plate bounding boxes, Phase 2 runs OCR on cropped regions. Prompts are in `qwen_client.py`.
- **Two backends, one output shape.** `PIPELINE_BACKEND` selects `local` (default) or `llm`. Both return the identical detections collection — `[{"plate": {"confidence", "coordinates"}, "ocr": [{"text", "confidence", "coordinates"}]}]` — so no caller, API, visualizer, or metric branches on which ran. `image_processing_service.py` holds the two paths in separate `_run_llm_pipeline` / `_run_local_pipeline` methods and branches once. **Switching back is configuration-only**: set `PIPELINE_BACKEND=llm` and redeploy. No migration, no data rewrite.
- **The local backend is the default, and its text accuracy is only partially known.** It is faster (60ms mean vs 3611ms) and detects more reliably on the corpus (recall 1.000 vs 0.375). On a 20-plate transcribed pilot it scores CER 0.367 / exact-match 0.35 — it reads nearly every plate it detects and gets roughly a third exactly right. That pilot is not a decision: it is too small, not randomly ordered, and the LLM arm was not scored on the same plates. Do not treat higher coverage as higher accuracy. See `openspec/changes/measure-local-backend-accuracy/COMPARISON.md`.
- **Stacked-plate row splitting is off by default, deliberately.** Aspect ratio cannot distinguish a two-line plate from a single-line plate carrying a caption — both span ratios 1.4–2.4, both have an ink gap, both split unevenly — and the split read scores *higher* confidence while being wrong. `PIPELINE_OCR_SPLIT_STACKED=true` enables it for regions known to be uniformly stacked. This is an open limitation, not a bug.
- **Latency is instrumented, not assumed.** Per-stage durations export as `lpr_pipeline_stage_duration_seconds{stage,outcome}` and end-to-end as `lpr_pipeline_duration_seconds{outcome}`. The pre-existing `lpr_processing_duration_seconds` is still recorded on both backends so they stay comparable on one series. `PIPELINE_LATENCY_BUDGET_SECONDS` (default 0.5) is the project's sub-500ms target; `PIPELINE_STAGE_BUDGETS` takes `stage=seconds` pairs.
- **ONNX Runtime install variants are an install-time choice, not a code branch.** No module branches on the execution provider; a stage is assigned `cpu`, `cuda`, or `rocm` by configuration and an unavailable provider falls back to CPU with a logged warning. The wheels:
  - CPU (default, and the supported deployment target): `pip install onnxruntime`
  - CUDA: `pip install onnxruntime-gpu`
  - ROCm (AMD): `pip install onnxruntime-rocm`, which needs a matching ROCm runtime
- **ROCm is never a prerequisite for contributors.** CPU inference is the supported path; ROCm or CUDA is for local experimentation only. `onnxruntime` is the only new runtime dependency — the web app must never import `torch` (see `ml/requirements-train.txt`).
- Bounding box coordinates arrive in Qwen2VL 0-1000 normalized range and must be converted via `convert_from_qwen2vl_format()`.
- `UploadedImage` media is organized into `uploads/YYYY/MM/DD/` and `processed/YYYY/MM/DD/` subdirectories.
- Django serves API-only (no templates, no web UI). The frontend is a separate Next.js SPA in `single-page-ui/`.
- `upload_to` path helpers in `models.py` generate date-partitioned upload paths.
- **Health and availability report the active backend, not "the API".** `/health/` returns `backend` on both paths and branches on it: under `local` it drops `api_healthy` entirely and reports `artifacts_healthy` instead, under `llm` it probes the VLM endpoint as before. The reason is a shipped incident — the local backend returned HTTP 500 on every upload while `/health/` reported healthy, because its only measurement was an external API that the local path never calls. Do not "fix" the missing `api_healthy` by filling it with artifact state; a field named `api_healthy` meaning "artifacts present" is precisely the misreading this design prevents.
- **`/api/v1/availability/` is not applicable under `local`.** The series derives from `lpr_api_health_status`, which is only written on the VLM probe, so under `local` the endpoint returns `applicable: false` with a reason. Checked *before* the cache read on purpose: the cache outlives a backend switch, so a series captured under `llm` stays readable afterwards and would otherwise be served as though it described local inference. `applicable` exists to distinguish this from `data: []` ("queried, nothing recorded") and from a 503 ("Prometheus unreachable"), since all three are otherwise easy to conflate.
- **CI must actually run the real-model tests.** `RealDetectorTest` and `RealModelLocalBackendTest` are gated on the ONNX artifacts being present and otherwise skip silently. `.github/workflows/test.yml` fetches artifacts and then asserts those classes executed, reading `__unittest_skip__` off the class itself — `loadTestsFromName` returns a `TestSuite` that never carries the flag, so counting tests is not enough and the assertion would pass trivially. Synthetic fixtures cannot replace this: they agree with the decoder and pass.

## Local ONNX Pipeline

The default detection and OCR backend, selected by `PIPELINE_BACKEND`. It runs
in-process on CPU and is the only path that fits the sub-500ms budget. Setting
`PIPELINE_BACKEND=llm` selects the old API-backed path instead.

### Stage contract

Every stage declares `name`, `inputs` (field names it consumes), and `outputs` (field
names it produces). `PipelineGraph` routes data purely from those declarations and
validates them at construction time, so an unsatisfied binding fails before any model
loads rather than at inference time.

| Stage | Inputs | Outputs | Notes |
|---|---|---|---|
| `detect_plate` | `image` | `detections` | YOLOX-tiny; letterboxes, decodes, NMS, maps coordinates back and clamps them |
| `rectify_plate` | `plate` | `rectified` | Perspective correction. Classical — loads no model. Takes an axis-aligned box when no corner geometry exists, since the corpus has no corner annotations |
| `read_plate` | `plate_crop` | `ocr` | PP-OCR CTC. Batch-oriented: `read_plates()` takes a list and returns one result per plate |

Three things in these stages were bugs found only by running the real artifacts, all
of the same class — an assumption about framework semantics rather than about what
the export emits:

- The YOLOX export **already exponentiates** width and height. Applying `exp()` again
  inflates every box until it clamps to the whole frame.
- The PP-OCR CTC head emits **already-normalised probabilities** (the graph contains
  the Softmax). Softmaxing again drove confidence to exactly 0.00 on every plate.
- The PP-OCR output is `[""] + dictionary + [" "]`, i.e. `len(dict) + 2` classes, with
  the trailing space class letting CTC emit a gap. Omitting it makes the highest index
  look out of range on every decode.

Synthetic fixtures written to match a decoder rather than the export will agree with
the decoder and pass. `test_pipeline_detection_real_model.py` exists because of this.

### Configuration

`PIPELINE_BACKEND` (`local` default, `llm` to switch back). Model artifacts are resolved
under `PIPELINE_MODEL_DIR` (default `model/plate/`, gitignored); `model/plate/manifest.json`
records filename, SHA-256, upstream identity, and license for each.

| Setting | Default | Notes |
|---|---|---|
| `PIPELINE_BACKEND` | `local` | `local` or `llm`. Artifacts under `PIPELINE_MODEL_DIR` are **required** when selected; a missing one raises rather than degrading to zero plates |
| `PIPELINE_MODEL_DIR` | `model/plate` | Artifacts are resolved relative to this |
| `PIPELINE_DETECTOR_MODEL` | `plate_yolox_tiny_640.onnx` | |
| `PIPELINE_DETECTOR_INPUT_SIZE` | `640,640` | Recall-critical, not a speed knob — see below |
| `PIPELINE_DETECTOR_CONF_THRESHOLD` | `0.3` | |
| `PIPELINE_DETECTOR_NMS_IOU` | `0.45` | |
| `PIPELINE_LAYOUT_THRESHOLD` | `2.0` | Aspect ratio separating stacked from single-line |
| `PIPELINE_OCR_MODEL` | `plate_ocr_ppocrv5_mobile.onnx` | |
| `PIPELINE_OCR_DICT` | `plate_ocr_dict.json` | |
| `PIPELINE_OCR_BATCH_SIZE` | `8` | Crops per inference |
| `PIPELINE_OCR_CHARSET_PROFILE` | `alphanumeric` | `alphanumeric` or `no_io` |
| `PIPELINE_OCR_SPLIT_STACKED` | `False` | Off by default; see above |
| `PIPELINE_RECTIFY_ENABLED` | `True` | When false, `OCR_CROP_PADDING_PX` applies instead |
| `PIPELINE_PROVIDER` | `cpu` | `cpu`, `cuda`, `rocm`; falls back to CPU with a warning |
| `PIPELINE_LATENCY_BUDGET_SECONDS` | `0.5` | The sub-500ms target |
| `PIPELINE_STAGE_BUDGETS` | empty | `stage=seconds` pairs, e.g. `detect_plate=0.4` |

**Detection resolution is a recall decision.** The corpus median plate height is 61px
with a 36px 10th percentile; at 640px input a 36px plate is still resolvable by a
stride-8 head, and at 416px it would not be. Measured recall at 640px is 1.000 on
plates under 40px. Do not lower it for speed without re-measuring that bucket.

### Training and evaluation

Training lives in `lpr_app/ml/` and uses its own venv with ROCm/CUDA torch. It is
**never imported by the web app**, which must not import `torch`.

```bash
pip install -r lpr_app/ml/requirements-train.txt
python -m lpr_app.ml.datasets.imanno_to_coco --corpus <corpus-root> --out <dataset-root>
python -m lpr_app.ml.benchmark --data <dataset-root> --model model/plate/plate_yolox_tiny_640.onnx
python -m lpr_app.ml.compare_backends --data <dataset-root> --limit 40
python -m lpr_app.ml.compare_backends --data <dataset-root> --limit 60 --dump-label-template <dir>
python -m lpr_app.ml.compare_backends --data <dataset-root> --limit 60 --labels <dir>/labels.json
```

- The benchmark exits non-zero when mean latency exceeds the budget, and reports recall
  bucketed by plate height, so a small-plate regression fails the check instead of
  being discovered in production.
- `compare_backends.py` measures both backends on the same images and records
  `COMPARISON.md`. Without labels it reports read coverage and confidence, which is
  not correctness. With `--labels <file>` it also scores CER and exact-match per
  confidence band, using `recognition_scoring.py` (Levenshtein over alphanumerics
  only — the `alphanumeric` profile never emits separators, so scoring raw strings
  would penalise it for its own charset).
- **Transcription labels are human-transcribed and gitignored, like the corpus.** No
  label set ships in the repo; the corpus has boxes only (its `imgareas.lbltxt` field
  holds the class name `plate` and nothing else). Produce one with
  `--dump-label-template <dir>`, which writes a per-plate crop plus a `labels.json`
  pre-filled with the local backend's own read. **Overwrite those values; do not
  confirm them.** A blank means "not transcribed" and is skipped rather than scored
  as a deletion — scoring it would charge the backend for a plate nobody could read.
- **A pilot measurement exists and is not yet a decision.** On 20 hand-transcribed
  plates: CER 0.367, exact-match 0.35. Confidence tracks correctness monotonically
  (CER 0.68 / 0.53 / 0.04 across the 0.0–0.5 / 0.5–0.8 / 0.8–1.0 bands), so
  `PIPELINE_OCR_MIN_CONFIDENCE` is a real lever — but 20 non-randomly-ordered plates
  are not enough to set it on, so it stays 0.0.
- **Per-layout accuracy is not reportable.** `layout_of()` classifies only aspect
  ratios outside 1.5–2.6 and records the rest as `unknown`, because geometry cannot
  tell a two-row plate from a one-row plate with a caption. On the pilot, 17 of 20
  plates are `unknown`. Do not re-introduce a single threshold: `EG·209` (one line,
  caption beneath, ratio 1.91) and `L802 WGK` (two rows, ratio 1.9) are
  indistinguishable, and a 2.0 cutoff labels both "stacked".
- **Ultralytics YOLO is AGPL-3.0** and cannot be used against this Apache-2.0 project.
  The detector is YOLOX (Apache-2.0). Do not "upgrade" the detector to a YOLO variant.
- The corpus is frame-extracted video and **leaks**: the published split shares 10
  images by perceptual hash, and a random split leaks far more through adjacent
  frames. The exporter builds a frame-grouped split with a deliberate gap (0 hash
  overlap, minimum frame distance 51). Metrics on the published split are inflated.

## Docker

Profile-based Docker Compose (deprecated individual compose files must not be used):

```bash
docker compose --profile core up -d                        # DEFAULT: local ONNX, no GPU, no LlamaCpp
docker compose --profile core --profile cpu up -d          # Rollback: LLM backend on CPU
docker compose --profile core --profile nvidia-cuda up -d  # Rollback: LLM backend on NVIDIA
docker compose --profile core --profile amd-vulkan up -d   # Rollback: LLM backend on AMD Vulkan
```

- Images published to `ghcr.io/faisalthaheem/open-lpr`
- **All Docker images are built and published by GitHub Actions CI.** Docker Compose files (`docker-compose.yaml`) only reference pre-built images from GHCR — never use `build:` directives in compose files.
- CI: `.github/workflows/docker-publish.yml` builds `linux/amd64` on push to main and version tags. arm64 was dropped: the deployment host is amd64, no requirement for it was ever documented, and the SPA's arm64 leg failed under qemu emulation (`Illegal instruction` during `npm ci`). Re-adding it means the `platforms:` list in every `docker-publish*.yml` plus a fix for the emulation crash
- Container runs as `django` user via `gosu` (see `docker-entrypoint.sh`)
- `docker-entrypoint.sh` runs migrate + collectstatic + optional createsuperuser on every start
- `fonts-noto` and `fonts-noto-cjk` are installed in the Docker image for Unicode text rendering (Arabic, CJK, etc.) on bounding box visualizations

## Environment Variables

Key variables (see `.env.example` and `.env.llamacpp.example` for full list):

- `QWEN_API_KEY`, `QWEN_BASE_URL`, `QWEN_MODEL` — AI model connection
- `PIPELINE_BACKEND` — `local` (default) or `llm`. The default runs plate detection and OCR with in-process ONNX models instead of the API, which requires the model artifacts to be present. **The rollback is configuration-only**: set `PIPELINE_BACKEND=llm` and redeploy; no migration and no data change, and the LLM path stays fully tested. Full key list in the Local ONNX Pipeline section above.
- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` — Django core
- `CORS_ALLOWED_ORIGINS` — Comma-separated frontend origins allowed to access the API (default: `http://localhost:3000`)
- `CORS_ALLOW_PRIVATE_NETWORK` — Allow browsers to access the API from a public origin when the API resolves to a private IP (default: `False`). Set to `True` when using Cloudflare-proxied frontend with a local API endpoint.
- `RATE_LIMIT_ENABLE` — Enable per-IP rate limiting on API endpoints (default: `True`)
- `RATE_LIMIT_RATE` — Throttle rate in `num/period` format, e.g. `2/min` (default: `2/min`)
- `RATE_LIMIT_EXCLUDE_PATHS` — Comma-separated URL paths excluded from rate limiting (default: `/health/,/api/v1/health-light/`)
- `RATE_LIMIT_INCLUDE_PATHS` — Comma-separated URL paths to rate limit; all other paths are exempt (default: `/api/v1/ocr/`)
- `DATABASE_PATH` — SQLite path (default: project root `db.sqlite3`)
- `MEDIA_PATH` — Media storage (default: `./media`, Docker: `./container-media`)
- `METRICS_FILE_PATH` — Prometheus metrics state file (default: `metrics_state.json` beside the database; Docker: `/app/metrics/metrics_state.json`)
- `AVAILABILITY_REFRESH_SECONDS` — Background refresh interval for the cached availability series (default: `60`)
- `UPLOAD_FILE_MAX_SIZE` — Default 250KB in settings.py (10MB in Docker compose). Bounds bytes on disk, **not memory**
- `UPLOAD_IMAGE_MAX_PIXELS` — Default 40,000,000. Decoded pixels, read from the image header before any decompression. Needed because a flat-colour PNG compresses ~3000:1, so a 0.4MB upload can declare 144MP and cost 430MB of RAM; Pillow's own guard only *warns* under 178MP. 0 disables. Applies in `validators.check_image_dimensions`, called from both the upload validators and `_run_local_pipeline` — do not rely on the upload-time check alone, since that path can also read images already on disk

### SPA Frontend (runtime via Docker environment)

- `BACKEND_API_URL` — Backend API URL (default: empty = relative paths, works behind shared reverse proxy). Docker Compose default: `http://lpr-app:8000`
- `NEXT_PUBLIC_UPLOAD_TIMEOUT` — Upload timeout in ms (default: 120000)

## Deployment

When the user asks to "deploy the change", follow these steps in order:

### 1. Ensure 80%+ test coverage
- Write or update tests to cover the changed code
- Run `python manage.py test` and verify all tests pass
- Ensure coverage is 80%+ for changed files (use `coverage run --source='lpr_app' manage.py test && coverage report`)

### 2. Commit and push via SSH
- Stage only the intended files (never commit secrets)
- Commit with a concise message matching the repo style
- Push to `origin` (git@github.com:faisalthaheem/open-lpr.git) via SSH

### 3. Wait for GitHub Actions CI
- Monitor the workflow run triggered by the push:
  ```bash
  gh run list --limit 1                          # Get latest run ID
  gh run watch <run-id>                          # Stream logs
  ```
- The CI builds amd64 Docker images and publishes to `ghcr.io/faisalthaheem/open-lpr`
- If the build fails, read the logs with `gh run view <run-id> --log-failed`, fix errors, commit and push again

### 4. Pull latest images on prod server
- SSH to prod: `ssh root@10.1.200.101`
- Navigate to the Coolify app directory and pull the latest images:
  ```bash
  ssh root@10.1.200.101 "cd /path/to/app && docker compose pull"
  ```
- If the exact path is unknown, inspect running containers first:
  ```bash
  ssh root@10.1.200.101 "docker ps --format '{{.Names}} {{.Image}}'"
  ```

### 5. Notify user
- Tell the user the images are pulled and ready
- The user will redeploy the app via Coolify themselves

## Conventions

- **Environment variables**: When adding new environment variables, add them to `.env.example`, `.env.llamacpp.example`, and any relevant Docker Compose files. Document them in this file under Environment Variables.
- **Docker images**: All images are built and published by GitHub Actions CI. Never add `build:` directives to Docker Compose files — always reference pre-built images from GHCR.
