## Why

Django 4.2 LTS reached end of life in April 2026. The project needs to upgrade to a supported version. Django 5.2 is the current LTS release, supported until April 2028, and is compatible with the existing Python 3.11 runtime.

## What Changes

- Pin Django to 5.2.x in `requirements.txt`.
- Fix any code or settings incompatibilities revealed by the upgrade.

## Capabilities

### New Capabilities

### Modified Capabilities

## Impact

- `requirements.txt` — Django version bump
- Potentially `lpr_project/settings.py` — if any settings need updating
- Docker image rebuild required
