from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import Client, TestCase, override_settings


@override_settings(MEDIA_ROOT="/tmp/test_lpr_health_media/")
class HealthLightEndpointTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_healthy_returns_200(self):
        response = self.client.get("/api/v1/health-light/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertTrue(data["database_healthy"])
        self.assertIn("timestamp", data)

    @patch("django.db.connection.cursor")
    def test_db_unhealthy_returns_503(self, mock_cursor):
        mock_ctx = MagicMock()
        mock_cursor.return_value.__enter__ = lambda s: mock_ctx
        mock_cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_ctx.execute.return_value = None
        mock_ctx.fetchone.return_value = (0,)

        response = self.client.get("/api/v1/health-light/")
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data["status"], "unhealthy")
        self.assertFalse(data["database_healthy"])

    @patch("django.db.connection.cursor", side_effect=Exception("DB down"))
    def test_db_exception_returns_503(self, mock_cursor):
        response = self.client.get("/api/v1/health-light/")
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data["status"], "unhealthy")

    def test_rejects_post(self):
        response = self.client.post("/api/v1/health-light/")
        self.assertEqual(response.status_code, 405)


@override_settings(MEDIA_ROOT="/tmp/test_lpr_health_media/")
@override_settings(PIPELINE_BACKEND="llm")
class AvailabilityEndpointTest(TestCase):
    """These exercise the Prometheus-backed path.

    The backend is pinned rather than left to the default: `local` has no
    external API to measure and correctly reports not-applicable, which is
    covered separately in `test_availability_backend`.
    """

    def setUp(self):
        self.client = Client()
        # The availability endpoint serves from the cache; clear it so tests
        # exercising a cold cache are not served another test's warm entry.
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_rejects_post(self):
        response = self.client.post("/api/v1/availability/")
        self.assertEqual(response.status_code, 405)

    @patch("lpr_app.services.availability.urllib.request.urlopen")
    def test_returns_data_points(self, mock_urlopen):
        import json

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {
                "status": "success",
                "data": {
                    "result": [
                        {
                            "values": [
                                [1717000000, "1"],
                                [1717000300, "0"],
                                [1717000600, "1"],
                            ]
                        }
                    ]
                },
            }
        ).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        response = self.client.get("/api/v1/availability/?days=1")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["data"]), 3)
        self.assertEqual(data["data"][0]["value"], 1.0)
        self.assertIn("timestamp", data["data"][0])

    @patch("lpr_app.services.availability.urllib.request.urlopen", side_effect=Exception("Connection refused"))
    def test_prometheus_unavailable_returns_503(self, mock_urlopen):
        response = self.client.get("/api/v1/availability/")
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data["error"], "Prometheus unavailable")

    @patch("lpr_app.services.availability.urllib.request.urlopen")
    def test_empty_prometheus_result(self, mock_urlopen):
        import json

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"status": "success", "data": {"result": []}}).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        response = self.client.get("/api/v1/availability/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["data"], [])

    @patch("lpr_app.services.availability.urllib.request.urlopen")
    def test_invalid_days_returns_400(self, mock_urlopen):
        response = self.client.get("/api/v1/availability/?days=abc")
        self.assertEqual(response.status_code, 400)
        self.assertIn("days", response.json()["error"])

    @patch("lpr_app.services.availability.urllib.request.urlopen")
    def test_serves_cached_series_without_upstream_call(self, mock_urlopen):
        from django.core.cache import cache

        from lpr_app.services.availability import cache_key

        cache.set(cache_key(3), [{"timestamp": "2026-01-01T00:00:00+00:00", "value": 1.0}], timeout=60)

        response = self.client.get("/api/v1/availability/?days=3")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["value"], 1.0)
        mock_urlopen.assert_not_called()

    @patch("lpr_app.services.availability.fetch_availability_points", return_value=None)
    def test_stale_cache_served_when_upstream_fails(self, mock_fetch):
        """A failed refresh must not turn into a user-visible error."""
        from django.core.cache import cache

        from lpr_app.services.availability import cache_key

        cache.set(cache_key(3), [{"timestamp": "2026-01-01T00:00:00+00:00", "value": 1.0}], timeout=60)
        cache.delete(cache_key(7))

        response = self.client.get("/api/v1/availability/?days=3")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]), 1)

    @patch("lpr_app.services.availability.fetch_availability_points", return_value=[])
    def test_cold_cache_fetches_inline(self, mock_fetch):
        response = self.client.get("/api/v1/availability/?days=5")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], [])
        mock_fetch.assert_called_once_with(5)

    @patch("lpr_app.services.availability.urllib.request.urlopen", side_effect=Exception("Connection refused"))
    def test_cold_cache_unreachable_upstream_returns_503(self, mock_urlopen):
        response = self.client.get("/api/v1/availability/?days=9")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], "Prometheus unavailable")


