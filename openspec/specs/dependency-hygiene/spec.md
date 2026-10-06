# dependency-hygiene Specification

## Purpose
Covers exact version pinning of runtime dependencies, keeping the OpenAI SDK current, keeping development tooling out of production images, and preserving reproducible builds.

## Requirements

### Requirement: Consistent dependency version pinning
Every entry in the runtime dependency manifest SHALL specify an exact version, with no open-ended ranges.

#### Scenario: No version ranges
- **WHEN** the runtime dependency manifest is inspected
- **THEN** no entry SHALL specify an open-ended lower or upper bound

#### Scenario: Previously ranged dependencies are pinned
- **WHEN** dependencies that previously used ranges are inspected
- **THEN** each SHALL specify the exact version currently deployed and verified

### Requirement: Current AI SDK version
The OpenAI SDK dependency SHALL be on a current release, and a compatibility workaround that was required only to support the previous pinned version SHALL be removed once the upgrade is verified against a live inference endpoint.

#### Scenario: Workaround removal is gated on verification
- **WHEN** the SDK upgrade is applied
- **THEN** removal of the explicit HTTP client compatibility workaround SHALL occur only after a real inference request against the configured endpoint succeeds

#### Scenario: Upgrade can be deferred independently
- **WHEN** the upgrade cannot be verified in a given release window
- **THEN** the previous pinned version and its compatibility workaround SHALL both be retained, and no other part of the change SHALL be blocked

#### Scenario: No unresolved compatibility errors
- **WHEN** an inference request is made after the upgrade
- **THEN** no HTTP client compatibility errors SHALL be raised

### Requirement: Development tooling is not shipped to production
Tooling used only for linting, formatting, or local verification SHALL NOT be included in the runtime dependency manifest or the production image.

#### Scenario: Runtime manifest contains runtime dependencies only
- **WHEN** the runtime dependency manifest is installed
- **THEN** it SHALL contain only dependencies required at runtime

#### Scenario: Production image size and contents
- **WHEN** the production image is built
- **THEN** no development-only tooling SHALL be present in the installed packages

### Requirement: Build remains reproducible
Pinned dependencies SHALL continue to install successfully in the CI and container builds.

#### Scenario: CI install succeeds
- **WHEN** the CI workflow installs pinned dependencies
- **THEN** the install SHALL complete without resolution conflicts

#### Scenario: Container build succeeds
- **WHEN** the multi-architecture image build installs pinned dependencies
- **THEN** the build SHALL complete for every target architecture
