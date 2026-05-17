## MODIFIED Requirements

### Requirement: Retry execution
The system SHALL retry processing a stuck image by incrementing `retry_count`, resetting `processing_status` to `pending`, and invoking the processing pipeline. The system SHALL process at most `RETRY_BATCH_SIZE` stuck images per command invocation.

#### Scenario: First retry attempt
- **WHEN** a stuck image has `retry_count = 0` and `max_retries = 2`
- **THEN** the system SHALL increment `retry_count` to 1, reset `processing_status` to `pending`, and reprocess the image

#### Scenario: Retry succeeds
- **WHEN** a retry attempt processes successfully
- **THEN** the image SHALL be marked `completed` with the processing result and `retry_count` preserved

#### Scenario: Retry fails but retries remain
- **WHEN** a retry attempt fails and `retry_count < max_retries`
- **THEN** the image SHALL be marked `failed` with the error message and remain eligible for future retry on the next command invocation

#### Scenario: Batch size limits images processed
- **WHEN** 20 images are stuck and `RETRY_BATCH_SIZE = 5`
- **THEN** the system SHALL process at most 5 images in this invocation, leaving the remaining 15 for subsequent runs

#### Scenario: Fewer stuck images than batch size
- **WHEN** 3 images are stuck and `RETRY_BATCH_SIZE = 5`
- **THEN** the system SHALL process all 3 images

#### Scenario: Batch size overridden via command line
- **WHEN** `RETRY_BATCH_SIZE = 5` in settings and the command is invoked with `--batch-size 20`
- **THEN** the system SHALL process at most 20 images in this invocation

### Requirement: Configurable timeout and retry count
`PROCESSING_TIMEOUT_MINUTES`, `MAX_RETRIES`, and `RETRY_BATCH_SIZE` SHALL be configurable via environment variables with sensible defaults.

#### Scenario: Default values
- **WHEN** no environment variables are set
- **THEN** `PROCESSING_TIMEOUT_MINUTES` SHALL default to 5, `MAX_RETRIES` SHALL default to 2, and `RETRY_BATCH_SIZE` SHALL default to 5

#### Scenario: Custom values
- **WHEN** `PROCESSING_TIMEOUT_MINUTES=10`, `MAX_RETRIES=3`, and `RETRY_BATCH_SIZE=10` are set in the environment
- **THEN** the system SHALL use those values for timeout detection, retry limits, and batch size

## ADDED Requirements

### Requirement: Batch size setting
The system SHALL provide a `RETRY_BATCH_SIZE` setting that caps the number of stuck images processed per command invocation.

#### Scenario: Default batch size
- **WHEN** `RETRY_BATCH_SIZE` is not configured
- **THEN** it SHALL default to 5

#### Scenario: Batch size from environment
- **WHEN** `RETRY_BATCH_SIZE=10` is set in the environment
- **THEN** the system SHALL process at most 10 stuck images per invocation
