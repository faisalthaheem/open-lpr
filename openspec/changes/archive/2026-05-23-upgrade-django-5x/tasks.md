## 1. Verification

- [x] 1.1 Install Django 5.2 into the virtual environment (`pip install -r requirements.txt`) and confirm version
- [x] 1.2 Run `python manage.py check --deploy` and resolve any errors or critical warnings
- [x] 1.3 Run `python manage.py makemigrations --check` to confirm no unexpected schema changes
- [x] 1.4 Run `python manage.py migrate` to apply any pending migrations
- [x] 1.5 Start the dev server and verify the home page, image detail page, history page, and health endpoint all load without errors

## 2. Dependency Compatibility

- [x] 2.1 Verify `django-cors-headers>=4.0` imports and runs without errors on Django 5.2
- [x] 2.2 Verify `django-apscheduler>=0.7.0` imports and runs without errors on Django 5.2; bump version if needed
- [x] 2.3 Verify remaining dependencies (`openai`, `python-decouple`, `gunicorn`, `prometheus-client`, `APScheduler`, `Pillow`) have no Django-related compatibility issues

## 3. Documentation Updates

- [x] 3.1 Update README.md Django badge from `Django-4.2.7` to `Django-5.2`
- [x] 3.2 Update README.md Python version references from `Python 3.8+` to `Python 3.10+`
- [x] 3.3 Update AGENTS.md header from "Django 4.2 web app" to "Django 5.2 LTS web app" and Python from "3.8+" to "3.10+"
- [x] 3.4 Review README.md Technology Stack table and confirm Django badge version is correct
