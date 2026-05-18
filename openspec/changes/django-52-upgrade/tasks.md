## 1. Upgrade

- [x] 1.1 Update `Django==4.2.30` to `Django>=5.2,<5.3` in `requirements.txt` and run `pip install -r requirements.txt`.
- [x] 1.2 Run `python -Wa manage.py check` and fix any issues.
- [x] 1.3 Run `python -Wa manage.py test lpr_app.tests.test_retry -v 2` and verify all 26 tests pass with no warnings.
- [x] 1.4 Run `python manage.py migrate --run-syncdb` and verify the database is consistent.
