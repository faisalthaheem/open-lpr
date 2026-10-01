## 1. Preflight (blocking, read-only)

- [x] 1.1 Query `UploadedImage` rows whose stored `api_response` has a `detections` value that is not a JSON array; record the count. This gates task group 7.
- [x] 1.2 Run `coverage run --source='lpr_app' manage.py test` and record current coverage percentage. This gates task 3.7.
- [x] 1.3 Grep the repo (README, docs, scripts, compose files) for references to `docker-compose-llamacpp-cpu.yml` and `docker-compose-llamacpp-amd-vulcan.yml`; record every referencing file. This gates task 8.4.
- [x] 1.4 Confirm a reachable inference endpoint is available for the SDK upgrade verification; record whether verification is possible in this release window.

## 2. Make the test suite green

- [x] 2.1 Create `scripts/` and move `test_api.py`, `test_metrics.py`, `test_setup.py`, and `test-llamacpp-integration.py` into it.
- [x] 2.2 Update any documentation referencing the old script paths (AGENTS.md, README.md, API_DOCUMENTATION.md, README-llamacpp.md).
- [x] 2.3 Verify no moved script is imported or referenced at runtime by the app or entrypoint.
- [x] 2.4 Run `python manage.py test` and confirm it reports `OK` with zero collection errors and no reduction in executed test count beyond the four harness scripts.
- [ ] 2.5 Commit as a standalone change.

## 3. Lint tooling and CI

- [x] 3.1 Add a pinned `ruff` version to a development requirements file (not `requirements.txt`).
- [x] 3.2 Add `pyproject.toml` (or `ruff.toml`) with `line-length = 120` and rule set `E`, `F`, `I`, `B`, `UP`.
- [x] 3.3 Run `ruff check` and fix all reported violations in Python source under `lpr_app/`, `lpr_project/`, and `manage.py`.
- [ ] 3.4 Run `ruff format` and commit the resulting mechanical reformat as its own commit, separate from behavioral changes.
- [x] 3.5 Verify `ruff format` reports no changes on a second run.
- [x] 3.6 Add `.github/workflows/test.yml` running lint, tests, and coverage as separate jobs on push and pull request, with coverage measured over `lpr_app`.
- [x] 3.7 Set the coverage threshold based on the value measured in task 1.2 — at the measured baseline if it is below 80%, so the pipeline ships green with a documented ratchet.
- [ ] 3.8 Ship the workflow with a non-required status check, confirm green on a full run, then make it required.
- [x] 3.9 Document the lint, format, and test commands in AGENTS.md, including the note that importing settings no longer creates directories.

## 4. Qwen client lifecycle

- [x] 4.1 Convert `get_qwen_client()` in `lpr_app/services/qwen_client.py` to a `functools.lru_cache(maxsize=1)` accessor returning a single shared instance.
- [x] 4.2 Verify a construction failure (absent `QWEN_API_KEY`) raises on first call and that a subsequent call retries construction rather than returning a cached broken client.
- [x] 4.3 Add tests: repeated accessor calls return the identical object; a missing API key raises; a failed construction is not cached as success.
- [x] 4.4 Audit `lpr_app/tests/` for tests that mutate Qwen settings or rely on constructing differently-configured clients; convert those to build their own client instance rather than mutating the cached one.
- [x] 4.5 Verify the change under gunicorn with multiple workers that each construct their own client.

## 5. Fault-tolerant batch inference

- [x] 5.1 Change `analyze_images_batch` in `lpr_app/services/qwen_client.py` to wrap each per-image call in its own `try`/`except`, appending an empty value on failure and continuing.
- [x] 5.2 Update the return type to a full-length list of optional strings and update the type annotation.
- [x] 5.3 Update the caller in `lpr_app/services/image_processing_service.py` so a partial result is processed per position rather than treated as total failure.
- [x] 5.4 Add tests: one failing item among successes preserves the successes; all items failing returns a full-length list of empties; an empty input batch returns an empty list.
- [x] 5.5 Verified against the local multimodal endpoint: multi-crop batch OCR returns one result per crop in input order (e.g. `قطر 349253` @ 0.98 and `قفر 349253` @ 0.92 from two crops of the same plate).

## 6. API input validation

