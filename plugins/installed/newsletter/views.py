"""Public newsletter endpoints — subscribe (popup/form POST) + confirm /
unsubscribe (one-click GET links from the emails)."""

from __future__ import annotations

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


@csrf_exempt
@require_http_methods(['POST'])
def subscribe_view(request):
    """Capture an email from a popup/form. Returns JSON for the popup JS.

    CSRF-exempt: a public, unauthenticated capture (like the analytics beacon)
    — it only creates a PENDING row, and nothing is mailable until the
    double-opt-in link is clicked, so there's no state-changing risk to forge.
    Per-IP rate-limited: each call writes a row and sends a confirmation
    email, so an unthrottled loop is a mail-amplification vector.
    """
    from core.utils.rate_limit import RateLimitExceeded, check_and_consume  # noqa: PLC0415

    ip = request.META.get('REMOTE_ADDR', '') or 'unknown'
    try:
        check_and_consume(key=f'newsletter:subscribe:{ip}', max_per_window=10, window_seconds=60)
    except RateLimitExceeded:
        return JsonResponse({'ok': False, 'error': 'Too many attempts.'}, status=429)
    from plugins.installed.newsletter.services import subscribe

    email = (request.POST.get('email') or '').strip()
    source = (request.POST.get('source') or 'popup').strip()[:12]
    customer = request.user if getattr(request.user, 'is_authenticated', False) else None
    sub, _created = subscribe(email, source=source, customer=customer)
    if sub is None:
        return JsonResponse({'ok': False, 'error': 'Enter a valid email address.'}, status=400)
    return JsonResponse(
        {'ok': True, 'status': sub.status, 'message': 'Check your inbox to confirm.'}
    )


@require_http_methods(['GET'])
def confirm_view(request, token: str):
    from plugins.installed.newsletter.services import confirm

    sub = confirm(token)
    return render(
        request,
        'newsletter/confirm.html',
        {'ok': sub is not None, 'email': getattr(sub, 'email', '')},
        status=200 if sub is not None else 404,
    )


@require_http_methods(['GET'])
def unsubscribe_view(request, token: str):
    from plugins.installed.newsletter.services import unsubscribe

    sub = unsubscribe(token)
    return render(
        request,
        'newsletter/unsubscribed.html',
        {'ok': sub is not None, 'email': getattr(sub, 'email', '')},
        status=200 if sub is not None else 404,
    )
