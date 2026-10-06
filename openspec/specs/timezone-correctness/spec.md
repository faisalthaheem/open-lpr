# timezone-correctness Specification

## Purpose
Covers timezone-aware datetime usage throughout the application, media path partitioning from the aware clock, and ISO 8601 serialization of API timestamps.

## Requirements

### Requirement: Timezone-aware datetime usage
All datetime values created by application code SHALL be timezone-aware, consistent with the project's `USE_TZ` setting.

#### Scenario: Timestamps created in models
- **WHEN** application code creates a datetime for persistence
- **THEN** it SHALL create a timezone-aware datetime rather than a naive local-time datetime

#### Scenario: Timestamps created in services
- **WHEN** the image processing service records a processing timestamp
- **THEN** it SHALL record a timezone-aware datetime

#### Scenario: Timestamps returned by views
- **WHEN** an API response includes a timestamp field
- **THEN** the value SHALL be derived from a timezone-aware datetime

#### Scenario: No naive datetime warnings
- **WHEN** the application processes an image and serves API responses under `USE_TZ = True`
- **THEN** no naive-datetime runtime warnings SHALL be emitted

### Requirement: Media partitioning uses aware timestamps
Media upload paths SHALL be partitioned by date using the same timezone-aware clock as the stored upload timestamp.

#### Scenario: Upload folder matches recorded upload date
- **WHEN** an image is stored
- **THEN** the year, month, and day segments of its media path SHALL be derived from the same timezone-aware clock used for its stored upload timestamp, so the folder date and the recorded date agree

#### Scenario: Path generation is independent of container local time
- **WHEN** the server's local timezone differs from UTC
- **THEN** the media path date segments SHALL still be consistent with the stored upload timestamp

#### Scenario: Existing partition layout is preserved
- **WHEN** media paths are generated
- **THEN** the `uploads/` and `processed/` prefixes and the year/month/day segment structure SHALL remain unchanged

### Requirement: Timezone-aware ISO 8601 output
API responses that include timestamps SHALL serialize them as ISO 8601 values derived from timezone-aware datetimes.

#### Scenario: Aware datetime serialization
- **WHEN** a response includes a timestamp from an aware datetime
- **THEN** the serialized value SHALL be a valid ISO 8601 string representing that instant

#### Scenario: Null timestamps remain null
- **WHEN** a timestamp field has no value
- **THEN** the serialized value SHALL be `null` rather than an empty string or an error
