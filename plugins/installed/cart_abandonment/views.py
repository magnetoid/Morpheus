"""Public cart-recovery routes — the one-click unsubscribe endpoint."""

from __future__ import annotations

from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def unsubscribe_view(request, token: str):
    """One-click cart-recovery unsubscribe.

    GET is the human clicking the email-footer link; POST is the RFC 8058
    ``List-Unsubscribe-Post`` flow (Gmail/Yahoo hit the URL with a bare POST,
    no CSRF token — the unguessable token IS the auth, and the action only ever
    *adds* a suppression, so it's idempotent and safe)."""
    from plugins.installed.cart_abandonment.services import suppress_from_token

    email = suppress_from_token(token)
    return render(
        request,
        'cart_abandonment/unsubscribed.html',
        {'ok': email is not None, 'email': email or ''},
        status=200 if email is not None else 404,
    )
