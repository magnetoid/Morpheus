"""HTTP surface for the payments plugin.

Currently exposes one endpoint: the Stripe webhook receiver. Stripe is
configured in its dashboard to POST to ``/payments/webhooks/stripe/``;
``PaymentService.process_webhook`` verifies the signature, updates the
matching ``PaymentTransaction``, and fires ``events.ORDER_PAID``.
"""
from __future__ import annotations

import logging

from morpheus.views import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
    csrf_exempt,
    require_POST,
)

logger = logging.getLogger('morpheus.payments.webhooks')


@csrf_exempt
@require_POST
def stripe_webhook(request: HttpRequest) -> HttpResponse:
    """Stripe POSTs raw JSON; we verify the signature inside PaymentService."""
    sig = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    if not sig:
        return HttpResponseBadRequest('missing stripe signature header')
    try:
        from plugins.installed.payments.services.stripe import PaymentService
        PaymentService.process_webhook(request.body, sig)
    except Exception as e:  # noqa: BLE001 — bad payload / bad signature / unknown event
        logger.warning('stripe webhook rejected: %s', e)
        return HttpResponseBadRequest(str(e)[:200])
    return JsonResponse({'ok': True})
