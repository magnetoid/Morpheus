"""HTTP surface for the payments plugin.

* ``/payments/webhooks/stripe/`` — Stripe webhook receiver
  (``PaymentService.process_webhook`` verifies + updates + fires ORDER_PAID).
* ``/payments/paypal/return|cancel/`` — the shopper lands here after
  approving/cancelling on PayPal; return captures + marks the order paid.
* ``/payments/webhooks/paypal/`` — PayPal webhook receiver (belt-and-braces
  for missed returns; verified via PayPal's verify-webhook-signature API).
"""

from __future__ import annotations

import logging

from morpheus.app.views import (
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
    """Stripe POSTs raw JSON; we verify the signature inside PaymentService.

    Rate-limited per-IP (1000/min) so an attacker flooding bogus
    signatures can't burn CPU on HMAC + DB lookups. Stripe's actual
    cadence is ~100/min from their IP range — comfortably under.
    """
    from core.utils.rate_limit import check_and_consume  # noqa: PLC0415

    ip = request.META.get('HTTP_CF_CONNECTING_IP') or request.META.get('REMOTE_ADDR', 'unknown')
    if not check_and_consume(key=f'stripe_webhook:{ip}', max_per_window=1000, window_seconds=60):
        return HttpResponse(status=429)

    sig = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    if not sig:
        return HttpResponseBadRequest('missing stripe signature header')
    try:
        from plugins.installed.payments.services.stripe import PaymentService  # noqa: PLC0415

        PaymentService.process_webhook(request.body, sig)
    except Exception as e:  # noqa: BLE001 — bad payload / bad signature / unknown event
        logger.warning('stripe webhook rejected: %s', e)
        return HttpResponseBadRequest(str(e)[:200])
    return JsonResponse({'ok': True})


# ── PayPal ────────────────────────────────────────────────────────────────────


def _confirmation_redirect(order):
    """Redirect to the order-confirmation page, guest-safe via public_token."""
    from morpheus.app.views import redirect  # noqa: PLC0415

    url = f'/order/confirmation/{order.order_number}/'
    token = getattr(order, 'public_token', '') or ''
    if token:
        url = f'{url}?token={token}'
    return redirect(url)


def paypal_return(request: HttpRequest) -> HttpResponse:
    """The shopper approved on PayPal — capture and mark the order paid.

    PayPal appends ``?token=<paypal_order_id>`` to the return URL; the
    matching pending PaymentTransaction locates our order. Idempotent: a
    refresh re-runs capture (PayPal answers ORDER_ALREADY_CAPTURED-ish
    errors) but ``mark_order_paid`` fires ORDER_PAID at most once.
    """
    from morpheus.app.views import redirect  # noqa: PLC0415
    from plugins.installed.payments.models import PaymentTransaction  # noqa: PLC0415
    from plugins.installed.payments.services import paypal  # noqa: PLC0415

    paypal_order_id = (request.GET.get('token') or '').strip()
    if not paypal_order_id:
        return redirect('/checkout/')

    tx = (
        PaymentTransaction.objects.filter(
            provider='paypal', provider_transaction_id=paypal_order_id
        )
        .select_related('order')
        .first()
    )
    if tx is None:
        logger.warning('paypal return: no transaction for %s', paypal_order_id)
        return redirect('/checkout/')

    if tx.status != PaymentTransaction.Status.SUCCEEDED:
        result = paypal.capture_order(paypal_order_id)
        if not result.get('success'):
            logger.warning(
                'paypal return: capture failed for %s: %s',
                paypal_order_id,
                result.get('error'),
            )
            from django.contrib import messages  # noqa: PLC0415

            messages.error(request, 'PayPal payment could not be completed. Please try again.')
            return redirect('/checkout/')
        paypal.mark_order_paid(paypal_order_id)

    return _confirmation_redirect(tx.order)


def apple_pay_domain_association(request: HttpRequest) -> HttpResponse:
    """Serve Stripe's Apple Pay domain-verification file.

    Apple Pay in the Payment Element requires
    ``/.well-known/apple-developer-merchantid-domain-association`` to serve
    Stripe's canonical association file. It's identical for every Stripe
    merchant, so we proxy stripe.com's copy with a 24h cache instead of
    vendoring a blob that Stripe may rotate.
    """
    import requests  # noqa: PLC0415
    from django.core.cache import cache  # noqa: PLC0415

    cache_key = 'payments:apple_pay_domain_assoc'
    content = cache.get(cache_key)
    if content is None:
        try:
            resp = requests.get(
                'https://stripe.com/files/apple-pay/apple-developer-merchantid-domain-association',
                timeout=10,
            )
            resp.raise_for_status()
            content = resp.content
            cache.set(cache_key, content, 60 * 60 * 24)
        except Exception as e:  # noqa: BLE001
            logger.warning('apple pay domain association fetch failed: %s', e)
            return HttpResponse(status=404)
    return HttpResponse(content, content_type='text/plain')


def paypal_cancel(request: HttpRequest) -> HttpResponse:
    """The shopper backed out on PayPal — return to checkout, cart intact."""
    from django.contrib import messages  # noqa: PLC0415

    from morpheus.app.views import redirect  # noqa: PLC0415

    messages.info(request, 'PayPal payment was cancelled — you have not been charged.')
    return redirect('/checkout/')


@csrf_exempt
@require_POST
def paypal_webhook(request: HttpRequest) -> HttpResponse:
    """PayPal webhook receiver — backstop when the shopper never returns.

    Signature is verified server-side against PayPal's
    verify-webhook-signature API (needs ``paypal_webhook_id`` configured).
    Only PAYMENT.CAPTURE.COMPLETED is acted on; everything else is 200-OK'd
    so PayPal stops retrying. Rate-limited like the Stripe receiver.
    """
    from core.utils.rate_limit import check_and_consume  # noqa: PLC0415
    from plugins.installed.payments.services import paypal  # noqa: PLC0415

    ip = request.META.get('HTTP_CF_CONNECTING_IP') or request.META.get('REMOTE_ADDR', 'unknown')
    if not check_and_consume(key=f'paypal_webhook:{ip}', max_per_window=1000, window_seconds=60):
        return HttpResponse(status=429)

    event = paypal.verify_webhook(request.headers, request.body)
    if event is None:
        return HttpResponseBadRequest('webhook verification failed')

    if event.get('event_type') == 'PAYMENT.CAPTURE.COMPLETED':
        resource = event.get('resource') or {}
        paypal_order_id = ((resource.get('supplementary_data') or {}).get('related_ids') or {}).get(
            'order_id', ''
        )
        if paypal_order_id:
            paypal.mark_order_paid(paypal_order_id)
        else:
            logger.warning('paypal webhook: capture event without related order id')
    return JsonResponse({'ok': True})
