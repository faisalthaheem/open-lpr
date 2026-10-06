"""Availability is only meaningful under the LLM backend.

The series is derived from `lpr_api_health_status`, which is written when the VLM
API is probed. Under `local` there is no such probe, so the metric goes stale --
and because the cache outlives a backend switch, a series captured under `llm`
stays readable after the switch. Serving it would report the uptime of a backend
this deployment no longer runs.
"""

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from lpr_app.services.availability import cache_key, get_availability_points, refresh_availability


class AvailabilityBackendTest(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    @override_settings(PIPELINE_BACKEND="local")
    def test_local_backend_reports_not_applicable(self):
        response = self.client.get("/api/v1/availability/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["applicable"])
        self.assertEqual(data["backend"], "local")
        self.assertIn("VLM API", data["reason"])
        self.assertEqual(data["data"], [])

    @override_settings(PIPELINE_BACKEND="local")
    def test_not_applicable_is_distinguishable_from_empty_series(self):
        """`applicable: false` must not look like "queried, nothing recorded".

        Both return HTTP 200 with an empty `data`, so the flag is the only thing
        telling the SPA whether to draw an outage or explain the absence.
        """
        not_applicable = self.client.get("/api/v1/availability/").json()

        with (
            override_settings(PIPELINE_BACKEND="llm"),
            patch("lpr_app.services.availability.fetch_availability_points", return_value=[]),
        ):
            empty = self.client.get("/api/v1/availability/").json()

        self.assertFalse(not_applicable["applicable"])
        self.assertTrue(empty["applicable"])
        self.assertEqual(empty["data"], [])

    @override_settings(PIPELINE_BACKEND="local")
    def test_series_cached_under_llm_is_not_served_under_local(self):
        """The cache is the trap: a stale series reads as current data."""
        stale = [{"timestamp": "2026-10-01T00:00:00+00:00", "value": 1.0}]
        with override_settings(PIPELINE_BACKEND="llm"):
            cache.set(cache_key(3), stale, timeout=300)

        points, error = get_availability_points(3)

        self.assertIsNone(points)
        self.assertIsNone(error)

    @override_settings(PIPELINE_BACKEND="local")
    def test_no_prometheus_query_under_local(self):
        with patch("lpr_app.services.availability.fetch_availability_points") as fetch:
            response = self.client.get("/api/v1/availability/")

        self.assertEqual(response.status_code, 200)
        fetch.assert_not_called()

    @override_settings(PIPELINE_BACKEND="local")
    def test_refresh_availability_makes_no_query_and_leaves_cache_empty(self):
        with patch("lpr_app.services.availability.fetch_availability_points") as fetch:
            self.assertFalse(refresh_availability(3))

        fetch.assert_not_called()
        self.assertIsNone(cache.get(cache_key(3)))

    @override_settings(PIPELINE_BACKEND="llm")
    def test_llm_backend_still_serves_series(self):
        series = [{"timestamp": "2026-10-01T00:00:00+00:00", "value": 1.0}]
        with patch("lpr_app.services.availability.fetch_availability_points", return_value=series):
            response = self.client.get("/api/v1/availability/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["applicable"])
        self.assertEqual(data["data"], series)

    @override_settings(PIPELINE_BACKEND="llm")
    def test_upstream_failure_still_returns_503(self):
        with patch("lpr_app.services.availability.fetch_availability_points", return_value=None):
            response = self.client.get("/api/v1/availability/")

        self.assertEqual(response.status_code, 503)
        self.assertIn("error", response.json())
