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

from abc import ABC, abstractmethod


class PaymentGateway(ABC):
    """Abstract payment provider. Plugins subclass + register an instance."""

    slug: str = ''
    label: str = ''
    supports_refunds: bool = True
    supports_webhooks: bool = True

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

    def enabled_gateways(self) -> list[PaymentGateway]:
        """Registered gateways whose Settings → Payments toggle is on.

        Read-only convenience for surfaces that want to honour the enable
        flag (e.g. a payment-method picker). The checkout/payment-intent
        path still uses ``default()`` — wiring this into checkout is
        deliberately deferred (see docs/plans/morph-backlog-2026-06.md).
        """
        from plugins.installed.payments.models import is_enabled

        return [g for g in self._gateways.values() if is_enabled(g.slug)]

    def default(self) -> PaymentGateway | None:
        # Prefer 'stripe' if registered, else first registered, else None.
        return self._gateways.get('stripe') or (next(iter(self._gateways.values()), None))


gateway_registry = GatewayRegistry()
