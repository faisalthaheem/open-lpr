# Tasks

## 1. Production defect: dimension validator accepts open images

Shipped first. Prod is currently returning HTTP 500 on every upload and this is the fix.

- [x] 1.1 In `lpr_app/utils/validators.py`, make `check_image_dimensions` branch on `isinstance(image_file, Image.Image)` and read `.size` directly from an open image instead of calling `Image.open` on it. An open image is not file-like and has no `read`, which is the `AttributeError` seen in production.
- [x] 1.2 Add a regression test passing an already-open `PIL.Image` to `check_image_dimensions` and asserting it returns a verdict. The existing suite passes a file-like object everywhere, which is why this shipped broken.
- [x] 1.3 Add a test covering the decode call site itself -- open a real image file, then pass the open image to the validator -- rather than testing the validator in isolation again.
- [x] 1.4 Assert both input forms agree: the same image yields the same verdict as a file-like object and as an open image.
- [x] 1.5 Run the full suite and confirm `test_image_decompression_bomb` and the decode-path tests pass together.

## 2. Artifact integrity as a health signal

- [x] 2.1 Add a cached artifact-integrity check in `lpr_app/pipeline/` returning whether all configured artifacts are present and match the manifest checksums at the pinned revision.
- [x] 2.2 Reuse `lpr_app/pipeline/fetch_artifacts.py` for checksum computation rather than duplicating hashing logic. It already fetches the manifest and computes checksums.
- [x] 2.3 Cache the integrity result with a short TTL so a health request is a presence check on the fast path and full verification happens only on cache miss. Hashing 37MB per health request is not acceptable.
- [x] 2.4 Test: healthy artifacts report healthy; a corrupted artifact is detected; repeated calls within the TTL do not re-verify.

## 3. Health endpoint reports the active backend

- [ ] 3.1 Branch `api_health_check` on `settings.PIPELINE_BACKEND`. Under `llm`, behaviour is unchanged.
- [ ] 3.2 Under `local`, remove the `get_qwen_client().health_check()` call and the `api_healthy` field from the response. Report `backend` and artifact health instead.
- [ ] 3.3 Include `backend` in the response under both backends so a consumer can always tell which one is active.
- [ ] 3.4 Keep the database check common to both backends, and keep status 503 when the database is unreachable regardless of backend.
- [ ] 3.5 Test: under `local`, no VLM client is constructed and no VLM request is made; `api_healthy` is absent; `backend` is `local`. Under `llm`, behaviour and response shape are unchanged.
- [ ] 3.6 Confirm with the metrics helper that `update_api_health_status` is not called with a VLM-derived value under `local`, since it is the input to the availability series.

## 4. Availability is not applicable under the local backend

- [ ] 4.1 Add a not-applicable response from `get_availability_points` or the view when `PIPELINE_BACKEND` is `local`, before any cache read. A cached LLM-derived series must not be served as if it described local inference.
- [ ] 4.2 Short-circuit `refresh_availability` under `local` so the scheduled job performs no Prometheus query and does not populate the cache.
- [ ] 4.3 Decide and record the response shape for not-applicable. It must be distinguishable from both an empty series and an error, since an empty array currently means "no data yet" and a 503 means "upstream failed".
- [ ] 4.4 Test: under `local`, the endpoint returns not-applicable and does not contact Prometheus; a series cached under `llm` is not served under `local`; `llm` behaviour is unchanged.
- [ ] 4.5 Test: `refresh_availability` under `local` performs no upstream query.

## 5. SPA renders the not-applicable state

- [ ] 5.1 Handle the not-applicable response in the availability view and render an explanatory state naming the active backend, rather than an empty chart frame.
- [ ] 5.2 Confirm the availability graph still renders normally when a series is present, so the `llm` path is unaffected.
- [ ] 5.3 Add or update the Storybook story for the not-applicable state.
- [ ] 5.4 Run `tsc --noEmit` and `eslint` on the changed files.

## 6. CI provisions artifacts

- [ ] 6.1 Add a fetch-and-verify step to the `test` job in `.github/workflows/test.yml`, before the test run, invoking `lpr_app/pipeline/fetch_artifacts.py`. Reuse the container's path rather than adding a second implementation.
- [ ] 6.2 Add an explicit assertion that the real-inference tests executed rather than skipped. Assert on the specific test classes, not a global skip count, so unrelated skips do not break CI.
- [ ] 6.3 Ensure a fetch failure fails the job rather than degrading into skips. No `continue-on-error`.
- [ ] 6.4 Confirm CI is green and that the skip count dropped from 28 to approximately the local count of 4.
- [ ] 6.5 Verify locally that the assertion would fail if artifacts were absent, so it is known to be load-bearing rather than trivially passing.

## 7. Documentation

- [ ] 7.1 Document that health and availability are backend-conditional, including the `api_healthy` removal, in README and AGENTS.md.
- [ ] 7.2 Note in AGENTS.md that compose still hard-requires `.env.llamacpp` and defaults `QWEN_BASE_URL` to the llamacpp service, and that decoupling it is a deliberate follow-up rather than an oversight.
- [ ] 7.3 Record the production incident and its cause in the changelog: the observability blind spot shipped alongside the working guard, which is why a one-line defect reached production undetected.

## 8. Verification before merge

- [ ] 8.1 Full suite passes, lint and format clean.
- [ ] 8.2 Confirm no test asserts on the removed `api_healthy` field under the local backend; update any that do.
- [ ] 8.3 Confirm the health endpoint makes no outbound request under `local`, verified by a test that would fail if a VLM client were constructed.
- [ ] 8.4 Re-verify the artifact fetch against the pinned revision end to end, as was done for PR #54.