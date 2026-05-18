## MODIFIED Requirements

### Requirement: Configurable timeout and retry count
`PROCESSING_TIMEOUT_MINUTES`, `MAX_RETRIES`, `RETRY_BATCH_SIZE`, and `RETRY_INTERVAL_MINUTES` SHALL be configurable via environment variables with sensible defaults.

#### Scenario: Default values
- **WHEN** no environment variables are set
- **THEN** `PROCESSING_TIMEOUT_MINUTES` SHALL default to 5, `MAX_RETRIES` SHALL default to 2, `RETRY_BATCH_SIZE` SHALL default to 5, and `RETRY_INTERVAL_MINUTES` SHALL default to 5

#### Scenario: Custom values
- **WHEN** `PROCESSING_TIMEOUT_MINUTES=10`, `MAX_RETRIES=3`, `RETRY_BATCH_SIZE=10`, and `RETRY_INTERVAL_MINUTES=3` are set in the environment
- **THEN** the system SHALL use those values for timeout detection, retry limits, batch size, and scheduling interval

## ADDED Requirements

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
