## Context

PR #54 merged the local ONNX pipeline and made it the default backend. The observability stack was not part of that change and still describes the world in which the VLM is the only inference path.

The current state, concretely:

- `api_health_check` calls `get_qwen_client().health_check()` on every request and folds the result into `api_healthy`, which drives both the HTTP status code and `lpr_api_health_status`.
- `lpr_api_health_status` is the sole input to the availability series (`avg_over_time(lpr_api_health_status[5m])` in `services/availability.py`). Nothing else feeds that graph.
- `refresh_availability` runs on a 60-second APScheduler job and queries Prometheus unconditionally, which in production means an outbound request to the configured VLM endpoint every 15 seconds from the health check plus one Prometheus query per interval.
- Under `PIPELINE_BACKEND=local`, none of these touch the code path that serves user requests.

The production deploy that followed #54 returned HTTP 500 on every upload from a defect in `check_image_dimensions`, while health, availability, and canary all reported healthy. The failure was invisible to every signal available to an operator.

There is a second, separate contributor. CI provisions no model artifacts, and `model/` is gitignored, so every test guarded by `skipUnless(has_model, ...)` skips. The CI run reports 28 skipped against 4 locally. The tests that exercise real ONNX inference and real session construction — the ones that would have caught a stage-contract or session-lifetime regression — never execute in CI.

A third thread, from the same root cause: `lpr-app` in compose still hard-requires `.env.llamacpp` and defaults `QWEN_BASE_URL` to `http://llamacpp-cpu:8000/v1`, a service that is not running under the default profile. The config still asserts a dependency the default path does not have.

## Goals / Non-Goals

**Goals:**

- No signal an operator can reach reports on the VLM path while the local backend serves requests. Either the signal describes the active backend, or it says it does not apply.
- Stop the periodic outbound VLM probe under the local backend, rather than merely ignoring its result.
- Make real-inference tests run in CI, and make the local and CI test counts comparable so a skip cannot hide a regression.
- Fix the live production defect and close the coverage gap that let it ship, in the same change, because the bug and the blind spot have one cause: nobody verified the decode path end to end.

**Non-Goals:**

- Redefining availability for the local backend. What fraction of time is a local pipeline "available" — process up, artifacts intact, meeting its latency budget, or producing correct text? These are different questions and only the first two are answerable from telemetry today.
- Repointing the graph at real pipeline signals. Follow-up, once a definition exists.
- Alerting on accuracy drift. The corpus carries no transcription labels, so there is no ground truth to drift from. This is the most important gap and also the least solvable right now.
- Deciding whether GPU-to-CPU provider fallback should be a warning or a hard failure. Separate change; it changes runtime behaviour rather than observability.
- The compose/env decoupling. Noted from the same root cause, but it is configuration surface, not observability, and bundling it would blur both changes.

## Decisions

### Availability returns not-applicable rather than a substituted series

Under the local backend, `/api/v1/availability/` returns an explicit not-applicable marker and the SPA renders an explanatory state.

The alternative considered was repointing the graph at pipeline success rate or latency-budget compliance. That would produce a real graph, and it is the right end state — but "available" is undefined, and shipping a graph before the definition is settled means the first definition chosen becomes the one operators trust. A missing graph is honest; a wrong graph is worse than a missing one, because it answers a question the reader does not know is unanswered.

Not-applicable is also forward-compatible: when a definition lands, the same endpoint gains a third state rather than changing shape.

### Health probes the active backend, not always the VLM

`api_health_check` branches on `settings.PIPELINE_BACKEND`. Under `llm`, behaviour is unchanged. Under `local`, it verifies artifact presence and integrity rather than making a network call, and reports `backend: "local"`.

This is BREAKING for consumers reading `api_healthy`. Retaining the field under `local` by reporting artifact state as though it were API health would be worse — a field named `api_healthy` that means "artifacts present" invites exactly the misreading this change exists to prevent. Removing it forces consumers to branch.

The local check is deliberately cheap and synchronous: stat the artifacts, verify checksums only if a cached verification is absent. Full verification on every health request would put a 37MB hash computation on the request path.

### Artifact integrity is a first-class health signal

First-boot download already verifies checksums against the pinned manifest. That verification is not repeated at runtime, so a corrupted artifact introduced after boot — a bad volume write, a truncated file, a tampered volume — is undetectable.

