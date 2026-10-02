# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Local ONNX plate detection and OCR backend — a YOLOX detector, classical perspective
  rectification, and a PP-OCR CTC recogniser — selectable with `PIPELINE_BACKEND=llm`.
  **See the Changed entry below for the default flip and its caveats.**
- Configuration-declared pipeline stage contract: stages declare their input and output field names and a `PipelineGraph` routes data from those declarations, validating bindings at construction so an unsatisfied edge fails before any model loads
- Per-stage and end-to-end latency metrics (`lpr_pipeline_stage_duration_seconds{stage,outcome}`, `lpr_pipeline_duration_seconds{outcome}`) with configurable budgets; `PIPELINE_LATENCY_BUDGET_SECONDS` defaults to 0.5
- `lpr_app/ml/` training and evaluation tooling, never imported by the web app: a corpus exporter with a leakage-free frame-grouped split, detector training, ONNX export, a benchmark that fails on budget overrun and reports recall bucketed by plate height, and a backend comparison harness
- `ruff` linting and formatting with a committed configuration (`pyproject.toml`), plus a `requirements-dev.txt` that keeps dev tooling out of the production image
- CI workflow (`.github/workflows/test.yml`) running lint, format check, and tests with a coverage gate on every push and pull request
- `METRICS_FILE_PATH` environment variable, so Prometheus metrics state is configurable outside Docker
- `AVAILABILITY_REFRESH_SECONDS` setting controlling the background refresh interval for the cached availability series
- `reset_qwen_client()` helper for tests that need to change client configuration

### Changed
- **`PIPELINE_BACKEND` now defaults to `local`.** Images are detected and read by in-process ONNX models by default, at ~60ms per image against the LLM backend's ~3600ms — the only path that fits the project's sub-500ms budget. Measured on the corpus, the local backend also detects more reliably (recall 1.000 vs 0.375 at IoU 0.3) and reads more plates (0.95 vs 0.375 of detections).
  - **Its text accuracy is unmeasured.** The corpus annotates plate boxes with no transcription labels, so there is no ground truth to score a read against; the local backend demonstrably misreads some plates it does find (`QG.260` → `0G260`). The flip rests on latency and detection numbers, not on a text-accuracy result, because none exists. Numbers recorded in `openspec/changes/measure-local-backend-accuracy/COMPARISON.md`.
  - **Model artifacts are now required at runtime.** A deployment without `model/plate/` populated cannot process images. This fails loudly with the resolved path rather than degrading to zero plates, which would be indistinguishable from a working service that found nothing.
  - **Rollback is configuration-only:** set `PIPELINE_BACKEND=llm` and redeploy. No migration, no data rewrite, and the LLM path remains fully tested.
- `lpr_app/services/image_processing_service.py` — the three-phase LLM procedure moved from inline code in `process_uploaded_image` into `_run_llm_pipeline`, alongside a new `_run_local_pipeline`. The LLM path's behaviour is unchanged, including its fixed-pixel OCR crop padding; tests pin the prompts sent, the padding applied, and the errors returned
- `openai` upgraded from `1.30.1` to `3.22.1`; the `DefaultHttpxClient` compatibility workaround it required is no longer needed
- All `requirements.txt` entries are now pinned exactly instead of using version ranges
- Importing `settings.py` no longer creates directories; directory creation moved to `docker-entrypoint.sh`
- Removed the deprecated `SECURE_BROWSER_XSS_FILTER` setting (a no-op since Django 4.0)
- Removed the legacy dictionary form of `detections`, which no code path can produce
- Removed leftover `DEBUG:` logging from request and inference paths; the `lpr_app` logger is now `INFO`
- Deleted `docker-compose-llamacpp-cpu.yml` and `docker-compose-llamacpp-amd-vulcan.yml`; use the profile-based `docker-compose.yaml`
- Manual integration and diagnostic scripts moved to `scripts/`, out of test discovery

