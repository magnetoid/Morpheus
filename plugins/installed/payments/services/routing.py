"""Payment-gateway routing for checkout.

Single entry point that resolves the shopper-selected gateway and asks it
to create a payment intent. This is the ONLY place the checkout flow picks
a gateway — everything else stays on the abstraction.

Safety contract (this is the live money path):

* Stripe is the default. An unset / unknown / disabled slug resolves to
  ``gateway_registry.default()`` (stripe when registered) — never an error
  at checkout.
* The submitted slug is validated server-side against
  ``enabled_gateways()``; a client may not pick a disabled gateway.
* Fail-soft: any resolution error falls back to the default gateway and
  logs, rather than 500-ing checkout.
* When stripe is the resolved gateway the call is byte-for-byte the old
  ``PaymentService.create_payment_intent(order)`` — the StripeGateway is a
  thin pass-through, so the live path is unchanged.

The resolved slug is recorded on ``order.payment_gateway`` so refunds and
reconciliation route back through the same gateway.
"""

# ruff: noqa: PLC0415
# Inline imports avoid a routing.py ↔ gateway.py ↔ models.py cycle at load.
from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.payments.routing')


def picker_gateways(user=None, ships: bool = True) -> list[dict]:
    """Presentation-ready list of enabled gateways for the checkout picker.

    Each entry: ``{slug, label, capability, instructions, is_default}``.
    ``capability`` is a short shopper-facing hint; ``instructions`` is the
    gateway's configured copy (``PaymentGatewayConfig.config['instructions']``,
    e.g. bank-transfer / cash-on-delivery notes) or ''. Empty list if no
    gateway is registered/enabled — the caller then hides the picker and
    checkout falls through to ``default()``. ``ships=False``: the cart has a
    line that does not ship, so cash on delivery is left out.
    """
    from plugins.installed.payments.gateway import gateway_registry
    from plugins.installed.payments.models import PaymentGatewayConfig

    default = gateway_registry.default(user=user, ships=ships)
    default_slug = default.slug if default else ''

    # One query for all configured instruction blobs (avoids N round-trips).
    instructions_by_slug: dict[str, str] = {}
    try:
        for row in PaymentGatewayConfig.objects.all():
            note = (row.config or {}).get('instructions') if isinstance(row.config, dict) else ''
            if note:
                instructions_by_slug[row.slug] = str(note)
    except Exception:  # noqa: BLE001 — config table missing/unmigrated: no notes
        instructions_by_slug = {}

    out: list[dict] = []
    for g in gateway_registry.enabled_gateways(user=user, ships=ships):
        if g.supports_webhooks:
            capability = 'Pay securely online'
        elif g.supports_refunds:
            capability = 'Sandbox / test payment'
        else:
            capability = 'Pay offline'
        out.append(
            {
                'slug': g.slug,
                'label': g.label,
                'capability': capability,
                'instructions': instructions_by_slug.get(g.slug, ''),
                'is_default': g.slug == default_slug,
            }
        )
    return out


def resolve_gateway(selected_slug: str | None, *, user=None, ships: bool = True):
    """Return the gateway to charge for ``selected_slug``.

    Falls back to ``gateway_registry.default()`` when the slug is empty,
    unknown, or not in ``enabled_gateways()`` (cash on delivery is not, for
    an order with a line that does not ship). Never raises — a resolution
    problem must not break checkout.
    """
    from plugins.installed.payments.gateway import gateway_registry

    default = gateway_registry.default(user=user, ships=ships)
    slug = (selected_slug or '').strip()
    if not slug:
        return default
    try:
        enabled = {g.slug for g in gateway_registry.enabled_gateways(user=user, ships=ships)}
    except Exception:  # noqa: BLE001 — DB hiccup must not break checkout
        logger.warning('routing: enabled_gateways() failed; using default', exc_info=True)
        return default
    if slug not in enabled:
        logger.info('routing: slug %r not enabled; falling back to default', slug)
        return default
    return gateway_registry.get(slug) or default


def create_payment_intent_for(order, selected_slug: str | None = None) -> dict:
    """Create a payment intent for ``order`` via the chosen gateway.

    Records the resolved gateway slug on ``order.payment_gateway`` and
    returns the gateway's result dict (``{success, client_secret?,
    transaction_id?, error?, ...}``).
    """
    customer = getattr(order, 'customer', None)
    ships = order_ships(order)
    gateway = resolve_gateway(selected_slug, user=customer, ships=ships)
    if gateway is None:
        if not ships and resolve_gateway(selected_slug, user=customer) is not None:
            # Only cash on delivery is set up, and the order has a download in it.
            logger.warning('routing: only cash on delivery is set up; a download needs another way')
            return {
                'success': False,
                'error': "Downloads can't be paid in cash on delivery, and this store has "
                'no other way to pay for them yet. Please contact us to complete your order.',
            }
        # Nothing is switched on AND set up (no keys, no bank details, COD off).
        logger.error('routing: no payment method is set up; checkout cannot take payment')
        return {
            'success': False,
            'error': "This store can't take payments right now. Please contact us to "
            'complete your order.',
        }

    _record_gateway_slug(order, gateway.slug)

    try:
        return gateway.create_payment_intent(order=order)
    except Exception as e:  # noqa: BLE001 — surface as a retryable failure, don't 500
        logger.warning('routing: %s.create_payment_intent failed: %s', gateway.slug, e)
        return {'success': False, 'error': str(e)[:300]}


def order_ships(order) -> bool:
    """Whether every line of ``order`` goes out in a parcel (orders' rule). An
    order whose lines cannot be read counts as shipping, which only keeps cash
    on delivery offered as before."""
    from plugins.installed.orders.services import line_ships

    try:
        return all(line_ships(item) for item in order.items.all())
    except Exception:  # noqa: BLE001 — an unsaved order has no lines to read
        return True


def _record_gateway_slug(order, slug: str) -> None:
    """Persist the chosen gateway slug on the order (best-effort).

    Skipped when the order isn't saved (no pk) — the standalone
    ``createPaymentIntent`` path always operates on a saved Order, and
    ``complete_order`` saves the order before this runs.
    """
    if not slug or getattr(order, 'pk', None) is None:
        return
    if getattr(order, 'payment_gateway', None) == slug:
        return
    try:
        order.payment_gateway = slug
        order.save(update_fields=['payment_gateway'])
    except Exception:  # noqa: BLE001 — recording is not worth failing a charge over
        logger.warning('routing: could not record gateway slug on order', exc_info=True)
