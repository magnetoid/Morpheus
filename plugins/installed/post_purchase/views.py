"""Public NPS feedback view.

Single endpoint at /post-purchase/nps/<token>/ — opened from the survey
email. No login required; token is a TimestampSigner sig over the order
pk valid for 30 days.
"""

from __future__ import annotations

import logging

from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger('morpheus.post_purchase.views')

TOKEN_MAX_AGE_SECONDS = 30 * 24 * 60 * 60  # 30 days


@require_http_methods(['GET', 'POST'])
def nps_form(request: HttpRequest, token: str) -> HttpResponse:
    order = _resolve_order_or_none(token)
    if order is None:
        return render(request, 'post_purchase/nps_invalid.html', status=410)

    from plugins.installed.post_purchase.models import NPSResponse  # noqa: PLC0415

    existing = NPSResponse.objects.filter(order=order).first()
    if request.method == 'POST':
        try:
            score = int(request.POST.get('score', '-1'))
        except (TypeError, ValueError):
            score = -1
        if not (0 <= score <= 10):
            return render(
                request,
                'post_purchase/nps_form.html',
                {
                    'order': order,
                    'token': token,
                    'existing': existing,
                    'error': 'Pick a score between 0 and 10.',
                },
                status=400,
            )
        comment = (request.POST.get('comment') or '')[:1000]
        customer = request.user if request.user.is_authenticated else None
        NPSResponse.objects.update_or_create(
            order=order,
            defaults={'score': score, 'comment': comment, 'customer': customer},
        )
        return redirect('post_purchase:nps_thanks')

    return render(
        request,
        'post_purchase/nps_form.html',
        {'order': order, 'token': token, 'existing': existing},
    )


def nps_thanks(request: HttpRequest) -> HttpResponse:
    return render(request, 'post_purchase/nps_thanks.html')


def _resolve_order_or_none(token: str):
    """Verify signed token → Order instance, or None if invalid/expired."""
    try:
        order_pk = TimestampSigner(salt='post_purchase.nps').unsign(
            token, max_age=TOKEN_MAX_AGE_SECONDS
        )
    except (BadSignature, SignatureExpired):
        return None

    try:
        from plugins.installed.orders.models import Order  # noqa: PLC0415

        return Order.objects.filter(pk=order_pk).first()
    except Exception:  # noqa: BLE001
        logger.exception('post_purchase: order lookup failed for token')
        return None


@csrf_exempt
@never_cache
@require_http_methods(['GET', 'POST'])
def unsubscribe(request: HttpRequest, token: str) -> HttpResponse:
    """GET asks; POST (the button, or a mail client's one-click) records it.

    No CSRF token: a mail client posts with none, the signed token is the
    authority, and the only thing a POST can do is add this one address.
    """
    from morpheus.app.views import render as page  # noqa: PLC0415
    from plugins.installed.post_purchase.unsubscribe import (  # noqa: PLC0415
        email_from_token,
        opt_out,
    )

    email = email_from_token(token)
    if email is None:
        raise Http404('Unknown unsubscribe link')
    done = request.method == 'POST'
    if done:
        opt_out(email)
    return page(
        request,
        'post_purchase/unsubscribe.html',
        {
            'email': email,
            'done': done,
            'seo_title': 'Unsubscribe',
            'seo_noindex_reason': 'an unsubscribe page',
        },
    )
