## Why

A codebase review surfaced a set of non-security defects that are actively degrading reliability and developer velocity: the test suite cannot run clean, nothing in CI runs tests or lint, every request builds a throwaway HTTP client, the image list endpoint returns 500s on malformed input, timezone-naive datetimes are written against a `USE_TZ=True` project, and a large amount of debug logging and legacy response-format branching is shipped in hot paths.

None of these are individually urgent, but together they mean regressions are caught only if a human remembers to run things locally. Fixing them now — while the codebase is small (7k lines, 214 tests) — is far cheaper than after the async processing work lands.

## What Changes

**Developer velocity and guardrails**

- Move the ad-hoc root-level scripts (`test_api.py`, `test_metrics.py`, `test_setup.py`) out of test discovery so `manage.py test` exits clean.
- Add `ruff` for linting and formatting, with a config committed to the repo.
- Add a CI workflow that runs lint, tests, and a coverage gate on every push and pull request. The existing Docker workflows build and publish but never verify the code.
- Delete the deprecated `docker-compose-llamacpp-cpu.yml` and `docker-compose-llamacpp-amd-vulcan.yml` files, which contradict the documented profile-based compose workflow.

**Correctness**

- `GET /api/v1/images/` SHALL return `400` for non-integer or out-of-range `page`/`page_size` parameters instead of raising an unhandled `ValueError` and returning `500`.
- Replace naive `datetime.now()` / `datetime.utcnow()` calls with `django.utils.timezone` equivalents across models, services, and views, so stored timestamps are timezone-aware under `USE_TZ=True`.
- Move `os.makedirs` calls out of `settings.py` import-time side effects and into the container entrypoint, so importing settings is side-effect free.
- Remove the long-deprecated `SECURE_BROWSER_XSS_FILTER` setting and other redundant Django defaults.

**Performance**

- Cache the `QwenVLClient` singleton instead of constructing a new `OpenAI` / `httpx` client — and therefore a new connection pool — on every request, including health checks.
- Make `analyze_images_batch` fault-tolerant: a failure on one plate crop no longer discards results already obtained for the other crops.
- Serve `/api/v1/availability/` from a periodically refreshed cache rather than making a blocking 10-second-timeout HTTP call to Prometheus on every request.

**Maintainability**

- Remove leftover `DEBUG:` logging statements from hot paths and drop the `lpr_app` logger to `INFO`.
- Consolidate the triplicated markdown-fence JSON extraction in `qwen_client.py` into a single helper that handles unterminated fences.
- Delete the legacy dictionary-format `detections` branches in `models.py` and `qwen_client.py`, plus the unused back-compat `LPR_PROMPT` constant. The list format is current.
- Expose `METRICS_FILE_PATH` through `config()` so it is overridable outside Docker (currently a hardcoded `/app/...` default that breaks local test runs).
- Pin all `requirements.txt` dependencies consistently and upgrade `openai` to a current release, which is expected to remove the `DefaultHttpxClient()` compatibility workaround.

**Explicitly out of scope for this change**

Security-related findings from the review (endpoint authentication, canary secret handling, `X-Forwarded-For` trust in rate limiting, metrics endpoint exposure) are excluded by request and will be handled in a separate change.

Moving the vision pipeline to an async queue, and migrating off SQLite, are larger architectural shifts that should follow this cleanup.

## Capabilities

### New Capabilities
- `ci-quality-gates`: linting, formatting, and test/coverage enforcement in CI and locally.
- `qwen-client-lifecycle`: shared client instance, connection reuse, and fault-tolerant batch inference.
- `api-input-validation`: validation and error semantics for numeric and date query parameters.
- `timezone-correctness`: timezone-aware datetime handling across models, services, and views.
- `logging-hygiene`: removal of debug residue from request and inference hot paths.
- `response-parsing`: consolidated, robust extraction of JSON from model responses.
- `detection-schema-simplification`: single supported `detections` schema, removal of legacy formats.
- `settings-configuration`: side-effect-free settings, removal of deprecated settings, env-driven metrics path.
- `availability-caching`: cached Prometheus availability data with background refresh.
- `dependency-hygiene`: consistent version pinning and current dependency versions.

### Modified Capabilities
- `api-image-list`: adds validation requirements for `page` and `page_size`, changing behavior from unhandled `500` to an explicit `400` response.

## Impact

**Code**
- `lpr_app/views/api_views.py` — pagination validation, availability caching, debug logging removal, timezone-aware timestamps.
- `lpr_app/services/qwen_client.py` — client caching, JSON extraction helper, legacy schema removal, `LPR_PROMPT` removal.
- `lpr_app/services/image_processing_service.py` — batch fault tolerance, debug logging removal, timezone-aware timestamps.
- `lpr_app/models.py` — timezone-aware upload paths, legacy schema branch removal.
- `lpr_app/metrics.py` — configurable metrics file path.
- `lpr_project/settings.py` — side-effect removal, deprecated setting removal, metrics path via `config()`.
- `docker-entrypoint.sh` — create required directories.

**Tests**
- New tests for pagination validation, `qwen_client` caching, batch fault tolerance, JSON extraction edge cases, and timezone-aware timestamps.
- Root-level scratch scripts relocate out of `lpr_app/tests` discovery.

**CI / Tooling**
- New workflow file for lint/test/coverage.
- New `ruff` configuration.
- Removed deprecated compose files.

**Dependencies**
- Add `ruff` as a dev dependency.
- Upgrade `openai` from `1.30.1`.
- Consistent pinning applied across `requirements.txt`.

**Configuration**
- `METRICS_FILE_PATH` added to `.env.example` and `.env.llamacpp.example`.

**Compatibility**
- `GET /api/v1/images/` returns `400` where it previously returned `500` on malformed pagination. The SPA already treats non-200 as an error, so no frontend change is required.
- Removal of the legacy `detections` dictionary format assumes no stored `api_response` records predate the list format. Records written by older versions will read as zero plates. A one-off check or data migration should confirm no such rows exist.