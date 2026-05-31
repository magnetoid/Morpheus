"""Persists the visitor cookie set lazily by services.visitor_id_for.

variant_for() sets `request._set_visitor_cookie` when it had to mint a
new id. This middleware attaches it to the response so the next
request from the same browser hashes into the same variant.
"""

from __future__ import annotations

from plugins.installed.experiments.services import COOKIE_MAX_AGE, VISITOR_COOKIE


class ExperimentsCookieMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        new_cookie = getattr(request, '_set_visitor_cookie', None)
        if new_cookie and VISITOR_COOKIE not in request.COOKIES:
            response.set_cookie(
                VISITOR_COOKIE,
                new_cookie,
                max_age=COOKIE_MAX_AGE,
                samesite='Lax',
                secure=not getattr(request, 'is_secure', lambda: True)(),
                httponly=True,
            )
        return response
