## Why

The `retry_stuck_images` management command exists but has no scheduler — it must be invoked manually or via external cron. There is no cron daemon in the Docker container and no sidecar process. Stuck images will remain stuck indefinitely unless someone remembers to run the command.

## What Changes

- Add `APScheduler` and `django-apscheduler` as dependencies.
- Register `retry_stuck_images` as a periodic job that runs automatically when Django starts.
- Use Django ORM job store for database-level locking to prevent duplicate execution across gunicorn workers.
- Add configurable settings: `RETRY_INTERVAL_MINUTES` (default 5) and `RETRY_SCHEDULER_ENABLED` (default True).
- Update `.env.example` and `.env.llamacpp.example` with new settings.

## Capabilities

### New Capabilities

### Modified Capabilities
- `stuck-image-retry`: Adds automatic periodic scheduling of the retry command, removing the need for external cron or manual invocation.

## Impact

- `requirements.txt` — add `APScheduler` and `django-apscheduler`
- `lpr_project/settings.py` — add `django_apscheduler` to `INSTALLED_APPS`, add `RETRY_INTERVAL_MINUTES` and `RETRY_SCHEDULER_ENABLED` settings
- `lpr_app/apps.py` — start scheduler in `AppConfig.ready()`
- `.env.example`, `.env.llamacpp.example` — document new env vars
- Database migration for django-apscheduler job store tables
