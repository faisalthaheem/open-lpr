## ADDED Requirements

### Requirement: Pipeline is a declared directed graph
The system SHALL represent the local detection pipeline as a directed graph of stages declared in configuration, in which each node identifies a stage implementation and its model artifact, and each edge declares that one stage consumes a named output field of another.

#### Scenario: Graph is assembled from configuration without code changes
- **WHEN** the pipeline configuration declares a set of nodes and their input bindings
- **THEN** the system SHALL construct and execute exactly those stages in dependency order without requiring any modification to the graph runtime

#### Scenario: Unsatisfied input binding is rejected at construction
- **WHEN** a declared node binds an input to a field that no upstream node in the graph produces
- **THEN** graph construction SHALL fail with an error naming the node and the unsatisfied field, before any stage is loaded or executed

#### Scenario: Cycle in the graph is rejected
- **WHEN** the declared edges form a cycle
- **THEN** graph construction SHALL fail with an error identifying the participating nodes

### Requirement: Stages declare their data contract
Each stage SHALL declare its name, the input fields it requires, and the output fields it produces, and the graph runtime SHALL use those declarations to route data between stages.

#### Scenario: Declared output fields are available to downstream binding
- **WHEN** a stage completes and declares an output field
- **THEN** a downstream stage bound to that field SHALL receive the produced value

#### Scenario: Required input field is absent at execution time
- **WHEN** a stage is executed and a field it declares as required is absent or null
- **THEN** the stage SHALL be skipped and the reason SHALL be recorded, rather than raising an unhandled error

### Requirement: Independent stages execute concurrently
Stages that do not depend on one another, whether declared as siblings or as consuming the same upstream output, SHALL be eligible to execute concurrently rather than only in declaration order.

#### Scenario: Sibling stages over a shared plate crop
- **WHEN** two stages both bind their input to the same rectified plate crop
- **THEN** the system SHALL be able to execute them concurrently, so end-to-end latency reflects the slower stage rather than their sum

#### Scenario: Sequential execution is selectable
- **WHEN** a configuration setting disables concurrent execution
- **THEN** independent stages SHALL execute one after another in a deterministic order

### Requirement: Stages execute conditionally on upstream content
A stage SHALL be able to declare a condition on an upstream output and SHALL be skipped without executing when the condition does not hold.

#### Scenario: No detections upstream means no downstream recognition
- **WHEN** the detection stage reports zero plate detections
- **THEN** stages that consume detections SHALL be skipped and the pipeline SHALL complete with an empty detections result

#### Scenario: Condition on a confidence threshold
- **WHEN** a stage declares a minimum-confidence condition and the upstream confidence is below that threshold
- **THEN** the stage SHALL be skipped and the skip reason SHALL be recorded

### Requirement: Stage failure is contained and recorded
A stage that raises during execution SHALL NOT prevent sibling or downstream-unrelated stages from completing, and the failure SHALL be recorded with the stage name and the reason.

#### Scenario: Failure of one stage does not abort the pipeline
- **WHEN** a stage raises an execution error while other stages have already produced valid outputs
- **THEN** the system SHALL preserve the outputs of the stages that succeeded and record the failed stage name and reason

#### Scenario: Failure of a stage whose output is consumed downstream
- **WHEN** a stage fails and downstream stages depend on its output
- **THEN** the dependent stages SHALL be skipped as a consequence, distinct from their own failure, and the cause SHALL reference the originating failed stage

### Requirement: Per-stage execution provider selection
Each stage SHALL be assigned an execution provider of `cpu`, `cuda`, or `rocm` by configuration, defaulting to CPU, and the stage SHALL run on the assigned provider when it is available.

#### Scenario: Default placement is CPU
- **WHEN** a stage is declared without an explicit provider
- **THEN** it SHALL execute on the CPU execution provider

#### Scenario: Provider substitution is logged
- **WHEN** a stage is assigned `rocm` and the ROCm execution provider is not available in the runtime
- **THEN** the stage SHALL fall back to the CPU execution provider, the substitution SHALL be logged, and the pipeline SHALL continue