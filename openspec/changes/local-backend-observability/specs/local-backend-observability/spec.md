# local-backend-observability Specification

## Purpose

Health and availability reporting describe the inference backend that is actually serving requests, so no operator-facing signal can report on the vision-language-model path while the local ONNX pipeline is handling uploads.

## ADDED Requirements

### Requirement: Health reports the active backend

The health endpoint SHALL report which inference backend is active, and SHALL describe that backend's health rather than always probing the external VLM endpoint.

#### Scenario: Health under the LLM backend probes the API
- **WHEN** the health endpoint is requested and `PIPELINE_BACKEND` is `llm`
- **THEN** the endpoint SHALL probe the configured VLM endpoint and report `api_healthy` alongside `backend` set to `llm`

#### Scenario: Health under the local backend makes no VLM call
- **WHEN** the health endpoint is requested and `PIPELINE_BACKEND` is `local`
- **THEN** the endpoint SHALL NOT contact the VLM endpoint and SHALL report `backend` set to `local`

#### Scenario: Local health depends on artifacts rather than an API call
- **WHEN** the health endpoint is requested and `PIPELINE_BACKEND` is `local`
- **THEN** the response SHALL include an artifact health field reflecting the presence and integrity of the model artifacts

#### Scenario: Response identifies the backend unconditionally
- **WHEN** the health endpoint is requested under either backend
- **THEN** the response SHALL include a `backend` field naming the active backend

#### Scenario: Database failure is reported under both backends
- **WHEN** the health endpoint is requested and the database is unreachable
- **THEN** the endpoint SHALL return status 503 regardless of the active backend

### Requirement: Availability is not applicable under the local backend

The availability endpoint SHALL NOT return a vision-language-model-derived series while the local backend is active, and SHALL instead signal that the series does not apply.

#### Scenario: Availability reports not-applicable under local
- **WHEN** the availability endpoint is requested and `PIPELINE_BACKEND` is `local`
- **THEN** the endpoint SHALL return an explicit not-applicable marker and SHALL NOT return a series derived from `lpr_api_health_status`

#### Scenario: Availability serves the series under the LLM backend
- **WHEN** the availability endpoint is requested and `PIPELINE_BACKEND` is `llm`
- **THEN** the endpoint SHALL serve the cached series exactly as before

#### Scenario: A stale local-backend series is never served
- **WHEN** a series was cached while the LLM backend was active and the backend is later switched to `local`
- **THEN** the endpoint SHALL NOT serve that cached series as if it described local inference

### Requirement: Scheduled availability refresh skips its query under the local backend

The background availability refresh SHALL NOT query the metrics backend while the local backend is active.

#### Scenario: Refresh does no upstream work under local
- **WHEN** the scheduled availability refresh runs and `PIPELINE_BACKEND` is `local`
- **THEN** it SHALL return without querying the metrics backend and without populating the cache

#### Scenario: Refresh behaves as before under the LLM backend
- **WHEN** the scheduled availability refresh runs and `PIPELINE_BACKEND` is `llm`
- **THEN** it SHALL query the metrics backend and populate the cache as before

### Requirement: The frontend renders a not-applicable availability state

The SPA SHALL render an explanatory state, naming the active backend, in place of the availability graph when the availability endpoint reports not-applicable.

#### Scenario: Graph is replaced by an explanation
- **WHEN** the availability response indicates not-applicable
- **THEN** the SPA SHALL render an explanatory state instead of a graph, and SHALL NOT render an empty chart frame

#### Scenario: Explanation names the active backend
- **WHEN** the not-applicable state is rendered
- **THEN** the state SHALL indicate which backend is active and that the graph is unavailable for it

#### Scenario: Graph still renders when a series exists
- **WHEN** the availability response contains a series
- **THEN** the SPA SHALL render the graph as before

### Requirement: Local backend health detects corrupted artifacts

The health endpoint SHALL detect model artifacts that fail checksum verification after first-boot download, rather than relying solely on the download-time check.

#### Scenario: Corrupted artifact is reported unhealthy
- **WHEN** an artifact fails checksum verification and `PIPELINE_BACKEND` is `local`
- **THEN** the health endpoint SHALL report the artifact as unhealthy

#### Scenario: Healthy artifacts report healthy
- **WHEN** all artifacts are present and match their published checksums
- **THEN** the health endpoint SHALL report the artifact health as healthy

#### Scenario: Verification cost is bounded
- **WHEN** the health endpoint is called repeatedly in quick succession
- **THEN** checksum verification SHALL be cached and SHALL NOT recompute on every request

### Requirement: Image dimension validation accepts open images and file-like objects

The image dimension validator SHALL accept either a file-like object or an already-open image, and SHALL NOT re-open an already-open image.

#### Scenario: File-like object is validated from its header
- **WHEN** the validator receives a file-like object
- **THEN** it SHALL read the declared dimensions without decompressing pixel data

#### Scenario: Already-open image is validated from its own size
- **WHEN** the validator receives an already-open image
- **THEN** it SHALL read the dimensions from that image without attempting to open it again

#### Scenario: Oversized dimensions are rejected on either input form
- **WHEN** either a file-like object or an already-open image declares more pixels than the configured maximum
- **THEN** the validator SHALL return a rejection naming the dimensions and the limit

#### Scenario: The decode path is covered by regression test
- **WHEN** the dimension check is invoked from the image processing decode path with an already-open image
- **THEN** it SHALL return a verdict rather than raising