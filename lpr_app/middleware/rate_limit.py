import time
import hashlib
from django.conf import settings
from django.http import JsonResponse
from django.core.cache import caches


def _parse_rate(rate_str):
    num, period = rate_str.split('/')
    num = int(num)
    period_seconds = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    return num, period_seconds.get(period[0].lower(), 60)


def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.rate = getattr(settings, 'RATE_LIMIT_RATE', '2/min')
        self.exclude_paths = getattr(settings, 'RATE_LIMIT_EXCLUDE_PATHS', ['/health/', '/api/v1/health-light/'])
        self.num_requests, self.period_seconds = _parse_rate(self.rate)
        self.cache = caches['default']
        self.cache_key_prefix = 'rl:'

    def _is_excluded(self, path):
        for excluded in self.exclude_paths:
            if path.startswith(excluded):
                return True
        return False

    def _get_cache_key(self, ip):
        bucket = int(time.time() / self.period_seconds)
        raw = f"{ip}:{bucket}"
        hash_key = hashlib.md5(raw.encode()).hexdigest()
        return f"{self.cache_key_prefix}{hash_key}"

    def __call__(self, request):
        if not getattr(settings, 'RATE_LIMIT_ENABLE', True):
            return self.get_response(request)

        if self._is_excluded(request.path):
            response = self.get_response(request)
            return response

        ip = _get_client_ip(request)
        cache_key = self._get_cache_key(ip)
        now = time.time()
        window_start = (int(now / self.period_seconds)) * self.period_seconds
        reset_at = window_start + self.period_seconds
        remaining_seconds = int(reset_at - now)

        current = self.cache.get(cache_key, 0)
        remaining = max(0, self.num_requests - current - 1)

        if current >= self.num_requests:
            response = JsonResponse(
                {'detail': f'Request was throttled. Expected available in {remaining_seconds} seconds.'},
                status=429,
            )
            response['Retry-After'] = str(remaining_seconds)
            response['X-RateLimit-Limit'] = str(self.num_requests)
            response['X-RateLimit-Remaining'] = '0'
            response['X-RateLimit-Reset'] = str(remaining_seconds)
            return response

        self.cache.set(cache_key, current + 1, timeout=self.period_seconds + 1)

        response = self.get_response(request)

        response['X-RateLimit-Limit'] = str(self.num_requests)
        response['X-RateLimit-Remaining'] = str(remaining)
        response['X-RateLimit-Reset'] = str(remaining_seconds)

        return response
