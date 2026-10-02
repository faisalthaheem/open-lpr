## ADDED Requirements

### Requirement: Uniform stage interface
Every pipeline stage SHALL implement a single interface that declares its name, its required input fields, its produced output fields, and its model artifact location, and that exposes a load operation and an execution operation.

#### Scenario: Stage declares its contract
- **WHEN** a stage is registered with the graph
- **THEN** it SHALL expose its name, required input fields, output fields, and model path without being executed

#### Scenario: Swapping a model requires no graph change
- **WHEN** the model artifact path for a declared stage is changed in configuration to a different ONNX file of the same input and output signature
- **THEN** the pipeline SHALL execute the new artifact with no change to the graph definition or to any other stage

#### Scenario: Non-model stage declares no artifact
- **WHEN** a stage performs no model inference, such as a classical geometric transform
- **THEN** it SHALL declare the absence of a model artifact and SHALL be executed without loading one

### Requirement: Stage loading is lazy and happens once
A stage's model artifact SHALL be loaded on first use and reused for subsequent executions, and a stage that is never executed SHALL NOT have its artifact loaded.

#### Scenario: Model loaded on first execution only
- **WHEN** a stage executes more than once during the process lifetime
- **THEN** the artifact SHALL be loaded on the first execution and the loaded session SHALL be reused, without a reload

#### Scenario: Skipped stage does not load its model
- **WHEN** a stage's execution condition does not hold and the stage is skipped
- **THEN** its model artifact SHALL not be loaded

#### Scenario: Session is shared safely across concurrent stages
- **WHEN** multiple stages are eligible to execute concurrently
- **THEN** each SHALL use its own session instance and no stage SHALL observe another's session state

### Requirement: Artifact absence is a clear failure
When a stage's declared model artifact is missing or cannot be loaded, the system SHALL raise an error naming the stage and the resolved path, rather than proceeding with an unusable stage.

#### Scenario: Missing artifact is reported with its path
- **WHEN** a stage's model file does not exist at its configured location
- **THEN** the system SHALL report an error naming the stage and the resolved path

#### Scenario: No silent degradation to a default model
- **WHEN** a stage's artifact cannot be loaded
- **THEN** the system SHALL NOT substitute a different model or bypass the stage implicitly

### Requirement: Inference input and output shape validation
The runtime SHALL verify that a loaded artifact's declared input and output names and shapes match what the stage expects to supply and consume, and SHALL report a mismatch as a stage error.

#### Scenario: Input shape mismatch is detected
- **WHEN** the artifact expects an input of a different rank or channel count than the stage provides
- **THEN** the stage SHALL fail with an error naming the expected and actual shape

#### Scenario: Output name mismatch is detected
- **WHEN** the artifact produces output tensors whose names do not match the outputs the stage reads
- **THEN** the stage SHALL fail with an error naming the missing output rather than reading a tensor of unintended meaning