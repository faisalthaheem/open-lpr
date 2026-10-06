# logging-hygiene Specification

## Purpose
Covers removal of debug-prefixed logging from request and inference paths, proportionate log volume per request, and exclusion of credential values from log output.

## Requirements

### Requirement: No debug-prefixed logging in request and inference paths
Debug-prefixed log statements left over from development SHALL be removed from request handling and inference paths.

#### Scenario: OCR upload request path
- **WHEN** an OCR upload request is processed
- **THEN** no log record containing a debug prefix SHALL be emitted for the request, including on success, on processing failure, and on exception

#### Scenario: Inference client path
- **WHEN** an inference call is made
- **THEN** no log record containing a debug prefix SHALL be emitted about the request URL, endpoint, model, or key presence

#### Scenario: Image processing path
- **WHEN** an image is processed
- **THEN** no log record containing a debug prefix SHALL be emitted about intermediate pipeline state or returned results

### Requirement: Actionable log level for application logging
The application logger SHALL NOT emit debug-level records during normal operation.

#### Scenario: Normal request produces no debug records
- **WHEN** the application serves requests in a non-debug configuration
- **THEN** the application logger SHALL emit records at info level and above only

#### Scenario: Verbose diagnostics are opt-in
- **WHEN** a developer needs debug-level diagnostics
- **THEN** the level SHALL be raised through configuration rather than through statements left permanently in the request path

### Requirement: Log volume is proportionate to request count
Per-request log output SHALL be bounded so that log volume does not grow with the number of internal pipeline steps.

#### Scenario: Successful request emits bounded records
- **WHEN** an OCR request succeeds
- **THEN** the number of log records emitted for that request SHALL remain small and fixed, independent of the number of pipeline phases

#### Scenario: Failures log context once
- **WHEN** a request fails with an exception
- **THEN** the error type, message, and traceback SHALL each be captured without being duplicated across adjacent statements

### Requirement: Request diagnostics exclude sensitive values
Logging SHALL NOT emit values that could carry credentials.

#### Scenario: API key is never logged by value
- **WHEN** a client is constructed or a request is made
- **THEN** no log record SHALL contain the API key value, only whether one is present
