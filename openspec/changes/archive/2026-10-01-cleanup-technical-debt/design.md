## Context

`lpr_app` is a ~7,000 line Django 5.2 app (excluding tests) with a ~4,000 line Next.js SPA. It runs as a gunicorn container behind Traefik, backed by SQLite, calling a Qwen3-VL model over an OpenAI-compatible endpoint.

The review that motivated this change covered the request path (`api_views.py`), the inference path (`image_processing_service.py` → `qwen_client.py`), settings, and CI. It found no security issues to address here (excluded by request), but a consistent theme: **the codebase has accumulated the debris of fast iteration and none of it is mechanically enforced.**

Concretely:

- `manage.py test` runs 214 tests and always exits non-zero, because Django's test discovery walks the project root and imports `test_api.py`, `test_metrics.py`, and `test_setup.py` — ad-hoc manual scripts that aren't valid unittest modules. This means the suite has been "red" for long enough that nobody notices, which destroys its value as a signal.
- CI (`.github/workflows/`) has four workflows, all of which build and publish Docker images. No workflow runs tests or lint. AGENTS.md asserts an 80% coverage requirement; nothing enforces it.
- `get_qwen_client()` builds a fresh `QwenVLClient`, `DefaultHttpxClient`, and `OpenAI` instance on every call. Because `analyze_image` and `health_check` each call it, every OCR request and every health check pays for TLS setup, connection establishment, and pool teardown.
- `api_image_list` calls `int(request.GET.get('page_size', 12))` with no guard. A malformed query string raises `ValueError` out of the view → `500`. `api_availability` in the same file already does this correctly, so the fix is to make one path match the other.
- `USE_TZ = True`, but `models.py`, `image_processing_service.py`, and `api_views.py` all use naive `datetime.now()` / `datetime.utcnow()`. These produce local-time strings and trigger Django's naive-datetime warnings.
- `settings.py` performs `os.makedirs` at import time for the DB dir, media dir, and static dir. This is why the test run logs `Permission denied: '/app'` — the metrics module defaults to `/app/metrics/` and settings creates paths it doesn't own.
- `lpr_app/metrics.py` hardcodes `METRICS_FILE_PATH = '/app/metrics/metrics_state.json'` as a `getattr(settings, ...)` fallback that is never actually set in settings, so it is unoverridable outside Docker.
- The same markdown-fence JSON extraction block is copy-pasted across `parse_lpr_response`, `parse_detection_response`, and `parse_ocr_response`. All three break if the model emits an unterminated fence.
- `models.py` and `scale_coordinates_in_response` both branch on a legacy dictionary `detections` format alongside the current list format, and `LPR_PROMPT` is a combined-prompt constant no longer used by the two-phase pipeline.
- Roughly 15 `logger.info(f"DEBUG: ...")` statements remain in `api_ocr_upload`, `qwen_client`, and `process_uploaded_image`. The `lpr_app` logger is set to `DEBUG`, so all of it lands in `django.log`.

## Goals / Non-Goals

**Goals**

- `python manage.py test` exits `OK` with no collection errors.
- A pull request that breaks tests or lint fails CI before any image is built.
- A single `QwenVLClient` instance, and therefore a single connection pool, is shared for the process lifetime.
- Malformed query parameters produce `400` with a useful message, not `500`.
- All persisted and returned timestamps are timezone-aware.
- Importing `settings.py` has no filesystem side effects.
- Debug residue is gone from hot paths; `django.log` reflects only actionable events.
- `detections` has exactly one supported shape in code.
- `METRICS_FILE_PATH` is configurable via environment.
- Dependency versions are pinned consistently and `openai` is on a current release.

**Non-Goals**

- Any authentication, authorization, canary-secret, or header-trust work. Explicitly excluded.
- Async processing / job queue. The pipeline stays synchronous inside the request.
- Migrating off SQLite.
- Restructuring `qwen_client.py` beyond the changes named above (the three parse functions keep their signatures).
- Any change to the SPA.
- Changing API response shapes or field names.

