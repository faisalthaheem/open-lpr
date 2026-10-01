## ADDED Requirements

### Requirement: Availability endpoint serves cached data
The availability endpoint SHALL serve availability series data from a cache and SHALL NOT perform a blocking upstream query to the metrics backend on every request.

#### Scenario: Cached response is returned
- **WHEN** the availability endpoint is requested and cached series data is present
- **THEN** the endpoint SHALL return the cached data without contacting the metrics backend

#### Scenario: Cold cache performs an inline fetch
- **WHEN** the availability endpoint is requested and no cached data is present
- **THEN** the endpoint SHALL perform one upstream fetch, populate the cache, and return the fetched data

#### Scenario: Upstream unavailability does not block
- **WHEN** the metrics backend is slow or unresponsive
- **THEN** requests to the availability endpoint SHALL NOT each occupy a worker for the full upstream timeout

### Requirement: Background cache refresh
Cached availability data SHALL be refreshed on a fixed interval without requiring a request to trigger the refresh.

#### Scenario: Periodic refresh occurs
- **WHEN** cached availability data reaches its refresh interval
- **THEN** a background job SHALL fetch fresh series data and update the cache

#### Scenario: Refresh continues after a failure
- **WHEN** a scheduled refresh fails
- **THEN** the scheduler SHALL continue running and a later scheduled refresh SHALL be attempted

### Requirement: Availability data shape is unchanged
The availability endpoint SHALL continue to return the same response structure so existing consumers require no change.

#### Scenario: Response envelope preserved
- **WHEN** the availability endpoint returns series data
- **THEN** the response SHALL contain a data field holding an array of points, each with a timestamp and a numeric value

#### Scenario: Empty result preserved
- **WHEN** no series data is available from the metrics backend
- **THEN** the endpoint SHALL return a response containing an empty data array

#### Scenario: Upstream error preserved
- **WHEN** the metrics backend cannot be reached and no cached data is available
- **THEN** the endpoint SHALL return a `503` status response indicating the metrics backend is unavailable

### Requirement: Staleness is bounded
The interval between successful cache refreshes SHALL be shorter than the interval at which the underlying metric is scraped, so served data is never more stale than one scrape interval by more than a bounded margin.

#### Scenario: Refresh interval configuration
- **WHEN** the refresh interval is configured
- **THEN** it SHALL be configurable through the project environment configuration mechanism

#### Scenario: Stale data is preferable to no data
- **WHEN** a refresh fails but previously cached data exists
- **THEN** the endpoint SHALL continue serving the cached data rather than returning an error