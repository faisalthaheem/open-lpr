## ADDED Requirements

### Requirement: Availability graph on home page
The SPA home page SHALL display a graph showing backend service availability over the last 3 days, using data from the Prometheus availability proxy endpoint.

#### Scenario: Graph displays availability data
- **WHEN** the home page loads and availability data is successfully fetched
- **THEN** the graph SHALL render a line chart with time on the X-axis and availability (0-100%) on the Y-axis, covering the last 3 days

#### Scenario: Data points represent health status
- **WHEN** the availability data contains data points
- **THEN** each data point value SHALL represent the average health status (0=down, 1=up) for a 5-minute interval, displayed as a percentage

#### Scenario: Prometheus data unavailable
- **WHEN** the availability data request fails or returns an error
- **THEN** the graph area SHALL display a fallback message (e.g., "Availability data unavailable") instead of an empty or broken chart

### Requirement: Graph visual styling
The availability graph SHALL use colors consistent with the SPA's existing design language and support dark mode.

#### Scenario: Dark mode support
- **WHEN** the SPA is in dark mode
- **THEN** the graph background, axes, labels, and grid SHALL use dark-appropriate colors matching the existing theme

#### Scenario: Health status colors
- **WHEN** the graph renders data points
- **THEN** the line SHALL use the SPA's purple accent color, and the area under the line SHALL have a semi-transparent fill
