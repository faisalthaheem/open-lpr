# availability-caching Specification

## ADDED Requirements

### Requirement: Availability is backend-aware
The availability series derives from the vision-language-model health metric. While the local backend is active, the endpoint SHALL NOT present that series, because it does not describe the inference path serving requests.

#### Scenario: Not-applicable marker replaces the series under the local backend
- **WHEN** the availability endpoint is requested and the local backend is active
- **THEN** the endpoint SHALL return an explicit not-applicable marker rather than a series derived from vision-language-model health

#### Scenario: A series cached under the LLM backend is not served under the local backend
- **WHEN** a series was cached while the LLM backend was active and the backend has since switched to local
- **THEN** the endpoint SHALL NOT serve that cached series

#### Scenario: LLM backend behaviour is preserved
- **WHEN** the LLM backend is active
- **THEN** the endpoint SHALL serve the cached series and the background refresh SHALL query the metrics backend, exactly as before

## MODIFIED Requirements

### Requirement: Availability endpoint serves cached data
The availability endpoint SHALL serve availability series data from a cache refreshed in the background, keeping request latency independent of metrics backend responsiveness, and SHALL short-circuit without contacting the metrics backend when the series is not applicable to the active backend.

#### Scenario: Cached response is returned
- **WHEN** the availability endpoint is requested, cached series data is present, and the series applies to the active backend
- **THEN** the endpoint SHALL return the cached data without contacting the metrics backend

#### Scenario: Cold cache performs an inline fetch
- **WHEN** the availability endpoint is requested, no cached data is present, and the series applies to the active backend
- **THEN** the endpoint SHALL perform one upstream fetch, populate the cache, and return the fetched data

#### Scenario: No upstream contact when the series does not apply
- **WHEN** the availability endpoint is requested and the local backend is active
- **THEN** the endpoint SHALL NOT contact the metrics backend

#### Scenario: Upstream unavailability does not block
- **WHEN** the metrics backend is slow or unresponsive
- **THEN** requests to the availability endpoint SHALL NOT each occupy a worker for the full upstream timeout

### Requirement: Background cache refresh
The availability series SHALL be refreshed on a configured interval in the background, and the refresh SHALL perform no upstream work when the series does not apply to the active backend.

#### Scenario: Refresh queries the metrics backend when the series applies
- **WHEN** the refresh job runs and the LLM backend is active
- **THEN** it SHALL query the metrics backend and store the result in the cache

#### Scenario: Refresh skips the query when the series does not apply
- **WHEN** the refresh job runs and the local backend is active
- **THEN** it SHALL return without querying the metrics backend and without populating the cache

#### Scenario: Refresh is resilient to upstream failure
- **WHEN** the refresh job's upstream query fails
- **THEN** it SHALL report failure without clearing previously cached data