### Fixed
- `lpr_processing_duration_seconds` was exported but never observed — no code path constructed `PerformanceTracker("processing")`, so the metric a dashboard already graphs was always empty. It is now recorded per upload on whichever backend ran, which is what makes the two backends comparable on one series.
- YOLOX output decoder applied `exp()` to the regressed width and height, which the ONNX export already does; every box inflated until it clamped to the whole frame
- PP-OCR CTC decode applied softmax to output that the export already emits as normalised probabilities, which drove recognition confidence to exactly 0.00 on every plate
- PP-OCR label layout assumed `[""] + dictionary`, omitting the trailing space class the model emits, making the highest index look out of range on every decode
- Plate regions were passed to rectification as `(x1, y1, x2, y2)` where `(x, y, w, h)` was expected, so the local backend rectified a mostly-vehicle crop and read nothing from it
- Test suite could not run clean: Django's discovery walked the project root and imported manual harness scripts, always reporting 2 collection errors
- `GET /api/v1/images/` returned `500` on a non-integer `page` or `page_size`; it now returns `400` naming the offending parameter, and clamps out-of-range values
- `analyze_images_batch` discarded results for every plate when a single crop failed; each item is now independent
- Unterminated markdown code fences in model responses were parsed as truncated JSON, failing otherwise-valid responses
- Naive datetimes were written against `USE_TZ=True`, so stored timestamps and media date partitions could disagree; all datetimes are now timezone-aware
- Media paths are now bucketed by the same aware clock as `upload_timestamp`, so `uploads/YYYY/MM/DD/` agrees with the recorded date regardless of server timezone
- `/api/v1/availability/` queried Prometheus synchronously on every request, occupying a worker for up to 10s; it now serves from a cache refreshed on a schedule
- Local test runs logged `Permission denied: '/app'` when persisting metrics

## [1.4.0] - 2026-06-02

### Added
- SPA health indicator in navbar with real-time backend status polling (green/yellow/red dot)
- Service availability graph on home page showing 3-day uptime history from Prometheus
- `/api/v1/health-light/` lightweight health endpoint for SPA polling
- `/api/v1/availability/` endpoint returning historical availability data
- `CORS_ALLOW_PRIVATE_NETWORK` setting for browser Private Network Access support (needed when SPA is Cloudflare-proxied but API resolves to private IP)
- Canary cleanup service that removes failed canary images and reports impact in metrics
- `SPA_PORT` environment variable for configurable SPA container port

### Fixed
- Health indicator permanently stuck on "Checking..." — `HealthProvider` now wraps entire body layout including navbar
- CORS Private Network Access blocked when frontend is public (Cloudflare) but API resolves to private IP
- APScheduler running under `manage.py` commands (now gated to only run under Gunicorn)
- SPA container health check failing in Alpine-based images (`127.0.0.1` instead of `localhost`)
- `CORS_ALLOWED_ORIGINS` missing from docker-compose environment

### Changed
- Docker Compose passes `CORS_ALLOWED_ORIGINS` to both SPA and Django containers
- Live demo URL updated to `openlpr.computedsynergy.com`

## [1.3.0] - 2026-05-24

### Added
- Runtime backend API configuration via `BACKEND_API_URL` environment variable (no rebuild needed)
- `/api/config` server-side endpoint that returns the backend URL to the SPA client
- `/health` route on SPA that redirects to the Django backend health endpoint
- `AppInitializer` component with spinner during config loading and error/retry state on failure

### Changed
- SPA now resolves backend API URL at runtime instead of build time
- `spa-dev.py` uses `BACKEND_API_URL` instead of `NEXT_PUBLIC_API_BASE_URL`
- Docker Compose SPA service passes `BACKEND_API_URL` via `environment:`
- `getImageUrl` and `getDownloadUrl` are now async (runtime-resolved base URL)
- Recent uploads on home page use shared `ImageCard` component
- Health nav link uses `/health` (SPA proxy) instead of direct backend URL
- Removed `NEXT_PUBLIC_API_BASE_URL` build arg from SPA Dockerfile (replaced by runtime `BACKEND_API_URL`)

### Removed
- Dead `NEXT_PUBLIC_MAX_UPLOAD_SIZE` build arg from SPA Dockerfile

## [1.2.3] - 2026-05-24

### Added
- SPA frontend env vars (`NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_UPLOAD_TIMEOUT`) to `.env.example` and `.env.llamacpp.example`
- SPA vars documented in AGENTS.md Environment Variables section
- Conventions section in AGENTS.md: env var documentation requirement, no `build:` in compose files

### Changed
- Docker image convention documented in AGENTS.md: all images built by CI, compose only references GHCR

### Removed
- Dead `NEXT_PUBLIC_MAX_UPLOAD_SIZE` build arg from SPA Dockerfile (max upload size fetched at runtime via `/api/v1/config/`)

## [1.2.2] - 2026-05-24

### Changed
- Add path filters to Django backend CI workflow to reduce CI noise on docs-only changes

## [1.2.1] - 2026-05-24

### Fixed
- Grant `contents:write` permission to Docker publish workflows for SBOM release attachment

### Removed
- Deleted `.roo/` directory (Roo Code IDE config artifacts)
- Deleted `nginx/` directory (unused — Traefik is the active reverse proxy)