- [x] 6.1 Add a module-level integer query parameter parsing helper in `lpr_app/views/api_views.py` returning either the parsed value or a `400` `JsonResponse` naming the offending parameter.
- [x] 6.2 Apply the helper to `page` and `page_size` in `api_image_list`, preserving the existing default of 12 and maximum of 100, clamping to a minimum of 1.
- [x] 6.3 Refactor `api_availability` day parsing to use the same helper, preserving its existing default of 3.
- [x] 6.4 Ensure `next` and `previous` pagination URLs carry the validated values actually used.
- [x] 6.5 Add tests: non-integer `page`, non-integer `page_size`, empty and whitespace values, `page` below 1, `page_size` above 100, `page_size` below 1 — all asserting the documented status and no `500`.
- [x] 6.6 Confirm the SPA requires no change, since it already treats a non-200 response as an error.

## 7. Response parsing consolidation

- [x] 7.1 Add a private `_extract_json_text(response_text: str) -> str` helper in `lpr_app/services/qwen_client.py` implementing the four documented cases.
- [x] 7.2 Handle the unterminated-fence case by taking content to end of string rather than computing an end index of `-1`.
- [x] 7.3 Refactor `parse_lpr_response`, `parse_detection_response`, and `parse_ocr_response` to delegate to the helper, keeping their signatures and return shapes unchanged.
- [x] 7.4 Remove `LPR_PROMPT`; verify no code path references it.
- [x] 7.5 Add tests for: JSON-tagged fence, bare fence, no fence, unterminated fence with valid JSON, and unterminated fence with invalid input returning no result.

## 8. Detection schema simplification (gated by task 1.1)

- [x] 8.1 If task 1.1 found non-array `detections` rows, migrate them to the array form; otherwise record that the count was zero and proceed.
- [x] 8.2 Remove the `isinstance(detections, dict)` branches and old `text_value` handling from `get_total_ocr_count` and `get_first_ocr_text` in `lpr_app/models.py`.
- [x] 8.3 Remove the mapping-form branches from `scale_coordinates_in_response` and `scale_detection_coordinates` in `lpr_app/services/qwen_client.py`.
- [x] 8.4 Delete `docker-compose-llamacpp-cpu.yml` and `docker-compose-llamacpp-amd-vulcan.yml`, updating any references found in task 1.3.
- [x] 8.5 Add tests asserting array detections yield correct plate count, OCR count, and first OCR text, and that a non-array value yields zero rather than raising.
- [x] 8.6 Verify image list and image detail endpoints still return correct plate and OCR summaries for existing rows.
- [ ] 8.7 Commit schema removal separately so it can be reverted independently.

## 9. Timezone correctness

- [x] 9.1 Replace naive `datetime.now()` with `django.utils.timezone.now()` in `lpr_app/models.py` (`upload_to_uploads`, `upload_to_processed`) and `lpr_app/services/image_processing_service.py` (`processing_timestamp`).
- [x] 9.2 Replace naive datetime usage in `lpr_app/views/api_views.py` (`api_health_check`, `api_health_light`, `api_availability`) with timezone-aware equivalents.
- [x] 9.3 Verify the `uploads/` and `processed/` prefix and year/month/day segment structure are unchanged.
- [x] 9.4 Run the suite and confirm no naive-datetime runtime warnings are emitted.
- [x] 9.5 Add tests asserting an upload's media path date segments agree with its stored upload timestamp, including when the server local timezone is not UTC.
- [x] 9.6 Note the date-partitioning behavior change for new uploads in the changelog.

## 10. Settings configuration

- [x] 10.1 Remove the `os.makedirs` calls and the static-directory existence check from `lpr_project/settings.py`.
- [x] 10.2 Add directory creation for the database directory, media directory, and static root to `docker-entrypoint.sh` before `migrate` and `collectstatic`.
- [x] 10.3 Confirm the entrypoint remains idempotent across container restarts.
- [x] 10.4 Add `METRICS_FILE_PATH` to `settings.py` via `config()` with a default derived from the configured data directory.
- [x] 10.5 Set the container metrics path explicitly through the environment in the Docker Compose files.
- [x] 10.6 Add `METRICS_FILE_PATH` to `.env.example` and `.env.llamacpp.example` and document it in AGENTS.md.
- [x] 10.7 Remove `SECURE_BROWSER_XSS_FILTER` and the redundant explicit `SECURE_CONTENT_TYPE_NOSNIFF` from `settings.py`.
- [x] 10.8 Verify importing settings in a read-only location succeeds without a permission error, and that the local test run no longer logs `Permission denied: '/app'`.

