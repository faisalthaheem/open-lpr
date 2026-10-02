# settings-configuration Specification

## Purpose
Covers side-effect-free settings import, directory creation at container start, environment-configurable filesystem paths, and removal of deprecated or misleading settings.

## Requirements

### Requirement: Settings import is free of filesystem side effects
Importing the Django settings module SHALL NOT create directories or otherwise mutate the filesystem.

#### Scenario: No directories created on settings import
- **WHEN** the settings module is imported
- **THEN** no directory creation SHALL occur as a side effect of the import

#### Scenario: Settings remain importable in read-only or restricted environments
- **WHEN** the settings module is imported in an environment where filesystem writes are not permitted
- **THEN** the import SHALL succeed without raising a permission error

#### Scenario: Settings import emits no log output
- **WHEN** the settings module is imported
- **THEN** no log record SHALL be emitted during the import

### Requirement: Required directories are created at container start
The container entrypoint SHALL create the directories required for the database, media, and collected static files before the application starts.

#### Scenario: Directories exist before application startup
- **WHEN** the container entrypoint runs
- **THEN** the database directory, media directory, and static root SHALL be created before the application process starts

#### Scenario: Startup is repeatable
- **WHEN** the entrypoint runs on a container restart where the directories already exist
- **THEN** it SHALL complete successfully without error

### Requirement: Settings paths are environment-configurable
Filesystem paths used by the application SHALL be resolved through the project's environment configuration mechanism with sensible defaults.

#### Scenario: Metrics state file path is configurable
- **WHEN** the metrics state file path is not supplied through the environment
- **THEN** the application SHALL derive a default path from the configured data directory rather than using a hardcoded container-specific path

#### Scenario: Metrics state file path can be overridden
- **WHEN** a metrics state file path is supplied through the environment
- **THEN** the application SHALL use the supplied path

#### Scenario: Metrics persistence works outside a container
- **WHEN** the application runs outside the containerized environment with no metrics path configured
- **THEN** metrics persistence SHALL write to the derived default location without a permission error

#### Scenario: Documented example configuration is updated
- **WHEN** an environment variable is added to settings
- **THEN** it SHALL be present in the project's example environment files and documented in the project agent documentation

### Requirement: Deprecated settings removed
Settings removed from the framework SHALL NOT remain in project configuration, and SHALL NOT imply protection the project does not provide.

#### Scenario: Removed framework setting is absent
- **WHEN** the settings module is inspected
- **THEN** it SHALL NOT contain settings that the installed Django version no longer recognizes

#### Scenario: No misleading security settings
- **WHEN** the settings module is inspected
- **THEN** every security-related setting present SHALL correspond to a framework option that is actually enforced

#### Scenario: Existing protections are preserved
- **WHEN** deprecated settings are removed
- **THEN** settings that remain in effect SHALL continue to be applied unchanged