@override_settings(MEDIA_ROOT="/tmp/test_lpr_health_media/")
class BackendAwareHealthTest(TestCase):
    """Health must describe the backend that is actually serving requests.

    The failure this prevents is specific and has happened: the local backend
    shipped and returned HTTP 500 on every upload, while this endpoint reported
    healthy because it was measuring an external API that was not in the request
    path.
    """

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.client = Client()

    def _integrity(self, **overrides):
        base = {"ok": True, "missing": [], "corrupt": []}
        base.update(overrides)
        return base

    @override_settings(PIPELINE_BACKEND="local")
    def test_local_backend_makes_no_vlm_call(self):
        """The load-bearing assertion: no VLM client is even constructed.

        Asserting on the response alone would pass even if the probe ran and its
        result were discarded, which is the behaviour that has to stop.
        """
        with (
            patch("lpr_app.pipeline.artifact_health.check_integrity", return_value=self._integrity()),
            patch("lpr_app.views.api_views.get_qwen_client") as client,
        ):
            response = self.client.get("/health/")

        self.assertEqual(response.status_code, 200)
        client.assert_not_called()

    @override_settings(PIPELINE_BACKEND="local")
    def test_local_backend_reports_artifacts_and_no_api_healthy(self):
        with patch(
            "lpr_app.pipeline.artifact_health.check_integrity",
            return_value=self._integrity(),
        ):
            response = self.client.get("/health/")

        data = response.json()
        self.assertEqual(data["backend"], "local")
        self.assertTrue(data["artifacts_healthy"])
        self.assertTrue(data["database_healthy"])
        self.assertNotIn("api_healthy", data)

    @override_settings(PIPELINE_BACKEND="local")
    def test_local_backend_unhealthy_when_artifacts_missing(self):
        with patch(
            "lpr_app.pipeline.artifact_health.check_integrity",
            return_value=self._integrity(ok=False, missing=["plate_yolox_tiny_640.onnx"]),
        ):
            response = self.client.get("/health/")

        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertFalse(data["artifacts_healthy"])
        self.assertIn("plate_yolox_tiny_640.onnx", data["artifacts_missing"])

    @override_settings(PIPELINE_BACKEND="local")
    def test_local_backend_names_corrupt_artifacts(self):
        with patch(
            "lpr_app.pipeline.artifact_health.check_integrity",
            return_value=self._integrity(ok=False, corrupt=["plate_ocr_dict.json"]),
        ):
            response = self.client.get("/health/")

        self.assertEqual(response.status_code, 503)
        self.assertIn("plate_ocr_dict.json", response.json()["artifacts_corrupt"])

    @override_settings(PIPELINE_BACKEND="local")
    def test_unverified_manifest_is_still_healthy(self):
        """Unknown integrity must not be reported as broken."""
        with patch(
            "lpr_app.pipeline.artifact_health.check_integrity",
            return_value=self._integrity(unverified=True),
        ):
            response = self.client.get("/health/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["artifacts_unverified"])

    @override_settings(PIPELINE_BACKEND="local")
    def test_no_artifact_detail_when_healthy(self):
        """Empty lists would be noise on every successful poll."""
        with patch("lpr_app.pipeline.artifact_health.check_integrity", return_value=self._integrity()):
            data = self.client.get("/health/").json()

        self.assertNotIn("artifacts_missing", data)
        self.assertNotIn("artifacts_corrupt", data)

    @override_settings(PIPELINE_BACKEND="llm")
    def test_llm_backend_probes_api_as_before(self):
        client = MagicMock()
        client.health_check.return_value = True
        with patch("lpr_app.views.api_views.get_qwen_client", return_value=client):
            response = self.client.get("/health/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["backend"], "llm")
        self.assertTrue(data["api_healthy"])
        client.health_check.assert_called_once()

    @override_settings(PIPELINE_BACKEND="llm")
    def test_llm_backend_unhealthy_when_api_down(self):
        client = MagicMock()
        client.health_check.return_value = False
        with patch("lpr_app.views.api_views.get_qwen_client", return_value=client):
            response = self.client.get("/health/")

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["api_healthy"])

    @override_settings(PIPELINE_BACKEND="llm")
    def test_llm_backend_does_not_report_artifacts(self):
        client = MagicMock()
        client.health_check.return_value = True
        with (
            patch("lpr_app.views.api_views.get_qwen_client", return_value=client),
            patch("lpr_app.pipeline.artifact_health.check_integrity") as integrity,
        ):
            data = self.client.get("/health/").json()

        self.assertNotIn("artifacts_healthy", data)
        integrity.assert_not_called()

    @override_settings(PIPELINE_BACKEND="local")
    def test_database_failure_reported_under_local_backend(self):
        """A dead database is unhealthy on either backend.

        The exception path returns status and error rather than
        database_healthy -- that predates this change and is left alone.
        """
        with (
            patch("lpr_app.pipeline.artifact_health.check_integrity", return_value=self._integrity()),
            patch("django.db.connection.cursor", side_effect=Exception("DB down")),
        ):
            response = self.client.get("/health/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "unhealthy")
