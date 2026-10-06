# ci-quality-gates Specification

## ADDED Requirements

### Requirement: CI provisions model artifacts so real-inference tests run
CI SHALL provision the model artifacts required by tests that exercise real inference, so those tests execute rather than skip. A provisioning failure SHALL fail the job rather than degrade into skipped tests.

#### Scenario: Artifact provisioning precedes the test run
- **WHEN** the CI test job runs
- **THEN** it SHALL fetch and verify the model artifacts before invoking the test runner

#### Scenario: Real-inference tests execute rather than skip
- **WHEN** the CI test job completes successfully
- **THEN** the tests exercising real inference SHALL have executed, and their skip guard SHALL NOT have triggered

#### Scenario: Provisioning failure fails the job
- **WHEN** artifact provisioning fails in CI
- **THEN** the test job SHALL fail with a provisioning error, and SHALL NOT proceed with the artifacts absent

#### Scenario: Silent skip regression is detected
- **WHEN** a change causes the artifact provisioning or the real-inference test guards to stop working
- **THEN** an explicit assertion on the executed real-inference tests SHALL fail the job, so a skip cannot be mistaken for a pass

#### Scenario: Test counts are comparable across environments
- **WHEN** the same commit is tested locally with artifacts present and in CI
- **THEN** the real-inference tests SHALL run in both environments, so their results are comparable

## MODIFIED Requirements

### Requirement: Continuous integration quality gates
CI SHALL run lint, tests, and a coverage check on pushes and pull requests, SHALL report pass or fail status for each independently of image publishing, and SHALL provision the artifacts those tests require.

#### Scenario: Failing test blocks the pipeline
- **WHEN** a pull request introduces a failing test
- **THEN** the CI test job SHALL fail and the failure SHALL be visible on the pull request

#### Scenario: Lint failure is reported separately from test failure
- **WHEN** a pull request introduces a lint violation but no test failure
- **THEN** the lint job SHALL fail and the test job SHALL pass, so the cause is identifiable

#### Scenario: Coverage is measured
- **WHEN** the test job completes
- **THEN** coverage SHALL be measured for the `lpr_app` package and reported in the job output

#### Scenario: Coverage regression is caught
- **WHEN** measured coverage falls below the configured threshold
- **THEN** the coverage job SHALL fail

#### Scenario: Required artifacts are provisioned rather than skipped
- **WHEN** the test job runs
- **THEN** the artifacts required by real-inference tests SHALL be fetched and verified as a job step, so their absence is a job failure and not a silent skip