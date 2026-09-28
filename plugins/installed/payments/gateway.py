"""
Payment gateway abstraction.

`PaymentGateway` is the ABC every payment provider implements. The
`gateway_registry` collects providers; the rest of the platform talks to
the abstraction, not Stripe directly.

Adapter shape:

    class FooGateway(PaymentGateway):
        slug = 'foo'
        label = 'Foo Pay'

        def create_payment_intent(self, *, order, **kw): ...
        def capture(self, *, transaction, **kw): ...
        def refund(self, *, transaction, amount, **kw): ...
        def webhook_verify(self, *, body, signature): ...

Plugins register their gateway in `ready()`:

    from plugins.installed.payments.gateway import gateway_registry
    gateway_registry.register(StripeGateway())
"""

# ruff: noqa: PLC0415
# Inline import in enabled_gateways() is intentional — avoids a
# gateway.py ↔ models.py import cycle at module load.
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger('morpheus.payments')


class PaymentGateway(ABC):
    """Abstract payment provider. Plugins subclass + register an instance."""

    slug: str = ''
    label: str = ''
    supports_refunds: bool = True
    supports_webhooks: bool = True
    # Offered only to staff (a sandbox method a merchant uses to test checkout).
    staff_only: bool = False

    def is_configured(self) -> bool:
        """Whether this gateway can take a payment right now.

        A gateway without its credentials (no Stripe keys, no bank details)
        must not be offered at checkout: shoppers would pick it, or get it as
        the default, and hit an error at the payment step.
        """
        return True

    @abstractmethod
    def create_payment_intent(self, *, order, **kwargs) -> dict:
        """Return {success: bool, client_secret?: str, transaction_id?: str, error?: str}."""

    def capture(self, *, transaction, **kwargs) -> dict:
        """Best-effort capture for delayed-capture providers."""
        return {'success': True}

    def refund(self, *, transaction, amount, **kwargs) -> dict:
        return {'success': False, 'error': 'Not implemented'}

    def webhook_verify(self, *, body: bytes, signature: str) -> dict | None:
        """Return parsed webhook event dict, or None if signature invalid."""
        return None


class GatewayRegistry:
    def __init__(self) -> None:
        self._gateways: dict[str, PaymentGateway] = {}

    def register(self, gateway: PaymentGateway) -> None:
        if not gateway.slug:
            return
        self._gateways[gateway.slug] = gateway

    def unregister(self, slug: str) -> None:
        self._gateways.pop(slug, None)

    def get(self, slug: str) -> PaymentGateway | None:
        return self._gateways.get(slug)

    def all(self) -> list[PaymentGateway]:
        return list(self._gateways.values())

    def enabled_gateways(self, *, user=None) -> list[PaymentGateway]:
        """Registered gateways that are switched on, set up, and offered to ``user``.

        Backs the checkout payment-method picker AND server-side
        validation of the submitted slug (see
        ``payments.services.routing``): checkout resolves the chosen
        gateway against this list and falls back to ``default()`` for an
        empty / unknown / disabled slug.
        """
        from plugins.installed.payments.models import is_enabled

        is_staff = bool(getattr(user, 'is_staff', False))
        return [
            g
            for g in self._gateways.values()
            if is_enabled(g.slug) and (is_staff or not g.staff_only) and _configured(g)
        ]

    def default(self, *, user=None) -> PaymentGateway | None:
        """Stripe when it can take payments, else the first working method.

        A staff-only method is the default only when nothing else is offered;
        ``None`` means the store cannot take a payment at all.
        """
        offered = self.enabled_gateways(user=user)
        for g in offered:
            if g.slug == 'stripe':
                return g
        return next((g for g in offered if not g.staff_only), None) or (
            offered[0] if offered else None
        )


def _configured(gateway: PaymentGateway) -> bool:
    try:
        return bool(gateway.is_configured())
    except Exception:  # noqa: BLE001 — a broken check means "not ready", never a 500
        logger.warning('payments: %s.is_configured() failed', gateway.slug, exc_info=True)
        return False


gateway_registry = GatewayRegistry()