## 11. Logging hygiene

- [x] 11.1 Remove all `DEBUG:`-prefixed log statements from `lpr_app/views/api_views.py`.
- [x] 11.2 Remove all `DEBUG:`-prefixed log statements from `lpr_app/services/qwen_client.py` and `lpr_app/services/image_processing_service.py`.
- [x] 11.3 Consolidate the exception logging in `api_ocr_upload` so error type, message, and traceback are each captured once rather than duplicated.
- [x] 11.4 Confirm no log statement emits the API key value, only its presence.
- [x] 11.5 Change the `lpr_app` logger level from `DEBUG` to `INFO` in `settings.py`.
- [x] 11.6 Grep for `DEBUG:` to confirm none remain in application source.
- [x] 11.7 Verify a successful OCR request emits a small, bounded number of records independent of pipeline phase count.

## 12. Availability caching

- [x] 12.1 Add an availability refresh function to `lpr_app/scheduler.py` alongside the existing retry job.
- [x] 12.2 Register the refresh on a fixed interval through the existing scheduler integration, with the interval configurable via `config()`.
- [x] 12.3 Refactor `api_availability` to read from the Django cache, performing an inline fetch only on a cold cache.
- [x] 12.4 Preserve the existing response envelope, the empty-data response, and the `503` response when no cached data exists and the metrics backend is unreachable.
- [x] 12.5 Set the refresh interval well below the Prometheus scrape interval.
- [x] 12.6 Add tests: cached hit performs no upstream call; cold cache fetches inline and populates; unreachable upstream with no cache returns `503`; unreachable upstream with stale cache still serves data.
- [x] 12.7 Verify no in-progress deployment ships a refresh interval longer than the scrape interval.

## 13. Dependency hygiene

- [x] 13.1 Pin every `requirements.txt` entry to an exact version, replacing the ranges on `Django` and `APScheduler` with the currently deployed and verified versions.
- [x] 13.2 Upgrade `openai` from `1.30.1` to a current release.
- [x] 13.3 Issue a real inference request against the configured endpoint to verify the upgrade.
- [x] 13.4 If verification fails, revert to `1.30.1` and retain the `DefaultHttpxClient` workaround; do not proceed with removal.
- [x] 13.5 If verification succeeds, remove the explicit `DefaultHttpxClient` workaround and its explanatory comment from `qwen_client.py`.
- [x] 13.6 Confirm `ruff` is not present in `requirements.txt` and is not installed into the production image.
- [x] 13.7 Confirm CI and multi-architecture image builds install the pinned set without conflicts.
- [ ] 13.8 Commit the dependency upgrade separately so it can be reverted independently.

## 14. Verification

- [x] 14.1 Run `python manage.py test` and confirm `OK` with zero collection errors.
- [x] 14.2 Run lint and confirm zero violations; run format twice and confirm no changes on the second run.
- [x] 14.3 Confirm coverage meets or exceeds the threshold set in task 3.7.
- [x] 14.4 Verified end to end against the local multimodal endpoint: upload → detect (1 plate) → OCR (`قطر 349253`) → visualize → save; list 200 with correct plate/OCR summary, detail 200 with 3 processing logs, processed-image download 200 (98 KB), and `?page=abc` returns 400.
- [x] 14.5 Confirm `GET /api/v1/images/` returns `400` for malformed pagination and `200` for valid requests.
- [x] 14.6 Confirm `/api/v1/availability/` responds promptly with the metrics backend stopped.
- [x] 14.7 Review `django.log` output for the duration of a test run and confirm no debug-prefixed records and bounded per-request volume.
- [x] 14.8 Update AGENTS.md with any behavior changes affecting contributors, and update the changelog.

## 15. Deployment

- [ ] 15.1 Push and monitor the CI run to completion.
- [ ] 15.2 Pull the published images on the production host and confirm the canary probe passes.
- [ ] 15.3 Notify the user that images are ready for redeploy.