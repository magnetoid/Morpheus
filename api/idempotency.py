from django.core.cache import cache
from django.http import HttpResponse


class IdempotencyMiddleware:
    """
    Enterprise API Idempotency Middleware.
    Prevents duplicate mutations (e.g., double-charging credit cards or placing duplicate orders)
    when network retries occur.

    Clients send an 'Idempotency-Key' header with a UUID.
    If the key has been seen recently (24 hours), the cached response is returned immediately
    without re-executing the underlying view/mutation.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # We only care about mutations/POST requests
        if request.method not in ['POST', 'PUT', 'PATCH']:
            return self.get_response(request)

        idempotency_key = request.headers.get('Idempotency-Key')
        if not idempotency_key:
            return self.get_response(request)

        # Optional: Tie the key to the authenticated user/agent to prevent cross-user key collisions
        user_id = (
            str(request.user.id)
            if hasattr(request, 'user') and request.user.is_authenticated
            else 'anon'
        )
        cache_key = f'idemp:{user_id}:{idempotency_key}'

        cached_response = cache.get(cache_key)
        if cached_response:
            return HttpResponse(
                cached_response['content'],
                status=cached_response['status'],
                content_type=cached_response['content_type'],
            )

        # Execute the actual request
        response = self.get_response(request)

        # Only cache successful or client-error responses, not 5xx server errors
        if 200 <= response.status_code < 500:
            cache.set(
                cache_key,
                {
                    'content': response.content,
                    'status': response.status_code,
                    'content_type': response.get('Content-Type', 'application/json'),
                },
                timeout=86400,
            )  # 24 hours

        return response
