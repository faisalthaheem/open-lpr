## Context

The project runs Django 4.2.30 on Python 3.11 with SQLite, gunicorn, and no third-party Django packages. All Django API usage in the codebase is standard and current — no deprecated imports, no `pytz`, no `index_together`, no positional `Model.save()` calls. `USE_TZ = True` and `DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'` are already set explicitly in settings.

## Goals / Non-Goals

**Goals:**
- Upgrade to Django 5.2 LTS with zero functional regressions.
- All existing tests continue to pass.

**Non-Goals:**
- Adopting new Django 5.x features (just the upgrade).
- Upgrading to Django 6.x (requires Python 3.12+).
- Changing the Python version.

## Decisions

**1. Target Django 5.2 LTS directly (skip 5.0/5.1)**

Django supports upgrading across multiple versions in one step. Going straight to 5.2 LTS avoids intermediate steps and lands on the longest-supported release.

**2. Verify via test suite + deprecation warnings**

Run `python -Wa manage.py test` to catch any deprecation warnings that signal future breakage.

## Risks / Trade-offs

- **[Docker image needs rebuild]** → Mitigation: Standard rebuild, no Dockerfile changes needed.
- **[openai SDK compatibility with Django 5.2]** → Mitigation: The openai SDK doesn't depend on Django. No conflict expected.
