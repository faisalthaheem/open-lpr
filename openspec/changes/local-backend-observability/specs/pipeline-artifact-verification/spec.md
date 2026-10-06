# pipeline-artifact-verification Specification

## Purpose

Model artifacts are fetched and checksum-verified by one code path shared by the container entrypoint and CI, and integrity is re-checked at runtime so corruption introduced after boot is detectable.

## ADDED Requirements

### Requirement: A single fetch path serves containers and CI

Artifact acquisition SHALL be performed by one implementation used by both the container entrypoint and the CI test job.

#### Scenario: CI uses the same fetcher as the entrypoint
- **WHEN** the CI test job provisions model artifacts
- **THEN** it SHALL invoke the same artifact fetch implementation the container entrypoint uses

#### Scenario: Fetch failure fails loudly rather than degrading
- **WHEN** artifact acquisition fails in CI
- **THEN** the test job SHALL fail and SHALL NOT silently proceed with artifacts absent

### Requirement: Artifacts are verified against a pinned revision

The fetch implementation SHALL verify every downloaded artifact against a checksum published at a pinned revision.

#### Scenario: Checksum mismatch is rejected
- **WHEN** a downloaded artifact does not match the checksum published at the pinned revision
- **THEN** the artifact SHALL be deleted and the fetch SHALL fail

#### Scenario: Already-correct artifacts are not re-fetched
- **WHEN** all artifacts are present and already match their published checksums
- **THEN** the fetch SHALL report zero downloads

#### Scenario: An existing artifact that fails verification is replaced
- **WHEN** an artifact is present but does not match its published checksum
- **THEN** the fetch SHALL re-download it

#### Scenario: The revision is pinned rather than a moving branch
- **WHEN** the fetch resolves artifact URLs
- **THEN** it SHALL resolve them at a pinned revision so a given deployment version yields the same bytes on every redeploy

### Requirement: Download interruption cannot yield a usable artifact

The fetch implementation SHALL NOT leave a partially written artifact in a state that a later run would treat as present.

#### Scenario: Interrupted transfer leaves no artifact
- **WHEN** a transfer is interrupted partway through
- **THEN** no artifact file SHALL exist at the target path and no partial file SHALL remain

#### Scenario: Download is published atomically
- **WHEN** a transfer completes successfully
- **THEN** the artifact SHALL appear at the target path atomically

### Requirement: Downloaded artifacts are world-readable

The fetch implementation SHALL publish artifacts with permissions that allow the runtime user to read them regardless of which user performed the download.

#### Scenario: Artifacts are readable after a privilege drop
- **WHEN** artifacts are downloaded as one user and the application subsequently runs as a different user
- **THEN** the artifacts SHALL remain readable by the runtime user