## Decisions

### 1. Relocate the scratch scripts rather than deleting them

`test_api.py` and `test-llamacpp-integration.py` are genuine manual integration harnesses referenced in AGENTS.md as a documented workflow. `test_metrics.py` and `test_setup.py` are one-off diagnostics.

**Decision:** move all four to `scripts/`. `scripts/` is not on the path Django's runner walks, so collection is fixed and the harnesses survive.

**Alternative considered:** renaming them `check_*.py` / `probe_*.py`. Rejected — moving them is clearer and groups them with `docker-entrypoint.sh` and the other operational scripts already at the root.

**Alternative considered:** adding a `test_*.py` exclusion to `manage.py test`. Rejected — it papers over the symptom and the harness scripts have no business in the project root.

### 2. Ruff for lint and format, with a permissive initial rule set

**Decision:** add `ruff` (pinned) with `ruff format` and a rule set of `E`, `F`, `I`, `B`, `UP`, at a first pass that fixes everything it reports rather than using `per-file-ignores` to silence noise. Configure `line-length = 120`, matching the existing code's widest practical lines.

**Alternative considered:** `flake8` + `black`. Rejected — ruff subsumes both in one tool and one config, with materially faster execution.

**Alternative considered:** adopt ruff's full default-plus rule set immediately. Rejected — the point is a green baseline that everyone can keep green; a larger set invites a long first-PR of unrelated churn.

**Risk accepted:** formatting the existing tree will produce a large mechanical diff. It is a one-time cost and `ruff format` makes every subsequent contribution conflict-free by construction.

### 3. Cache the Qwen client as a lazily-initialized module singleton

**Decision:** convert `get_qwen_client()` into a cached accessor using `functools.lru_cache(maxsize=1)`. Construction failures (missing `QWEN_API_KEY`) propagate on first call and are then cached by `lru_cache` only on success, so a misconfigured deploy fails loudly rather than being masked by a cached exception.

**Alternative considered:** `@lru_cache` directly on `QwenVLClient.__init__`-adjacent factory vs. an explicit module-level `_client` global with a lock. `lru_cache` is thread-safe enough here: the cache miss path may construct more than one client under a race, but both are functionally identical and one wins. The extra `httpx` client constructed in a rare race is a negligible cost and does not justify hand-rolled locking.

**Alternative considered:** Django's `singleton` pattern or a Django cache. Rejected — the client holds an open connection pool; the cache serializes awkwardly and offers no benefit over a plain function-level cache.

**Note on multi-process:** gunicorn runs multiple workers, so this yields one client per worker, not one per host. That is the correct granularity — an `httpx` client is not safe to share across processes.

### 4. Make `analyze_images_batch` fault-tolerant per item

Currently a single exception in any iteration returns `None` for the whole batch, so a single malformed plate crop discards OCR results already obtained for every other plate. That is the worst-case behavior for a multi-plate image.

**Decision:** wrap each per-image call in its own `try`/`except`. On failure, append `None` in that slot and continue. Return the full-length list of `Optional[str]`. The caller in `image_processing_service.py` already handles falsy entries by setting `detections[idx]['ocr'] = []`, so it needs only a small change to stop treating a `None` return as total failure.

The return type becomes `list[Optional[str]]` rather than `Optional[list[str]]`. The "whole call raised" case disappears because per-item failures are absorbed; a caller-level check for `None` is retained for defence.

**Alternative considered:** bounded parallelism (thread pool) across the crops. Genuinely attractive for latency, but it changes concurrency characteristics against a single inference endpoint and risks triggering server-side queuing. Deferred — the fault-tolerance fix is worth doing now and is orthogonal to parallelizing later.

### 5. Parse query parameters through a small helper that returns 400

