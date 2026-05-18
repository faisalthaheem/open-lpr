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

### Requirement: Retry exhaustion
The system SHALL mark an image as permanently `failed` with a descriptive error message when `retry_count` reaches `max_retries`.

#### Scenario: All retries exhausted
- **WHEN** a stuck image has `retry_count = 2` and `max_retries = 2`
- **THEN** the system SHALL set `processing_status = 'failed'` and `error_message` to "Processing failed after 2 attempts. Last error: {original_error}"

#### Scenario: Exhausted image not retried again
- **WHEN** an image has `retry_count >= max_retries` and is in `failed` state
- **THEN** the system SHALL NOT attempt further retries

### Requirement: Configurable timeout and retry count
`PROCESSING_TIMEOUT_MINUTES`, `MAX_RETRIES`, `RETRY_BATCH_SIZE`, and `RETRY_INTERVAL_MINUTES` SHALL be configurable via environment variables with sensible defaults.

#### Scenario: Default values
- **WHEN** no environment variables are set
- **THEN** `PROCESSING_TIMEOUT_MINUTES` SHALL default to 5, `MAX_RETRIES` SHALL default to 2, `RETRY_BATCH_SIZE` SHALL default to 5, and `RETRY_INTERVAL_MINUTES` SHALL default to 5

#### Scenario: Custom values
- **WHEN** `PROCESSING_TIMEOUT_MINUTES=10`, `MAX_RETRIES=3`, `RETRY_BATCH_SIZE=10`, and `RETRY_INTERVAL_MINUTES=3` are set in the environment
- **THEN** the system SHALL use those values for timeout detection, retry limits, batch size, and scheduling interval

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

### Requirement: Batch size setting
The system SHALL provide a `RETRY_BATCH_SIZE` setting that caps the number of stuck images processed per command invocation.

#### Scenario: Default batch size
- **WHEN** `RETRY_BATCH_SIZE` is not configured
- **THEN** it SHALL default to 5

#### Scenario: Batch size from environment
- **WHEN** `RETRY_BATCH_SIZE=10` is set in the environment
- **THEN** the system SHALL process at most 10 stuck images per invocation

### Requirement: Periodic retry scheduling
The system SHALL automatically trigger the stuck image retry command at a configurable interval without requiring external cron or manual invocation.

#### Scenario: Scheduler runs on application start
- **WHEN** the Django application starts and `RETRY_SCHEDULER_ENABLED` is not set or is `True`
- **THEN** the system SHALL start a background scheduler that runs `retry_stuck_images` every `RETRY_INTERVAL_MINUTES` minutes

#### Scenario: Scheduler disabled via environment
- **WHEN** `RETRY_SCHEDULER_ENABLED=False` is set in the environment
- **THEN** the system SHALL NOT start the background scheduler, and retry must be triggered manually

#### Scenario: Default scheduling interval
- **WHEN** `RETRY_INTERVAL_MINUTES` is not configured
- **THEN** the scheduler SHALL trigger retry processing every 5 minutes

#### Scenario: Custom scheduling interval
- **WHEN** `RETRY_INTERVAL_MINUTES=10` is set in the environment
- **THEN** the scheduler SHALL trigger retry processing every 10 minutes

### Requirement: Scheduler handles multi-worker deployment
When multiple gunicorn workers are running, the scheduler SHALL execute the retry job only once per interval.

#### Scenario: Single worker execution
- **WHEN** 3 gunicorn workers are running and the retry interval elapses
- **THEN** only one worker SHALL execute the retry job, and the other workers SHALL skip execution for that interval

#### Scenario: Worker restart recovers scheduler
- **WHEN** a gunicorn worker crashes and restarts
- **THEN** the scheduler SHALL resume on the restarted worker and continue firing jobs at the configured interval
