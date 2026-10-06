## ADDED Requirements

### Requirement: Shared client instance
The Qwen3-VL API client SHALL be constructed once per process and reused for all subsequent inference and health-check calls.

#### Scenario: Repeated accessor calls return the same client
- **WHEN** the client accessor is called multiple times within a single process
- **THEN** all calls SHALL return the same client instance rather than constructing a new one

#### Scenario: Connection pool is reused across requests
- **WHEN** multiple OCR requests are served by one process
- **THEN** all requests SHALL reuse the single underlying HTTP client and connection pool

#### Scenario: Client configuration is resolved once
- **WHEN** the client is first constructed
- **THEN** the API key, base URL, and model SHALL be read from settings at that time and reused for the life of the process

#### Scenario: Client is process-scoped
- **WHEN** the application runs under multiple worker processes
- **THEN** each worker SHALL construct its own client, and no client instance SHALL be shared across process boundaries

### Requirement: Missing configuration fails loudly
Client construction with an absent API key SHALL raise an error rather than silently returning a non-functional client.

#### Scenario: Absent API key raises on first use
- **WHEN** the client accessor is first invoked and no API key is configured
- **THEN** an error SHALL be raised identifying the missing configuration

#### Scenario: Failed construction is not cached as success
- **WHEN** client construction raises an error
- **THEN** a subsequent accessor call SHALL attempt construction again rather than returning a cached broken client

### Requirement: Fault-tolerant batch inference
Batch inference SHALL isolate failures to individual items so that one failure does not discard results already obtained for other items.

#### Scenario: One item fails and others succeed
- **WHEN** a batch of images is submitted and one image raises an error
- **THEN** the successful results SHALL be returned in their original positions, and the failed position SHALL contain an empty value rather than causing the whole batch to fail

#### Scenario: All items fail
- **WHEN** every image in a batch raises an error
- **THEN** a result of the same length as the input SHALL be returned with every position empty

#### Scenario: Callers handle partial results
- **WHEN** a caller receives a batch result containing empty positions
- **THEN** the caller SHALL treat only those positions as failed and SHALL process the remaining positions normally

### Requirement: Inference call instrumentation
Inference calls SHALL record their outcome and duration without emitting per-request debug residue.

#### Scenario: Successful call is logged at info level
- **WHEN** an inference call completes successfully
- **THEN** a single informational record with the call duration SHALL be emitted, and no debug-prefixed records SHALL be emitted for the call

#### Scenario: Failed call is logged once
- **WHEN** an inference call raises an error
- **THEN** a single error record SHALL be emitted containing the error type and message