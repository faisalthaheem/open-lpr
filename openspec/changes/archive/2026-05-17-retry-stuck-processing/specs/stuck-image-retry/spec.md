## ADDED Requirements

### Requirement: Stuck image detection
The system SHALL identify images with `processing_status` of `processing` or `pending` where `upload_timestamp` is older than `PROCESSING_TIMEOUT_MINUTES` minutes.

#### Scenario: Image stuck in processing state
- **WHEN** an image has `processing_status = 'processing'` and `upload_timestamp` is more than 5 minutes ago
- **THEN** the system SHALL consider it stuck and eligible for retry

#### Scenario: Image stuck in pending state
- **WHEN** an image has `processing_status = 'pending'` and `upload_timestamp` is more than 5 minutes ago
- **THEN** the system SHALL consider it stuck and eligible for retry

#### Scenario: Recent image not considered stuck
- **WHEN** an image has `processing_status = 'processing'` and `upload_timestamp` is less than 5 minutes ago
- **THEN** the system SHALL NOT attempt to retry it

### Requirement: Retry execution
The system SHALL retry processing a stuck image by incrementing `retry_count`, resetting `processing_status` to `pending`, and invoking the processing pipeline.

#### Scenario: First retry attempt
- **WHEN** a stuck image has `retry_count = 0` and `max_retries = 2`
- **THEN** the system SHALL increment `retry_count` to 1, reset `processing_status` to `pending`, and reprocess the image

#### Scenario: Retry succeeds
- **WHEN** a retry attempt processes successfully
- **THEN** the image SHALL be marked `completed` with the processing result and `retry_count` preserved

#### Scenario: Retry fails but retries remain
- **WHEN** a retry attempt fails and `retry_count < max_retries`
- **THEN** the image SHALL be marked `failed` with the error message and remain eligible for future retry on the next command invocation

### Requirement: Retry exhaustion
The system SHALL mark an image as permanently `failed` with a descriptive error message when `retry_count` reaches `max_retries`.

#### Scenario: All retries exhausted
- **WHEN** a stuck image has `retry_count = 2` and `max_retries = 2`
- **THEN** the system SHALL set `processing_status = 'failed'` and `error_message` to "Processing failed after 2 attempts. Last error: {original_error}"

#### Scenario: Exhausted image not retried again
- **WHEN** an image has `retry_count >= max_retries` and is in `failed` state
- **THEN** the system SHALL NOT attempt further retries

### Requirement: Configurable timeout and retry count
`PROCESSING_TIMEOUT_MINUTES` and `MAX_RETRIES` SHALL be configurable via environment variables with sensible defaults.

#### Scenario: Default values
- **WHEN** no environment variables are set
- **THEN** `PROCESSING_TIMEOUT_MINUTES` SHALL default to 5 and `MAX_RETRIES` SHALL default to 2

#### Scenario: Custom values
- **WHEN** `PROCESSING_TIMEOUT_MINUTES=10` and `MAX_RETRIES=3` are set in the environment
- **THEN** the system SHALL use those values for timeout detection and retry limits

### Requirement: Retry attempt logging
Each retry attempt SHALL be recorded in `ProcessingLog` with the attempt number and outcome.

#### Scenario: Retry attempt logged
- **WHEN** the system retries a stuck image
- **THEN** a `ProcessingLog` entry SHALL be created with status `started` and message "Retry attempt {retry_count}/{max_retries}"

#### Scenario: Retry failure logged
- **WHEN** a retry attempt fails
- **THEN** a `ProcessingLog` entry SHALL be created with status `error` and the failure reason

### Requirement: UI displays retry information
The image detail page SHALL display the retry count and, when retries are exhausted, the exhaustion message.

#### Scenario: Retry count shown
- **WHEN** an image has `retry_count > 0`
- **THEN** the image detail page SHALL display "Retry attempts: {retry_count}/{max_retries}"

#### Scenario: No retries shown when zero
- **WHEN** an image has `retry_count = 0`
- **THEN** the image detail page SHALL NOT display retry information
