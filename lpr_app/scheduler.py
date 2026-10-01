import logging

from django.core.management import call_command

logger = logging.getLogger(__name__)


def run_retry_stuck_images():
    call_command("retry_stuck_images")


def refresh_availability():
    """
    Refresh the cached availability series so the API never queries Prometheus inline.

    A failed refresh is logged and skipped; the previously cached series is kept and
    the next scheduled run tries again.
    """
    from .services.availability import DEFAULT_DAYS
    from .services.availability import refresh_availability as _refresh

    if not _refresh(DEFAULT_DAYS):
        logger.warning("Availability refresh failed; keeping previously cached series")


__all__ = ["refresh_availability", "run_retry_stuck_images"]
