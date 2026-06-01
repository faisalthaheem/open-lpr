import os
import sys
from unittest import mock

from django.test import TestCase, override_settings

from lpr_app.apps import _should_run_scheduler


class SchedulerGatingTest(TestCase):

    def test_skips_when_running_manage_py(self):
        with mock.patch.object(sys, 'argv', ['manage.py', 'migrate']):
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertFalse(_should_run_scheduler())

    def test_skips_when_running_manage_py_shell(self):
        with mock.patch.object(sys, 'argv', ['manage.py', 'shell']):
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertFalse(_should_run_scheduler())

    def test_runs_when_running_gunicorn(self):
        with mock.patch.object(sys, 'argv', ['gunicorn', '--bind', '0.0.0.0:8000']):
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertTrue(_should_run_scheduler())

    def test_runs_when_gunicorn_in_path(self):
        with mock.patch.object(sys, 'argv', ['/opt/venv/bin/gunicorn']):
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertTrue(_should_run_scheduler())

    @override_settings(RETRY_SCHEDULER_ENABLED=False)
    def test_disabled_by_setting(self):
        with mock.patch.object(sys, 'argv', ['gunicorn']):
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertFalse(_should_run_scheduler())

    def test_run_scheduler_env_var_overrides(self):
        with mock.patch.object(sys, 'argv', ['manage.py', 'migrate']):
            with mock.patch.dict(os.environ, {'RUN_SCHEDULER': 'true'}):
                self.assertTrue(_should_run_scheduler())

    def test_run_scheduler_env_var_one(self):
        with mock.patch.object(sys, 'argv', ['manage.py', 'shell']):
            with mock.patch.dict(os.environ, {'RUN_SCHEDULER': '1'}):
                self.assertTrue(_should_run_scheduler())

    def test_run_scheduler_env_var_yes(self):
        with mock.patch.object(sys, 'argv', ['manage.py', 'check']):
            with mock.patch.dict(os.environ, {'RUN_SCHEDULER': 'yes'}):
                self.assertTrue(_should_run_scheduler())

    def test_run_scheduler_env_var_false_does_not_override(self):
        with mock.patch.object(sys, 'argv', ['gunicorn']):
            with mock.patch.dict(os.environ, {'RUN_SCHEDULER': 'false'}):
                self.assertTrue(_should_run_scheduler())

    def test_run_scheduler_env_var_empty_does_not_override(self):
        with mock.patch.object(sys, 'argv', ['manage.py', 'runserver']):
            with mock.patch.dict(os.environ, {'RUN_SCHEDULER': ''}):
                self.assertFalse(_should_run_scheduler())

    def test_runs_under_django_runserver(self):
        with mock.patch.object(sys, 'argv', ['manage.py', 'runserver']):
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertFalse(_should_run_scheduler())
