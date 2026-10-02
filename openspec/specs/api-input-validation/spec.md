# api-input-validation Specification

## Purpose
Covers consistent validation of numeric query parameters on public API endpoints, so that malformed client input produces a descriptive client error rather than an unhandled server error.

## Requirements

### Requirement: Numeric query parameter validation
Numeric query parameters on public API endpoints SHALL be validated before use, and unparseable values SHALL produce a client error response rather than an unhandled server error.

#### Scenario: Unparseable integer parameter
- **WHEN** a request supplies an integer query parameter whose value is not a valid integer
- **THEN** the endpoint SHALL return a `400` status response whose error message names the offending parameter, and SHALL NOT return a `500`

#### Scenario: Whitespace and empty values
- **WHEN** a request supplies an integer query parameter that is empty or contains only whitespace
- **THEN** the endpoint SHALL treat it as unparseable and return a `400` status response

#### Scenario: Negative page number
- **WHEN** a request supplies a page number below the minimum valid value
- **THEN** the endpoint SHALL clamp the value to the minimum rather than erroring

#### Scenario: Page size above maximum
- **WHEN** a request supplies a page size above the configured maximum
- **THEN** the endpoint SHALL clamp the value to the maximum rather than erroring

#### Scenario: Page size below minimum
- **WHEN** a request supplies a page size below the configured minimum
- **THEN** the endpoint SHALL clamp the value to the minimum rather than erroring

### Requirement: Validation is applied consistently across endpoints
Endpoints that accept numeric query parameters SHALL apply the same validation helper rather than relying on per-endpoint ad hoc handling.

#### Scenario: Shared helper is used
- **WHEN** more than one endpoint parses an integer query parameter
- **THEN** all such endpoints SHALL use the same shared validation helper

#### Scenario: Validation preserves existing bounds
- **WHEN** validation is introduced for a parameter that already had a documented default and maximum
- **THEN** the default and maximum SHALL remain unchanged
