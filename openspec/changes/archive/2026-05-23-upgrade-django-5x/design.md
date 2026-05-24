## Context

The project is a Django-based license plate recognition web app. `requirements.txt` already declares `Django>=5.2,<5.3`, meaning the dependency is already pinned to the 5.2 LTS line. However, documentation and metadata across the project still reference Django 4.2 and Python 3.8+. The codebase needs a verified, documented upgrade with all references updated.

Current state:
- `requirements.txt`: `Django>=5.2,<5.3` (already correct)
- `Dockerfile`: `python:3.11-slim` (compatible with Django 5.2)
- README.md: Badge says `Django-4.2.7`, text says `Python 3.8+`
- AGENTS.md: Says "Django 4.2 web app", "Python 3.8+"
- No usage of Django APIs removed in 5.0/5.1/5.2 (verified via codebase scan)

## Goals / Non-Goals

**Goals:**
- Verify full codebase compatibility with Django 5.2 LTS
- Update all documentation to accurately reflect Django 5.2 and Python 3.10+
- Run Django system checks and migrations against Django 5.2
- Verify third-party dependency compatibility

**Non-Goals:**
- Upgrading to Django 6.0 (out of scope; 5.2 LTS is the right target for long-term support through April 2028)
- Changing the database backend (staying with SQLite default)
- Modifying application behavior or adding new features

## Decisions

### 1. Target Django 5.2 LTS (not 6.0)

**Decision**: Pin to Django 5.2 LTS.

**Rationale**: Django 5.2 LTS receives extended support until April 2028. Django 6.0 (current) only gets support until April 2027. For a project that values stability, the LTS release is the right choice. The `requirements.txt` already pins `>=5.2,<5.3` which is correct.

### 2. Update minimum Python to 3.10

**Decision**: Declare Python 3.10+ as the minimum supported version.

**Rationale**: Django 5.2 requires Python 3.10+. The Dockerfile already uses Python 3.11, so no Docker change is needed. Documentation must be updated from "3.8+" to "3.10+".

### 3. No code changes expected

**Decision**: Treat this as a documentation-and-verification change.

**Rationale**: Codebase scan found no usage of APIs removed in Django 5.0/5.1/5.2 (`force_text`, `urlquote`, etc.). The `requirements.txt` already pins 5.2. The primary work is verification and documentation updates.

### 4. Verify third-party deps in requirements.txt

**Decision**: Check each dependency for Django 5.2 compatibility and bump versions if needed.

| Dependency | Current Pin | Django 5.2 Compatible? |
|---|---|---|
| `django-cors-headers>=4.0` | Yes (4.0+ supports Django 5.x) | No change needed |
| `django-apscheduler>=0.7.0` | Needs verification | May need bump |
| `APScheduler>=3.10,<4.0` | Independent of Django | No change needed |

## Risks / Trade-offs

- **Hidden deprecated API usage** → Mitigation: Run `python manage.py check --deploy` and review all deprecation warnings. Run the test suite.
- **Third-party incompatibility** (`django-apscheduler`) → Mitigation: Test import and basic functionality; bump version if needed.
- **Migration schema changes** → Mitigation: Django 5.2 ORM is backwards-compatible. Run `makemigrations --check` to confirm no auto-generated schema changes.
- **Existing deployments on older Django** → Mitigation: This is a documentation alignment, not a breaking dependency change (requirements.txt already pins 5.2).