`api_availability` already demonstrates the right pattern (`try`/`except (ValueError, TypeError)` with a fallback), but it *defaults* rather than rejecting. For pagination, silently falling back to a default on garbage input hides client bugs.

**Decision:** a module-level helper in `api_views.py` that parses an integer parameter and, on failure, returns a `JsonResponse` with `400` and a message naming the offending parameter. `page` floors at 1; `page_size` clamps to `[1, 100]`, preserving the existing `min(..., 100)` cap.

**Alternative considered:** a DRF-style parser library or a custom Django system check. Rejected — this is one endpoint with two integer parameters. Introducing a dependency or a reusable framework for it is disproportionate.

**Alternative considered:** clamp silently like `api_availability` does. Rejected for `page_size`; rejected for `page` too, since a client sending `page=abc` has a bug worth surfacing.

### 6. Adopt `django.utils.timezone` everywhere, including upload paths

**Decision:** replace `datetime.now()` with `django.utils.timezone.now()` in `models.py`, `image_processing_service.py`, and `api_views.py`; replace `datetime.utcnow()` / `utcfromtimestamp()` in `api_availability` with timezone-aware equivalents.

`upload_to_uploads` and `upload_to_processed` are the subtle case: they currently bucket media into `uploads/YYYY/MM/DD/` using *server local time*, while `upload_timestamp` is stored as UTC. Under a non-UTC container timezone the two disagree, and images land in a date folder that differs from their recorded upload date. Using `timezone.now()` makes the partition consistent with the stored timestamp.

**Alternative considered:** switching `TIME_ZONE` handling to a fixed UTC everywhere and accepting local-time partitions. Rejected — bucketing on the aware "now" keeps the folders human-meaningful in local time while the DB stores absolute UTC, which is what a reader expects.

**Note:** existing rows keep their naive UTC values; no backfill is planned. This is display-level drift only, not data corruption.

### 7. Move directory creation into the entrypoint

**Decision:** remove the `os.makedirs` calls from `settings.py`. `docker-entrypoint.sh` already runs on every container start and already runs `migrate` + `collectstatic`, so it is the natural place. For local development the directories are created by `.gitignore`d paths that developers already have, and `manage.py` runs will surface a clear error if not.

**Alternative considered:** a Django `AppConfig.ready()` hook that creates directories. Rejected — `ready()` runs on every management command including `collectstatic` and `test`, reintroducing import-time-ish side effects and complicating test isolation. The entrypoint is the correct place for deployment-shaped setup.

### 8. Consolidate JSON extraction with a fence-tolerant parser

**Decision:** a single `_extract_json_text(response_text: str) -> str` helper that:
1. Strips leading/trailing whitespace.
2. If a ` ```json ` fence is present, takes content after it up to the next fence; if no closing fence exists, takes content to end of string.
3. Else if a bare ` ``` ` fence is present, same logic.
4. Else returns the whole string.

The current `.find('```', start)` returns `-1` when unterminated, so `response_text[start:-1]` silently truncates the last character and raises `JSONDecodeError` for valid JSON. Handling the unterminated case is a real correctness fix, not just deduplication.

**Alternative considered:** strip fences with a regex. Rejected — the branch for a fenced/unfenced/mixed response is clearer as explicit code, and a regex obscures the unterminated-fence case that motivated the change.

**Note:** the three public functions keep their existing signatures and remain the only entry points; the helper is private.

### 9. Remove the legacy `detections` dictionary branches

**Decision:** delete the `isinstance(detections, dict)` branches in `models.py` (`get_total_ocr_count`, `get_first_ocr_text`), in `scale_coordinates_in_response`, and in `scale_detection_coordinates`, plus the old-format `text_value` handling inside them. Remove the unused `LPR_PROMPT` constant.

**Rationale:** the two-phase pipeline only ever writes the list format. The dict branches are unreachable from current code paths and exist purely as defensive handling for responses the app itself produced in an earlier version.

