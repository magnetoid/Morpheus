"""CSRF for endpoints that serve both API clients and the dashboard.

A JSON endpoint called by API clients with a Bearer token cannot carry a CSRF
token, so it was ``@csrf_exempt`` — and it also accepted a plain staff session,
which made it a target for a cross-site POST protected only by the browser's
SameSite default. The exemption belongs to the Bearer request, not to the URL:
with ``Authorization: Bearer`` the check is skipped (the token is the proof);
any other request goes through Django's normal CSRF check.
"""

from __future__ import annotations

from functools import wraps

from django.views.decorators.csrf import csrf_exempt, csrf_protect


def csrf_exempt_for_bearer(view):
    exempt = csrf_exempt(view)
    protected = csrf_protect(view)

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if auth.startswith('Bearer '):
            return exempt(request, *args, **kwargs)
        return protected(request, *args, **kwargs)

    # Django's CsrfViewMiddleware consults this flag on the view it dispatches
    # to; the inner decorators decide per request.
    wrapped.csrf_exempt = True
    return wrapped
