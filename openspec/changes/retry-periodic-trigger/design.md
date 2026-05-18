## Context

The `retry_stuck_images` management command finds and retries stuck images, but requires external scheduling (cron, systemd timer). The Docker container runs only gunicorn — no cron daemon, no sidecar process. The docker-compose deployment uses 1 gunicorn worker, but the Dockerfile defaults to 3 workers, so the scheduler must handle multi-worker deployment without duplicate execution.

## Goals / Non-Goals

**Goals:**
- Automatically run `retry_stuck_images` at a configurable interval when Django starts.
- Prevent duplicate execution when multiple gunicorn workers are running.
- Allow the scheduler to be disabled via environment variable.
- Zero Docker infrastructure changes (no sidecar, no cron daemon).

**Non-Goals:**
- Adding Celery or any message broker.
- Changing the Dockerfile or docker-compose configuration.
- Adding a manual "Retry" button in the UI.
- Scheduling any jobs other than stuck image retry.

## Decisions

**1. APScheduler with django-apscheduler**

Use `APScheduler` (v3.x) with `django-apscheduler` for Django integration. APScheduler runs as a background thread within the Django process. `django-apscheduler` provides a Django ORM job store that uses database-level locking to ensure only one worker fires each job per interval.

Alternatives considered:
- *Custom daemon thread + file lock*: Zero dependencies, but reinventing APScheduler's locking, retry, and state management. Fragile edge cases (stale locks, crash recovery).
- *Celery Beat*: Adds Redis/RabbitMQ dependency. Overkill for a single periodic job.
- *Cron daemon in container*: Requires Dockerfile changes, cron installation, and crontab management. Violates the "zero Docker changes" goal.

**2. Scheduler started in AppConfig.ready()**

Start the APScheduler background thread in `lpr_app.apps.LprAppConfig.ready()`. This is the standard Django pattern for starting background services — `ready()` is called once after all models are loaded, before the application starts serving requests.

**3. django-apscheduler added to INSTALLED_APPS**

`django-apscheduler` provides Django models for job storage (`DjangoJob`, `DjangoJobExecution`). Adding it to `INSTALLED_APPS` and running migrations creates the necessary tables.

**4. Configurable via python-decouple**

`RETRY_INTERVAL_MINUTES` (default 5) and `RETRY_SCHEDULER_ENABLED` (default True) follow the existing pattern in `settings.py` using `config()` from `python-decouple`.

**5. Existing management command reused**

The scheduler calls `retry_stuck_images` via `django.core.management.call_command()`. No new processing logic — the management command already implements the full retry pipeline with batch size limits.

## Risks / Trade-offs

- **[Scheduler thread runs in every gunicorn worker]** → Mitigation: `django-apscheduler`'s ORM job store uses database-level locking. Only one worker acquires the lock and fires the job per interval. Other workers see the job as already executed.
- **[Scheduler thread dies if worker crashes]** → Mitigation: Gunicorn restarts crashed workers, which re-initializes the app and restarts the scheduler. Jobs that were mid-execution are handled by the management command's idempotent design (it queries fresh each time).
- **[Database migration adds new tables]** → Mitigation: `django-apscheduler` migrations are standard Django migrations. Safe to run alongside existing data.
- **[Two new dependencies]** → Mitigation: `APScheduler` and `django-apscheduler` are mature, widely-used packages with minimal surface area.
