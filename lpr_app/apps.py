import logging
import os
import sys

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)


def _should_run_scheduler():
    if not getattr(settings, 'RETRY_SCHEDULER_ENABLED', True):
        return False
    if os.environ.get('RUN_SCHEDULER', '').lower() in ('1', 'true', 'yes'):
        return True
    return 'gunicorn' in os.path.basename(sys.argv[0]).lower()


class LprAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lpr_app'
    verbose_name = 'License Plate Recognition'

    def ready(self):
        if not _should_run_scheduler():
            return

        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.interval import IntervalTrigger
            from django_apscheduler.jobstores import DjangoJobStore

            scheduler = BackgroundScheduler()
            scheduler.add_jobstore(DjangoJobStore(), 'default')

            scheduler.add_job(
                'lpr_app.scheduler:run_retry_stuck_images',
                trigger=IntervalTrigger(minutes=settings.RETRY_INTERVAL_MINUTES),
                id='retry_stuck_images',
                replace_existing=True,
            )

            scheduler.start()
            logger.info(
                'APScheduler started: retry_stuck_images every %d minutes',
                settings.RETRY_INTERVAL_MINUTES,
            )
        except Exception:
            logger.exception('Failed to start APScheduler')