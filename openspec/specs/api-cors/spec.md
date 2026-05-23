## ADDED Requirements

### Requirement: CORS headers for SPA origin
The backend SHALL include CORS headers in API responses to allow requests from the SPA frontend origin.

#### Scenario: Preflight request handling
- **WHEN** the SPA sends an OPTIONS preflight request to any API endpoint
- **THEN** the backend SHALL respond with `Access-Control-Allow-Origin` set to the configured SPA origin, `Access-Control-Allow-Methods` including GET and POST, `Access-Control-Allow-Headers` including `Content-Type`, and a 200 status code

#### Scenario: CORS headers on API responses
- **WHEN** the SPA sends a GET or POST request to any API endpoint from a different origin
- **THEN** the backend SHALL include `Access-Control-Allow-Origin` in the response header matching the request's `Origin` header (if it matches the configured allowed origins)

#### Scenario: CORS not applied to non-API routes
- **WHEN** a request is made to a non-API route (e.g., admin, Django views)
- **THEN** the backend MAY omit CORS headers for those routes

### Requirement: Configurable allowed origins
The list of allowed CORS origins SHALL be configurable via Django settings.

#### Scenario: Default allowed origins
- **WHEN** no `CORS_ALLOWED_ORIGINS` setting is provided
- **THEN** the backend SHALL default to allowing `http://localhost:3000` for local SPA development

#### Scenario: Custom allowed origins
- **WHEN** `CORS_ALLOWED_ORIGINS` is set to a list of URLs via environment variable
- **THEN** the backend SHALL allow CORS requests only from those origins
