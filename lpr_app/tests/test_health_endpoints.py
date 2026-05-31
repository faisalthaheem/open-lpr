from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, override_settings


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
class AvailabilityEndpointTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_rejects_post(self):
        response = self.client.post("/api/v1/availability/")
        self.assertEqual(response.status_code, 405)

    @patch("lpr_app.views.api_views.urllib.request.urlopen")
    def test_returns_data_points(self, mock_urlopen):
        import json
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "status": "success",
            "data": {
                "result": [{
                    "values": [
                        [1717000000, "1"],
                        [1717000300, "0"],
                        [1717000600, "1"],
                    ]
                }]
            }
        }).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        response = self.client.get("/api/v1/availability/?days=1")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["data"]), 3)
        self.assertEqual(data["data"][0]["value"], 1.0)
        self.assertIn("timestamp", data["data"][0])

    @patch("lpr_app.views.api_views.urllib.request.urlopen", side_effect=Exception("Connection refused"))
    def test_prometheus_unavailable_returns_503(self, mock_urlopen):
        response = self.client.get("/api/v1/availability/")
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data["error"], "Prometheus unavailable")

    @patch("lpr_app.views.api_views.urllib.request.urlopen")
    def test_empty_prometheus_result(self, mock_urlopen):
        import json
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "status": "success",
            "data": {"result": []}
        }).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        response = self.client.get("/api/v1/availability/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["data"], [])

    @patch("lpr_app.views.api_views.urllib.request.urlopen")
    def test_invalid_days_defaults_to_3(self, mock_urlopen):
        import json
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "status": "success",
            "data": {"result": []}
        }).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        response = self.client.get("/api/v1/availability/?days=abc")
        self.assertEqual(response.status_code, 200)
