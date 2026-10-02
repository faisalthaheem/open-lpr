## ADDED Requirements

### Requirement: Configurable per-stage and end-to-end latency budgets
The system SHALL record a measured duration for each executed pipeline stage and for the pipeline as a whole, and SHALL compare each against a configurable budget.

#### Scenario: Per-stage duration is measured
- **WHEN** a stage completes execution
- **THEN** the elapsed time for that stage SHALL be recorded, whether it succeeded, was skipped, or failed

#### Scenario: End-to-end duration is measured
- **WHEN** the pipeline completes for an image
- **THEN** the total elapsed time across all executed stages SHALL be recorded

#### Scenario: Budget is configurable
- **WHEN** a latency budget is configured for a stage or for the pipeline
- **THEN** the recorded duration SHALL be compared against that budget, and the comparison result SHALL be available to callers and to monitoring

#### Scenario: Budget default reflects the sub-500ms target
- **WHEN** no explicit budget is configured
- **THEN** the end-to-end pipeline budget SHALL default to 0.5 seconds

### Requirement: Latency is exported as a metric
Stage and pipeline durations SHALL be exported through the existing Prometheus metrics surface with a stage label, so per-stage cost and regressions are observable in production.

#### Scenario: Per-stage duration is exported
- **WHEN** a stage completes
- **THEN** a histogram observation with a label identifying the stage SHALL be recorded on the existing application metrics registry

#### Scenario: Stage label identifies the stage
- **WHEN** multiple distinct stages have executed
- **THEN** their observations SHALL be distinguishable by label, so per-stage cost can be read separately

#### Scenario: Skipped and failed stages are distinguishable
- **WHEN** a stage is skipped or fails
- **THEN** its observation SHALL be recorded with a label distinguishing that outcome from a successful execution

### Requirement: Latency budget is enforced by an automated check
The system SHALL provide an automated check that measures pipeline latency over the annotated corpus and fails when the end-to-end budget is exceeded, so a regression is caught before deployment rather than observed after.

#### Scenario: Benchmark reports a result
- **WHEN** the benchmark tooling is run against a corpus
- **THEN** it SHALL report per-stage and end-to-end durations, including the count of images measured

#### Scenario: Benchmark exits non-zero when the budget is exceeded
- **WHEN** measured end-to-end latency exceeds the configured budget
- **THEN** the benchmark SHALL exit with a non-zero status so the check fails

#### Scenario: Measurement excludes first-run model loading
- **WHEN** benchmark timings are collected
- **THEN** the first execution's one-time model loading SHALL be excluded from per-stage latency figures, so the reported durations reflect steady-state cost

### Requirement: Regression in measured latency is visible
A change that increases measured latency beyond the budget SHALL be detectable from exported metrics alone, without requiring a code review to notice.

#### Scenario: Slow stage appears in metrics
- **WHEN** one stage's latency grows substantially while others are unchanged
- **THEN** the exported per-stage histogram SHALL show the regression attributable to that stage

#### Scenario: Existing end-to-end metric remains meaningful
- **WHEN** the local pipeline backend replaces the LLM backend
- **THEN** the existing overall image processing duration metric SHALL continue to be recorded, so comparisons across backends remain possible on a single metric