**Alternative considered:** keeping the branches behind a version check. Rejected — no `api_response` row can be produced by current code in dict form, so the check would always be false.

**Risk and required verification:** any `UploadedImage.api_response` row written before the list format landed will read as zero plates. **Before deleting, query the table** for rows where `detections` is not a JSON array. If any exist, either migrate them or retain the dict branch for reads only. This is a blocking prerequisite, not a nice-to-have.

### 10. Cache availability data with background refresh

`/api/v1/availability/` makes a blocking `urllib` call to Prometheus with a 10-second timeout on every request. An unresponsive Prometheus turns every SPA availability chart load into a 10-second hang, and each request occupies a gunicorn worker for that duration.

**Decision:** use Django's cache framework. The view reads from cache and returns immediately; a refresh job updates the cache on a fixed interval via the existing APScheduler integration (`lpr_app/scheduler.py` already hosts `run_retry_stuck_images`). When the cache is cold, the view performs one inline fetch rather than returning empty, so first paint is correct.

**Alternative considered:** have Prometheus push to the app, or have the SPA fetch Prometheus directly. Both change the deployment topology and the CORS posture — out of scope for a cleanup change.

**Alternative considered:** shorter timeout (e.g. 2s) and no cache. Rejected — it still blocks a worker per request and produces a degraded chart under load rather than serving slightly stale data.

**Chosen cache backend:** the project currently uses Django's default (locally memory). A per-worker memory cache means each worker refreshes independently, which is acceptable here — the data is a health metric, not a source of truth. If the refresh interval is set well below the scrape interval, the duplication is harmless. Not switching to Redis as part of this change.

### 11. Pin dependencies and upgrade `openai`

**Decision:** pin every `requirements.txt` entry exactly, including `Django` and `APScheduler` which currently use ranges. Upgrade `openai` from `1.30.1` (mid-2024) to a current release.

**Rationale for the `openai` upgrade:** `1.30.1` is old enough that the vendored `httpx` conflicts with the installed `httpx`, which is why `qwen_client.py` constructs a `DefaultHttpxClient()` explicitly with the comment "This fixes the compatibility issue between OpenAI and httpx." On a current SDK this workaround is unnecessary.

**Verification required before removing the workaround:** run a real inference request against the configured endpoint. If the upgrade is too risky for the release window, the alternative is to keep `1.30.1` and keep the workaround — the cleanup is independent and can ship either way. This is the one item in the change with a genuine external dependency and no way to verify it from the test suite alone.

Note that `requirements.txt` has no dev/extra split. `ruff` belongs in a separate dev requirements file or as a CI-only install step, not in the runtime image.

### 12. Wire `METRICS_FILE_PATH` through settings

**Decision:** add `METRICS_FILE_PATH = config('METRICS_FILE_PATH', default=str(LOG_DIR / 'metrics_state.json'), cast=str)` to `settings.py`, keeping `metrics.py`'s `getattr(settings, 'METRICS_FILE_PATH', ...)` read but with the Docker path as the explicit env default in compose files.

**Rationale:** the current hardcoded `/app/metrics/...` default is what produces `Permission denied: '/app'` during local test runs. Deriving the default from `LOG_DIR` (already the DB dir) makes local runs work with no configuration while Docker continues to use `/app/metrics` via env.

**Alternative considered:** defaulting the in-code fallback to a temp dir. Rejected — an env-driven setting in `settings.py` is consistent with how every other path in this project is configured, and keeps `metrics.py` free of path policy.

### 13. Remove deprecated and redundant settings

**Decision:** delete `SECURE_BROWSER_XSS_FILTER` (removed in Django 4.0; this project runs 5.2, so it is a no-op that implies protection it does not provide). Drop `SECURE_CONTENT_TYPE_NOSNIFF` back to the Django default rather than stating it explicitly.

**Note:** the security posture of the deployment is out of scope for this change per the exclusions. This decision removes a *misleading* setting; it does not add or weaken any control.