## [1.2.0] - 2026-05-24

### Added
- Next.js 16 SPA frontend with React 19 and Tailwind CSS 4
- Storybook 10 with component stories for all UI components
- Dark mode support with system preference detection in SPA
- REST API endpoints: `/api/v1/images/`, `/api/v1/images/<id>/`, `/api/v1/download/<id>/<type>/`, `/api/v1/config/`
- CORS support via `django-cors-headers` for SPA cross-origin requests
- Configurable fixed-pixel padding for OCR crop regions
- Disclaimer banner in SPA with no-liability and data usage notice
- SPA pages: Home (upload), Images (history with search/filter/pagination), Image Detail (detection results, logs, raw API response)

### Changed
- **Breaking**: Django backend is now API-only — all server-rendered templates removed
- Django upgraded from 4.2.30 to 5.2 LTS (supported through April 2028)
- Python minimum version raised from 3.8+ to 3.10+
- Frontend migrated from Bootstrap 5 / Django templates to Next.js SPA
- Removed all Django HTML templates, forms, template tags, and web views
- Removed legacy monolithic `views.py` and `views_refactored.py`
- Removed `nginx/` directory (Traefik is the active reverse proxy)
- File upload accepts WEBP in addition to JPEG and PNG
- README updated: tech stack badges, API endpoints, file structure, acknowledgments
- AGENTS.md updated to reflect API-only Django + Next.js SPA architecture

### Fixed
- Hydration mismatch in Next.js SPA disclaimer banner (extracted to `"use client"` component)
- `.gitignore` `lib/` pattern fixed to `/lib/` (was matching `single-page-ui/src/lib/`)

### Removed
- `templates/` directory (all HTML templates)
- `lpr_app/forms.py` (Django forms — only used by removed web views)
- `lpr_app/templatetags/` (template tag libraries)
- `lpr_app/views/web_views.py` (template-rendering views)
- `lpr_app/views.py` (legacy monolithic views)
- `lpr_app/views_refactored.py` (unused leftover)
- `lpr_app/utils/response_helpers.py` `WebResponseHelper` class
- `nginx/` directory (unused — Traefik is the active reverse proxy)

## [1.1.0] - 2026-05-15

### Added
- Two-phase LPR pipeline with dynamic detection scaling for improved accuracy
- Comprehensive canary monitoring system with automated health checks
- Profile-based Docker Compose with merge design pattern (replaces individual compose files)
- Custom monitoring Docker images (Prometheus, Grafana, Blackbox Exporter) with embedded configs
- GitHub Actions workflow for building and publishing monitoring images
- NVIDIA CUDA GPU support for local LlamaCpp inference
- AMD Vulkan GPU support for local LlamaCpp inference
- Dark mode support with system theme detection and automatic switching
- Dynamic font scaling for OCR text visualization
- Favicon for the LPR application
- Star History chart in README
- Coolify deployment support with custom Docker images
- Configurable Traefik router rules via environment variables
- Configurable service ports to avoid conflicts
- CSRF trusted origins configuration for cross-origin requests
- Prometheus monitoring with LPR app dashboard
- Grafana dashboards for both LPR app and canary service
- Blackbox exporter for HTTP probing
- Simplified mobile pagination
- Liability disclaimer in application header
- Live demo link in README

### Changed
- Split monolithic `views.py` into modular view components (`views/` subpackage)
- Django upgraded from 4.2.7 to 4.2.30
- Pillow upgraded from 10.1.0 to 12.2.0
- Gunicorn upgraded from 21.2.0 to 22.0.0
- Maximum image upload size reduced from 10MB to 250KB for optimized processing
- Homepage updated to show 9 processed images with annotations
- UI condensed for better screen utilization
- Image list page now shows annotated images with OCR text and plate count
- README reorganized with collapsible sections and compact navigation

### Fixed
- Fixed `django.logstatic` typo in docker-entrypoint.sh causing chown error on startup
- Fixed metrics directory permissions by adding `/app/metrics` to Dockerfile
- Fixed metrics state file (`metrics_state.json`) creation and permissions in entrypoint
- Fixed canary service HTTP 502 error and connectivity issues
- Fixed canary image cleanup functionality
- Fixed canary dashboard configuration and connectivity
- Fixed Prometheus and Blackbox Exporter duplicate binary names in CMD
- Fixed Grafana provisioning duplicate UID warnings
- Fixed metrics endpoint errors
- Fixed multi-platform Docker build issue
- Fixed Traefik Docker API compatibility issue
- Fixed database file ownership to prevent readonly database errors
- Fixed hardcoded API response data in LPR processing
- Fixed KeyError in `get_first_ocr_text()` method
- Fixed OCR results display in dark mode
- Fixed pagination URL encoding and error handling
- Fixed reverse pagination on image list page
- Fixed duplicate timestamps (removed redundant ones)
- Fixed display of correct max file size on upload page
- Eliminated duplicate Traefik configuration
- Fixed navigation links in README.md

