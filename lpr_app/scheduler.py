import logging

from django.conf import settings
from django.core.management import call_command

logger = logging.getLogger(__name__)


def run_retry_stuck_images():
    call_command('retry_stuck_images')
