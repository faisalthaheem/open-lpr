## ADDED Requirements

### Requirement: Relative time formatting utility
The frontend SHALL provide a `formatRelativeTime` function that accepts an ISO 8601 date string and returns a human-readable relative time string.

#### Scenario: Less than 60 seconds ago
- **WHEN** the timestamp is less than 60 seconds in the past
- **THEN** the function SHALL return "just now"

#### Scenario: Minutes ago
- **WHEN** the timestamp is between 1 and 59 minutes in the past
- **THEN** the function SHALL return "<n> minutes ago" (e.g. "5 minutes ago", "1 minute ago" for singular)

#### Scenario: Hours ago
- **WHEN** the timestamp is between 1 and 23 hours in the past
- **THEN** the function SHALL return "<n> hours ago" (e.g. "2 hours ago", "1 hour ago" for singular)

#### Scenario: Days ago
- **WHEN** the timestamp is between 1 and 29 days in the past
- **THEN** the function SHALL return "<n> days ago" (e.g. "3 days ago", "1 day ago" for singular)

#### Scenario: 30 or more days ago
- **WHEN** the timestamp is 30 or more days in the past
- **THEN** the function SHALL return "on <date>" where date is formatted as a short date string

#### Scenario: Future timestamp
- **WHEN** the timestamp is in the future
- **THEN** the function SHALL return "just now"

### Requirement: PST timezone label on card timestamps
Image cards SHALL display the string "PST" as a timezone indicator appended to the relative time string.

#### Scenario: Relative time with PST suffix
- **WHEN** an image card displays a relative timestamp
- **THEN** the displayed string SHALL be the relative time followed by " · PST" (e.g. "5 minutes ago · PST")
