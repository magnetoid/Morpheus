import time

from django.core.cache import cache
from django.http import JsonResponse


class RateLimitMiddleware:
    """
    Enterprise Redis-backed Rate Limiting Middleware.
    Protects the GraphQL and Agent API endpoints from abuse, bot traffic,
    and runaway AI agent loops.

    Applies a simple sliding window / token bucket approximation.
    Agents authenticated via Authorization Header get higher limits than anonymous IPs.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # We only limit GraphQL and Agent API routes, static assets are skipped
        if not request.path.startswith('/graphql') and not request.path.startswith('/api'):
            return self.get_response(request)

        auth_header = request.headers.get('Authorization')
        client_ip = self._get_client_ip(request)

        # Identify client and assign limits
        if auth_header and auth_header.startswith('Bearer '):
            # Agent / Auth'd User - e.g., 600 requests per minute
            client_id = f'agent:{auth_header.split(" ")[1][:20]}'
            limit = 600
        else:
            # Anonymous IP - e.g., 100 requests per minute
            client_id = f'ip:{client_ip}'
            limit = 100

        window_size_seconds = 60
        current_minute = int(time.time() / window_size_seconds)
        cache_key = f'ratelimit:{client_id}:{current_minute}'

        # Increment atomic counter in Redis
        try:
            requests = cache.incr(cache_key)
        except ValueError:  # Key doesn't exist yet
            cache.set(cache_key, 1, timeout=window_size_seconds * 2)
            requests = 1

        if requests > limit:
            return JsonResponse(
                {
                    'error': 'Rate limit exceeded.',
                    'code': 'RATE_LIMITED',
                    'retry_after': window_size_seconds,
                },
                status=429,
            )

        return self.get_response(request)

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
