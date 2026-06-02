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
    CACHES=_TEST_CACHE,
)
class RateLimitWithinLimitTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_request_within_limit_succeeds(self):
        response = self.client.get("/api/v1/config/")
        self.assertEqual(response.status_code, 200)

    def test_rate_limit_headers_present(self):
        response = self.client.get("/api/v1/config/")
        self.assertIn("X-RateLimit-Limit", response.headers)
        self.assertIn("X-RateLimit-Remaining", response.headers)
        self.assertIn("X-RateLimit-Reset", response.headers)

    def test_rate_limit_header_values(self):
        response = self.client.get("/api/v1/config/")
        self.assertEqual(response["X-RateLimit-Limit"], "3")
        self.assertEqual(response["X-RateLimit-Remaining"], "2")


@override_settings(
    MEDIA_ROOT="/tmp/test_lpr_ratelimit_media/",
    RATE_LIMIT_ENABLE=True,
    RATE_LIMIT_RATE="2/min",
    RATE_LIMIT_EXCLUDE_PATHS=["/health/", "/api/v1/health-light/"],
    CACHES=_TEST_CACHE,
)
class RateLimitExceededTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_exceeding_limit_returns_429(self):
        self.client.get("/api/v1/config/")
        self.client.get("/api/v1/config/")
        response = self.client.get("/api/v1/config/")
        self.assertEqual(response.status_code, 429)

    def test_429_includes_retry_after_header(self):
        self.client.get("/api/v1/config/")
        self.client.get("/api/v1/config/")
        response = self.client.get("/api/v1/config/")
        self.assertIn("Retry-After", response.headers)

    def test_429_includes_rate_limit_headers(self):
        self.client.get("/api/v1/config/")
        self.client.get("/api/v1/config/")
        response = self.client.get("/api/v1/config/")
        self.assertEqual(response["X-RateLimit-Limit"], "2")
        self.assertEqual(response["X-RateLimit-Remaining"], "0")

    def test_429_body_contains_error_detail(self):
        self.client.get("/api/v1/config/")
        self.client.get("/api/v1/config/")
        response = self.client.get("/api/v1/config/")
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("throttled", data["detail"].lower())


@override_settings(
    MEDIA_ROOT="/tmp/test_lpr_ratelimit_media/",
    RATE_LIMIT_ENABLE=True,
    RATE_LIMIT_RATE="2/min",
    RATE_LIMIT_EXCLUDE_PATHS=["/health/", "/api/v1/health-light/"],
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
    CACHES=_TEST_CACHE,
)
class RateLimitDisabledTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_no_rate_limiting_when_disabled(self):
        for _ in range(10):
            response = self.client.get("/api/v1/config/")
            self.assertEqual(response.status_code, 200)

    def test_no_rate_limit_headers_when_disabled(self):
        response = self.client.get("/api/v1/config/")
        self.assertNotIn("X-RateLimit-Limit", response.headers)


@override_settings(
    MEDIA_ROOT="/tmp/test_lpr_ratelimit_media/",
    RATE_LIMIT_ENABLE=True,
    RATE_LIMIT_RATE="5/min",
    RATE_LIMIT_EXCLUDE_PATHS=["/health/", "/api/v1/health-light/"],
    CACHES=_TEST_CACHE,
)
class CustomRateTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_custom_rate_respected(self):
        for i in range(5):
            response = self.client.get("/api/v1/config/")
            self.assertEqual(response.status_code, 200)
        response = self.client.get("/api/v1/config/")
        self.assertEqual(response.status_code, 429)

    def test_custom_rate_header_shows_limit(self):
        response = self.client.get("/api/v1/config/")
        self.assertEqual(response["X-RateLimit-Limit"], "5")
