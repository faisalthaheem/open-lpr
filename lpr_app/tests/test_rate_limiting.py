from django.core.cache import cache
from django.test import TestCase, Client, override_settings

_TEST_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'rate-limit-test',
    }
}


@override_settings(
    MEDIA_ROOT="/tmp/test_lpr_ratelimit_media/",
    RATE_LIMIT_ENABLE=True,
    RATE_LIMIT_RATE="3/min",
    RATE_LIMIT_EXCLUDE_PATHS=["/health/", "/api/v1/health-light/"],
    RATE_LIMIT_INCLUDE_PATHS=["/api/v1/ocr/"],
    CACHES=_TEST_CACHE,
)
class RateLimitWithinLimitTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_included_path_gets_rate_limited(self):
        response = self.client.post("/api/v1/ocr/", {})
        self.assertIn(response.status_code, [400, 429, 200])

    def test_rate_limit_headers_on_included_path(self):
        response = self.client.post("/api/v1/ocr/", {})
        self.assertIn("X-RateLimit-Limit", response.headers)
        self.assertIn("X-RateLimit-Remaining", response.headers)
        self.assertIn("X-RateLimit-Reset", response.headers)

    def test_rate_limit_header_values(self):
        response = self.client.post("/api/v1/ocr/", {})
        self.assertEqual(response["X-RateLimit-Limit"], "3")
        self.assertEqual(response["X-RateLimit-Remaining"], "2")


@override_settings(
    MEDIA_ROOT="/tmp/test_lpr_ratelimit_media/",
    RATE_LIMIT_ENABLE=True,
    RATE_LIMIT_RATE="2/min",
    RATE_LIMIT_EXCLUDE_PATHS=["/health/", "/api/v1/health-light/"],
    RATE_LIMIT_INCLUDE_PATHS=["/api/v1/ocr/"],
    CACHES=_TEST_CACHE,
)
class RateLimitExceededTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_exceeding_limit_returns_429(self):
        self.client.post("/api/v1/ocr/", {})
        self.client.post("/api/v1/ocr/", {})
        response = self.client.post("/api/v1/ocr/", {})
        self.assertEqual(response.status_code, 429)

    def test_429_includes_retry_after_header(self):
        self.client.post("/api/v1/ocr/", {})
        self.client.post("/api/v1/ocr/", {})
        response = self.client.post("/api/v1/ocr/", {})
        self.assertIn("Retry-After", response.headers)

    def test_429_includes_rate_limit_headers(self):
        self.client.post("/api/v1/ocr/", {})
        self.client.post("/api/v1/ocr/", {})
        response = self.client.post("/api/v1/ocr/", {})
        self.assertEqual(response["X-RateLimit-Limit"], "2")
        self.assertEqual(response["X-RateLimit-Remaining"], "0")

    def test_429_body_contains_error_detail(self):
        self.client.post("/api/v1/ocr/", {})
        self.client.post("/api/v1/ocr/", {})
        response = self.client.post("/api/v1/ocr/", {})
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("throttled", data["detail"].lower())


@override_settings(
    MEDIA_ROOT="/tmp/test_lpr_ratelimit_media/",
    RATE_LIMIT_ENABLE=True,
    RATE_LIMIT_RATE="2/min",
    RATE_LIMIT_EXCLUDE_PATHS=["/health/", "/api/v1/health-light/"],
    RATE_LIMIT_INCLUDE_PATHS=["/api/v1/ocr/"],
    CACHES=_TEST_CACHE,
)
class NonIncludedPathsNotLimitedTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_config_endpoint_not_rate_limited(self):
        for _ in range(10):
            response = self.client.get("/api/v1/config/")
            self.assertEqual(response.status_code, 200)

    def test_images_endpoint_not_rate_limited(self):
        for _ in range(10):
            response = self.client.get("/api/v1/images/")
            self.assertEqual(response.status_code, 200)

    def test_availability_not_rate_limited(self):
        for _ in range(10):
            response = self.client.get("/api/v1/availability/")
            self.assertIn(response.status_code, [200, 503])

    def test_config_no_rate_limit_headers(self):
        response = self.client.get("/api/v1/config/")
        self.assertNotIn("X-RateLimit-Limit", response.headers)


@override_settings(
    MEDIA_ROOT="/tmp/test_lpr_ratelimit_media/",
    RATE_LIMIT_ENABLE=True,
    RATE_LIMIT_RATE="2/min",
    RATE_LIMIT_EXCLUDE_PATHS=["/health/", "/api/v1/health-light/"],
    RATE_LIMIT_INCLUDE_PATHS=["/api/v1/ocr/"],
    CACHES=_TEST_CACHE,
)
class HealthExcludedTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_health_light_not_rate_limited(self):
        for _ in range(5):
            response = self.client.get("/api/v1/health-light/")
            self.assertEqual(response.status_code, 200)

    def test_health_light_no_rate_limit_headers(self):
        response = self.client.get("/api/v1/health-light/")
        self.assertNotIn("X-RateLimit-Limit", response.headers)


@override_settings(
    MEDIA_ROOT="/tmp/test_lpr_ratelimit_media/",
    RATE_LIMIT_ENABLE=False,
    RATE_LIMIT_RATE="2/min",
    RATE_LIMIT_EXCLUDE_PATHS=["/health/", "/api/v1/health-light/"],
    RATE_LIMIT_INCLUDE_PATHS=["/api/v1/ocr/"],
    CACHES=_TEST_CACHE,
)
class RateLimitDisabledTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_no_rate_limiting_when_disabled(self):
        for _ in range(10):
            response = self.client.post("/api/v1/ocr/", {})
            self.assertIn(response.status_code, [400, 200])

    def test_no_rate_limit_headers_when_disabled(self):
        response = self.client.post("/api/v1/ocr/", {})
        self.assertNotIn("X-RateLimit-Limit", response.headers)


@override_settings(
    MEDIA_ROOT="/tmp/test_lpr_ratelimit_media/",
    RATE_LIMIT_ENABLE=True,
    RATE_LIMIT_RATE="5/min",
    RATE_LIMIT_EXCLUDE_PATHS=["/health/", "/api/v1/health-light/"],
    RATE_LIMIT_INCLUDE_PATHS=["/api/v1/ocr/"],
    CACHES=_TEST_CACHE,
)
class CustomRateTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_custom_rate_respected(self):
        for i in range(5):
            response = self.client.post("/api/v1/ocr/", {})
            self.assertIn(response.status_code, [400, 200])
        response = self.client.post("/api/v1/ocr/", {})
        self.assertEqual(response.status_code, 429)

    def test_custom_rate_header_shows_limit(self):
        response = self.client.post("/api/v1/ocr/", {})
        self.assertEqual(response["X-RateLimit-Limit"], "5")
