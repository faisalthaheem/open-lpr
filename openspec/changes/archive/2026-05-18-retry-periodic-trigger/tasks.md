## 1. Dependencies

- [x] 1.1 Add `APScheduler>=3.10,<4.0` and `django-apscheduler>=0.7.0` to `requirements.txt` and run `pip install -r requirements.txt`.

## 2. Settings

- [x] 2.1 Add `django_apscheduler` to `INSTALLED_APPS` in `settings.py`.
- [x] 2.2 Add `RETRY_INTERVAL_MINUTES` (default 5) and `RETRY_SCHEDULER_ENABLED` (default True) to `settings.py` using `python-decouple` `config()`.
- [x] 2.3 Add `RETRY_INTERVAL_MINUTES` and `RETRY_SCHEDULER_ENABLED` to `.env.example` and `.env.llamacpp.example` with comments.

## 3. Scheduler Setup

- [x] 3.1 In `lpr_app/apps.py`, start the APScheduler background thread in `LprAppConfig.ready()` — create a `BackgroundScheduler` with `DjangoJobStore`, register `retry_stuck_images` as an `interval` job using the `RETRY_INTERVAL_MINUTES` setting, and guard with `RETRY_SCHEDULER_ENABLED`.
- [x] 3.2 Run `python manage.py migrate` to create the django-apscheduler database tables.

## 4. Verification

- [x] 4.1 Run `python -Wa manage.py check` and verify no issues.
- [x] 4.2 Run `python manage.py test lpr_app.tests.test_retry -v 2` and verify all tests pass.
- [x] 4.3 Start the dev server briefly and verify the scheduler starts (check logs for APScheduler startup messages and job registration).
