## ADDED Requirements

### Requirement: Green test suite on default discovery
`python manage.py test` SHALL complete without test collection errors and SHALL report a successful result.

#### Scenario: Default discovery runs cleanly
- **WHEN** `python manage.py test` is executed from the project root
- **THEN** the runner SHALL import only test modules under the Django app test packages, and SHALL NOT report `unittest.loader._FailedTest` collection errors

#### Scenario: Manual integration harnesses are not collected
- **WHEN** the repository contains manual integration scripts under `scripts/`
- **THEN** the default test discovery SHALL NOT attempt to import those scripts as test modules

### Requirement: Automated lint and format tooling
The project SHALL provide a committed lint and format configuration, and the tooling SHALL be runnable locally without additional setup.

#### Scenario: Lint runs clean
- **WHEN** the lint command is executed against the repository
- **THEN** it SHALL report no violations across the configured rule set

#### Scenario: Format command produces stable output
- **WHEN** the format command is executed twice in succession
- **THEN** the second execution SHALL report no files as changed

#### Scenario: Development tooling is separated from runtime dependencies
- **WHEN** the runtime dependency manifest is installed into the production image
- **THEN** it SHALL NOT include the lint and format tooling

### Requirement: Continuous integration quality gates
CI SHALL run lint, tests, and a coverage check on pushes and pull requests, and SHALL report pass or fail status for each independently of image publishing.

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

### Requirement: Tooling baseline documentation
Project documentation SHALL state the commands for linting, formatting, and running tests.

#### Scenario: Contributor guidance is current
- **WHEN** a contributor reads the project agent documentation
- **THEN** it SHALL list the lint, format, and test commands, and SHALL note that importing settings no longer creates directories