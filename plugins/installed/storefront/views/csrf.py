"""The visitor's own CSRF token, for forms on edge-cached pages.

A storefront page the CDN caches carries the token of whoever filled the cache
and sets no cookie, so a form on it answered 403 for everyone else (Montenegro's
cookie banner, 2026-10-13). `storefront/csrf-refresh.js` fetches this and writes
the visitor's token into every form.
"""

from __future__ import annotations

from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET


@require_GET
@never_cache
@ensure_csrf_cookie
def csrf_token_view(request):
    return JsonResponse({'token': get_token(request)})
