## Why

The project's `requirements.txt` already pins `Django>=5.2,<5.3`, but all documentation, badges, and the AGENTS.md still reference Django 4.2. Django 4.2 LTS extended support ends April 7, 2026. The codebase needs a verified upgrade to Django 5.2 LTS with all documentation and metadata brought in sync, and Python version requirements updated (Django 5.2 requires Python 3.10+).

## What Changes

- Verify all application code, views, models, and services are compatible with Django 5.2 APIs
- Update README.md Django version badge from 4.2.7 to 5.2
- Update README.md Python version references from 3.8+ to 3.10+
- Update AGENTS.md to reflect Django 5.2 and Python 3.10+
- Update Dockerfile Python base image if needed (currently 3.11, already compatible)
- Verify and run Django system check (`python manage.py check`) against Django 5.2
- Run migrations to ensure schema compatibility with Django 5.2 ORM
- Verify all third-party dependencies (`django-cors-headers`, `django-apscheduler`, etc.) are compatible with Django 5.2

## Capabilities

### New Capabilities

_None — this is an upgrade of the framework, not a new feature._

### Modified Capabilities

_None — no spec-level behavior changes. The upgrade maintains existing functionality on a newer framework version._

## Impact

- **Dependencies**: `requirements.txt` already pins Django 5.2; need to verify `django-cors-headers>=4.0` and `django-apscheduler>=0.7.0` compatibility with Django 5.2
- **Documentation**: README.md, AGENTS.md — version badges, Python version requirements, technology stack references
- **Docker**: Dockerfile uses `python:3.11-slim` which is compatible; no change needed
- **Database**: SQLite migrations must be verified; Django 5.2 ORM changes are backwards-compatible for existing schemas
- **Breaking changes**: Django 5.0+ removed several deprecated APIs (e.g., `force_text`, `urlquote`); codebase scan shows no usage of removed APIs
- **Python version**: Minimum supported Python changes from 3.8 to 3.10; AGENTS.md and README must reflect this
