"""
Availability series retrieval.

The availability endpoint used to query Prometheus synchronously on every request,
which blocked a gunicorn worker for up to the upstream timeout whenever Prometheus
was slow. This module separates fetching from serving: a background job refreshes
the series on an interval and the view serves the cached copy, fetching inline only
when the cache is cold.
"""

import json
import logging
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from django.conf import settings
from django.core.cache import cache

from ..pipeline.local_backend import LLM_BACKEND, LOCAL_BACKEND

logger = logging.getLogger(__name__)

CACHE_KEY_TEMPLATE = "availability:{days}"
DEFAULT_DAYS = 3
QUERY_STEP_SECONDS = "300"
UPSTREAM_TIMEOUT_SECONDS = 10

# The series is derived from `lpr_api_health_status`, which is only written under
# the LLM backend. Under `local` the metric is stale rather than absent -- a
# previously-cached series outlives a backend switch -- so serving it would report
# the uptime of a backend this deployment no longer runs.
NOT_APPLICABLE_REASON = (
    "Availability is measured from the external VLM API, which is not in the request " "path under the local backend."
)


def active_backend() -> str:
    return getattr(settings, "PIPELINE_BACKEND", LOCAL_BACKEND)


def is_applicable() -> bool:
    return active_backend() == LLM_BACKEND


# Cache entries outlive the refresh interval so a failed refresh keeps serving the
# last good series rather than dropping to an error.
CACHE_TTL_SECONDS = settings.AVAILABILITY_REFRESH_SECONDS * 10


def cache_key(days: int) -> str:
    return CACHE_KEY_TEMPLATE.format(days=days)


def fetch_availability_points(days: int = DEFAULT_DAYS):
    """
    Query Prometheus for the availability series.

    Args:
        days: Size of the window to query, in days

    Returns:
        A list of ``{"timestamp": ..., "value": ...}`` points, or None if the
        upstream request failed.
    """
    prometheus_url = getattr(settings, "PROMETHEUS_URL", "http://prometheus:9090")
    now = datetime.now(dt_timezone.utc)
    start = now - timedelta(days=days)

    params = urllib.parse.urlencode(
        {
            "query": "avg_over_time(lpr_api_health_status[5m])",
            "start": start.timestamp(),
            "end": now.timestamp(),
            "step": QUERY_STEP_SECONDS,
        }
    )

    url = f"{prometheus_url}/api/v1/query_range?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=UPSTREAM_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"Availability query failed: {str(e)}")
        return None

    results = data.get("data", {}).get("result", [])
    if not results:
        return []

    return [
        {
            "timestamp": datetime.fromtimestamp(float(v[0]), tz=dt_timezone.utc).isoformat(),
            "value": float(v[1]),
        }
        for v in results[0].get("values", [])
    ]


def refresh_availability(days: int = DEFAULT_DAYS) -> bool:
    """
    Fetch the series and store it in the cache.

    Runs on a schedule from the application scheduler.

    Returns:
        True if the cache was updated, False if the fetch failed.
    """
    # Checked before the query, not after: under `local` there is nothing to
    # fetch, and populating the cache would leave a series for the endpoint to
    # serve after a later switch back.
    if not is_applicable():
        return False

    points = fetch_availability_points(days)
    if points is None:
        return False

    cache.set(cache_key(days), points, timeout=CACHE_TTL_SECONDS)
    return True


def get_availability_points(days: int = DEFAULT_DAYS):
    """
    Return the availability series, fetching inline only on a cold cache.

    Args:
        days: Size of the window, in days

    Returns:
        A ``(points, error)`` tuple. ``points`` is a list (possibly empty) on
        success and None with ``error`` set when the series could not be obtained.
        When the active backend has no external API to measure, the tuple is
        ``(None, None)`` -- check ``is_applicable()`` to tell that case apart from
        an empty series, which means "queried, nothing recorded yet".
    """
    # Before the cache read: a series cached under `llm` survives the switch and
    # would otherwise be served as though it described local inference.
    if not is_applicable():
        return None, None

    key = cache_key(days)
    cached = cache.get(key)
    if cached is not None:
        return cached, None

    points = fetch_availability_points(days)
    if points is None:
        return None, "Prometheus unavailable"

    cache.set(key, points, timeout=CACHE_TTL_SECONDS)
    return points, None
