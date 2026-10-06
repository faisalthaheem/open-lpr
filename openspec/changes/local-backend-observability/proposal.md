## Why

`PIPELINE_BACKEND` now defaults to `local`, but the observability stack still measures the vision-language-model path exclusively. The availability graph plots `lpr_api_health_status`, which is set solely from `QwenVLClient.health_check()`, so it reports the health of a service that is no longer in the request path. Under the default backend the system can be entirely non-functional while every dashboard reads green.

This is not hypothetical. The local backend shipped in PR #54 and the first production deploy returned HTTP 500 on every single upload — while the health endpoint, the availability graph, and the canary all reported success. A pre-existing bug in a dimension guard was invisible to every signal an operator would check, because none of them touched local inference.

Two consequences follow. Operators are told the system is healthy when it is not, and the real failure modes of the local backend — artifact integrity, provider fallback, accuracy drift — have no instrumentation at all. Separately, CI skips every test that exercises real inference, so the pipeline's most valuable tests never run.

## What Changes

- **BREAKING**: Under `PIPELINE_BACKEND=local`, `/api/v1/health/` stops probing the external VLM endpoint and no longer reports `api_healthy`. The response schema gains an explicit backend indicator; consumers reading `api_healthy` must branch on backend.
- Under `PIPELINE_BACKEND=local`, `/api/v1/availability/` returns a not-applicable marker rather than a VLM-derived series. The SPA renders an explanatory state instead of a graph, rather than plotting a trend that was never measured.
- The background availability refresh job skips its Prometheus query entirely under the local backend, removing the periodic outbound request.
- CI fetches the pinned model artifacts before running tests, so tests exercising real inference execute instead of skipping. Test counts become comparable between local and CI environments.
- Fixes the production-breaking bug in `check_image_dimensions`: it accepts an already-open `PIL.Image` in addition to a file-like object. Callers on the decode path already hold one, and re-opening it raised `AttributeError` because a PIL image is not file-like.
- Adds regression coverage for that call site. The guard itself was correct and tested; the seam wiring it into the decode path was not, which is how a one-line defect reached production with a green test suite.

Explicitly out of scope: redefining what "available" means for the local backend, repointing the graph at real pipeline signals, and alerting on accuracy drift. Those need an agreed definition before any graph is honest, and are recorded as follow-ups.

## Capabilities

### New Capabilities
- `local-backend-observability`: Health, availability, and probe behaviour conditioned on which inference backend is active, including the not-applicable contract for the availability graph and the artifact-integrity signal.
- `pipeline-artifact-verification`: Runtime verification that the deployed model artifacts match their published checksums, independent of first-boot download.

### Modified Capabilities
- `availability-caching`: The refresh job and endpoint become backend-aware — under the local backend the series is not applicable, and the endpoint must not return a stale VLM-derived series as if it described local inference.
- `ci-quality-gates`: CI must provision model artifacts so that real-inference tests run rather than skip, making local and CI test counts comparable.
- `settings-configuration`: Documents `PIPELINE_MODEL_DOWNLOAD`, `PIPELINE_MODEL_REVISION`, `PIPELINE_MODEL_REPO`, and `UPLOAD_IMAGE_MAX_PIXELS` as supported configuration, and records that `check_image_dimensions` must accept both file-like objects and open PIL images.

## Impact

- `lpr_app/views/api_views.py` — `api_health_check` branches on backend; `api_availability` returns a not-applicable response.
- `lpr_app/services/availability.py` — `refresh_availability` and `fetch_availability_points` short-circuit under the local backend.
- `lpr_app/utils/validators.py` — `check_image_dimensions` accepts an open `PIL.Image`. **This is the live production defect.**
- `lpr_app/services/image_processing_service.py` — no change needed once the validator accepts both forms; the existing call site becomes correct.
- `single-page-ui/` — availability view renders a not-applicable state; health display adapts to the response schema change.
- `.github/workflows/test.yml` — artifact-fetch step before the test job.
- Behaviour change for any external consumer of `/api/v1/health/` that reads `api_healthy`. This is a public API field removal under the default backend.