Health gains an artifact-integrity check whose result is cached for a short interval. This is the signal that would have caught the production deploy's class of failure, and it is the one property of the local backend that is cheap to check and decisive when it fails.

### The scheduled refresh skips its query under the local backend

`refresh_availability` returns early rather than querying Prometheus and discarding the result. Skipping the query and ignoring its result are behaviourally equivalent from the caller's perspective, but only the former stops the periodic work. This is a small change that avoids leaving a pointless query running on a timer forever.

### CI fetches artifacts, and test counts become comparable

The test job runs `fetch_artifacts.py` before `manage.py test`, exactly as the Docker entrypoint does. This reuses one code path rather than adding a second, and it means CI verifies the same download-and-verify logic production uses.

Followed by an explicit assertion that the real-model tests did not skip. Without it, a future change that breaks the fetch — a moved revision, a renamed artifact — reintroduces silent skips and CI goes green while testing nothing. The count of skipped tests is the assertion; it fails the build if the real-model tests are not running.

Artifact download adds roughly 37MB and a network dependency to the test job. A fetch failure must fail loudly rather than fall back to skipping, for the same reason.

### The validator accepts both file-like objects and open images

`check_image_dimensions` is called from three places. Two hold a file-like object and must not decode; one holds an already-open `PIL.Image` and must not re-open it, because a PIL image has no `read` and `Image.open` raises `AttributeError`.

The fix is an `isinstance` branch: an open image already has `.size` from its header at zero cost, so this path is no more expensive than the file-like one. Re-opening to obtain the same information would be both slower and incorrect.

The more important half is the regression test. The original guard was correct and thoroughly tested — ten tests covering the accept/reject boundary, the disable path, and the no-decode property. None of them exercised the call site added in the same commit. That is why a green suite shipped a broken upload path, and the new test targets the seam rather than the function.

### Compose decoupling is deliberately excluded

`lpr-app` requiring `.env.llamacpp` and defaulting `QWEN_BASE_URL` to the llamacpp service is the same root cause — config still asserting the VLM path. It is excluded because it is a different class of change: it alters what operators must configure, not what operators can observe. Bundling it would make both changes harder to review and impossible to roll back independently.

## Risks / Trade-offs

[Health endpoint response shape changes under the local backend, breaking external consumers of `api_healthy`] → Announced as BREAKING in the proposal. The field is removed rather than repurposed, so a consumer that reads it fails loudly under `local` instead of silently receiving a different meaning. Migration documented in the spec.

[CI gains a network dependency on huggingface.co, and a transient failure turns into a red build] → Accepted deliberately. A silent skip is the failure mode being fixed; a noisy failure is correct. Retries belong on the fetch, not on the test job.

[Skipped-test assertion is brittle — unrelated future skips trip it] → Assert on the specific real-model test classes rather than a global skip count, so unrelated skips do not break CI.

[Not-applicable availability is less useful than a graph, and operators may find a missing graph confusing] → The SPA states which backend is active and why the graph is absent, rather than rendering an empty panel. Repointing the graph remains a tracked follow-up.

[Checksum verification on the health path is itself a DoS vector if triggered per request] → Cached with a short TTL and cheap on the fast path (presence check); full verification only on cache miss.

[Prod stays broken until this change ships] → Stated plainly and accepted as the user's decision. The defect is a two-line fix; bundling it behind a full change cycle is the tradeoff chosen.

## Migration Plan

1. Land the `check_image_dimensions` fix and its regression test first within the change, so prod recovers as early as possible.
2. Health branches on backend; availability returns not-applicable; SPA adapts.
3. CI gains the artifact-fetch step and the skip assertion.
4. Deploy. Expect `/api/v1/health/` to stop reporting `api_healthy` and the availability graph to disappear. Both are intended, and both should be confirmed as such rather than treated as a regression.

Rollback: revert the change. Because artifact downloads happen at boot and are independent of observability, a rollback does not disturb the model files or require re-fetching them.

## Open Questions

- What is the definition of availability for the local backend — process up, artifacts intact, latency budget met, or output correct? The first two are answerable from telemetry. The fourth is not, at all. This determines what a repointed graph can honestly show.
- Should provider fallback from GPU to CPU remain a warning? Currently it is, so a broken accelerator produces no alert and only a slower service. Changing it alters runtime behaviour and is out of scope here.
- Is there a defensible accuracy signal at all? A held-out labelled set would create one. None exists, and building it is a larger project than this change.