### Deprecated
- Individual Docker Compose files (`docker-compose-llamacpp-cpu.yml`, `docker-compose-llamacpp-amd-vulcan.yml`)
- Use profile-based approach with main `docker-compose.yml` instead

### Security
- Django security patches included in upgrade to 4.2.30
- Pillow security patches included in upgrade to 12.2.0
- Non-root Docker user maintained
- Input validation and sanitization maintained
- CSRF protection with trusted origins support

## [1.0.0] - 2025-11-23

### Added
- Initial release of Open LPR - License Plate Recognition System
- Django-based web application with license plate recognition capabilities
- RESTful API with comprehensive endpoints for image processing
- User-friendly web interface with drag-and-drop upload functionality
- Image processing pipeline with bounding box visualization
- Search and filter functionality for processed images
- Responsive design that works across all devices
- Docker deployment support with optimized multi-stage Dockerfile
- Automated CI/CD pipeline with GitHub Actions
- Multi-architecture support (linux/amd64, linux/arm64)
- Automatic publishing to GitHub Container Registry
- Software Bill of Materials (SBOM) generation for security scanning
- Local inference support with LlamaCpp server
- CPU and GPU deployment options for LlamaCpp
- Comprehensive documentation for local deployment
- Environment configuration templates
- Model download automation
- Visual showcase with screenshots in documentation
- API documentation with detailed endpoint descriptions
- Docker deployment guide with multiple deployment options
- LlamaCpp and ROCm resources collection
- Troubleshooting guides and best practices

### Features
- AI-powered detection using qwen3-vl-4b-instruct vision-language model
- Advanced OCR integration with confidence scores
- Bounding box visualization for detected plates and OCR text
- Permanent storage of uploaded and processed images
- Side-by-side comparison of original and processed images
- Health check endpoint for monitoring
- Download functionality for original and processed images
- Processing status tracking with AJAX endpoints
- Comprehensive error handling and logging
- Security best practices including non-root Docker user
- Environment-based configuration management
- Input validation and sanitization

### Documentation
- Comprehensive README with visual showcase
- Detailed API documentation
- Docker deployment guide
- LlamaCpp deployment guide
- LlamaCpp and ROCm resources collection
- Contributing guidelines
- Code style guidelines

### Technical Details
- Django 4.x web framework
- Bootstrap 5 for responsive UI
- Gunicorn WSGI server for production
- SQLite database with migration support
- Docker containerization with multi-stage builds
- GitHub Actions for CI/CD
- Semantic versioning with automated tagging
- SBOM generation for security scanning

### Security
- Non-root Docker user for security
- Environment-based configuration
- Secure file upload handling
- Input validation and sanitization
- CSRF protection
- Security headers configuration

### Performance
- Optimized Docker image for production use
- Gunicorn WSGI server with 3 workers
- Efficient image processing pipeline
- Configurable batch processing
- Multi-architecture Docker images

### Developer Experience
- Well-structured codebase following Django best practices
- Comprehensive documentation
- Environment configuration templates
- Management commands for project setup
- Clear code organization with separation of concerns

### Deployment
- Standard Docker deployment with cloud-based AI services
- LlamaCpp CPU deployment for local inference
- LlamaCpp GPU deployment with AMD Vulkan support
- Environment configuration templates
- Automated model download
- Health checks and monitoring

### API Endpoints
- Web endpoints for user interface
- REST API endpoints for programmatic access
- Health check endpoint
- File upload and processing endpoints
- Image download endpoints
- Search and filtering endpoints

### Known Limitations
- Large images (>10MB) may require increased memory allocation
- GPU acceleration is currently limited to AMD GPUs with Vulkan support
- Concurrent processing is limited by Django's development server (use Gunicorn in production)

### Dependencies
- Django 4.x
- Bootstrap 5
- Gunicorn
- Docker
- LlamaCpp (for local inference)
- Qwen3-VL model

### License
- MIT License

---

## [Unreleased]

### Planned
- Batch processing capabilities
- Real-time video stream processing
- Additional language support for license plates
- Performance optimizations
- Mobile application