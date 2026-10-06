# settings-configuration Specification

## ADDED Requirements

### Requirement: Inference backend and artifact settings are environment-configurable
The inference backend selection and the artifact acquisition settings SHALL be resolved through the project's environment configuration mechanism with sensible defaults, so a deployment can state its intent without editing code.

#### Scenario: Backend selection is configurable
- **WHEN** the inference backend is not supplied through the environment
- **THEN** the application SHALL default to the local ONNX backend

#### Scenario: Artifact revision is pinned by default
- **WHEN** the artifact revision is not supplied through the environment
- **THEN** the application SHALL resolve artifacts at a pinned release revision rather than a moving branch

#### Scenario: Artifact acquisition can be disabled
- **WHEN** artifact download is disabled through the environment
- **THEN** the container entrypoint SHALL skip the download while still verifying artifact presence before serving traffic

#### Scenario: Upload pixel ceiling is configurable
- **WHEN** the upload pixel ceiling is not supplied through the environment
- **THEN** the application SHALL enforce a default ceiling derived from expected input resolution, so an image exceeding it is rejected on declared dimensions before decompression

#### Scenario: Disabling the pixel ceiling is supported
- **WHEN** the upload pixel ceiling is set to zero through the environment
- **THEN** the dimension check SHALL be skipped

#### Scenario: Artifact settings are documented
- **WHEN** an artifact or backend environment variable is added to settings
- **THEN** it SHALL be present in the project's example environment files and documented in the project agent documentation

### Requirement: Validators tolerate their input forms
A validator that accepts more than one kind of input object SHALL handle each declared form rather than assuming one, because a validator that raises on a valid form is worse than one that is absent.

#### Scenario: Open image is accepted by the dimension validator
- **WHEN** the image dimension validator receives an already-open image
- **THEN** it SHALL read the declared dimensions from that image without attempting to open it again

#### Scenario: File-like object is accepted by the dimension validator
- **WHEN** the image dimension validator receives a file-like object
- **THEN** it SHALL read the declared dimensions from that object's header without decompressing pixel data

#### Scenario: Non-image input is left to the caller
- **WHEN** the dimension validator receives input that is not an image
- **THEN** it SHALL defer to the caller's existing validity handling rather than reporting a competing error