### 14. Delete the deprecated per-profile compose files

**Decision:** remove `docker-compose-llamacpp-cpu.yml` and `docker-compose-llamacpp-amd-vulcan.yml`. `docker-compose.yaml` is the documented entrypoint and AGENTS.md states the individual compose files must not be used.

**Alternative considered:** keep them but add a deprecation header. Rejected — they already contradict the documented workflow and nothing references them; leaving them invites another deploy from the wrong file.

**Verification:** grep the repo (including README, docs, and scripts) for references to both filenames before deleting, and update any that exist.

## Risks / Trade-offs

- **Ruff reformat produces a large diff** → Do it as its own commit, separate from behavioral changes, so a formatting-only revert is possible without losing fixes. State this in the PR description.

- **Deleting legacy dict branches loses plate data for old rows** → Blocking prerequisite: query for `detections` non-array rows before touching the code. If rows exist, migrate or keep read-only compatibility. Do not merge without this check.

- **`openai` upgrade could change response parsing or retry behaviour** → Upgrade and verify with a real request against the live endpoint. If verification isn't possible in the release window, defer the upgrade and keep `1.30.1` plus the httpx workaround; the rest of the change is independent.

- **Caching the Qwen client changes failure semantics** → A client created at first use holds its config for process lifetime, so changing `QWEN_BASE_URL` requires a process restart. That is already true of Django settings in practice. Verify that no test relies on constructing differently-configured clients; such tests should build their own instance rather than mutating the cached one.

- **Timezone switch changes date partitioning for new uploads** → Media uploaded after this change lands in UTC-based folders rather than server-local ones, so recent images may sit in a different date folder than before. Harmless and self-correcting; worth one line in the changelog.

- **Availability caching serves briefly stale data** → Bounded and acceptable for a health indicator. Mitigation: refresh interval set well under the Prometheus scrape interval, and the cold-cache path performs an inline fetch so the first load is never wrong.

- **Moving `makedirs` out of settings may break a developer workflow that relied on it** → The entrypoint covers Docker; for local dev the error surfaces immediately with a clear path. Note it in AGENTS.md.

- **A strict CI gate could block unrelated contributions** → Roll out the workflow non-blocking first (report status without failing the build), confirm the baseline is green, then flip to required. Avoids a surprise hard-fail on the first PR from an outside contributor.

- **Coverage gate may fail immediately if actual coverage is below 80%** → Measure before enforcing. If actual coverage is materially lower, set the threshold at the current value with a documented ratchet rather than shipping a red pipeline.

## Migration Plan

1. **Preflight (read-only).** Query for `UploadedImage` rows whose `api_response.detections` is not a JSON array. Record the count. Also measure current test coverage and record it. These two numbers gate steps 4 and 9 respectively.

2. **Make the suite green** — relocate scratch scripts to `scripts/`, confirm `manage.py test` exits `OK`. No behavior change; safe to ship alone.

3. **Add lint and CI (non-blocking)** — commit `ruff` config, run `ruff format` as its own commit, add the CI workflow with a non-required status check.

4. **Flip CI to enforcing** once lint and tests are green on a full run.

5. **Independent fixes** — client caching, batch fault tolerance, pagination validation, JSON extraction, settings side effects, `METRICS_FILE_PATH`, deprecated setting removal, compose file cleanup. Each is small and separately revertable. Group them by module to keep review diffs readable.

6. **Schema simplification** — the legacy branch removal. Gated on the preflight query. Ship as its own commit so it can be reverted without affecting anything else.

7. **Dependency upgrade** — separate commit, verified against the live endpoint, rollback is a one-line revert to `1.30.1`.

8. **Availability caching** — ship last; it is the only change with a runtime timing dependency.

**Rollback:** every step is a normal commit with no schema migrations, no stored-format rewrites, and no API contract changes. Rollback is a revert. The one non-revertible-by-revert item is the timezone switch, which is additive for new records only.