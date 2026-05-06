"""
Morpheus CMS — Hook Registry
The event bus that connects all plugins without tight coupling.
"""
import logging
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger('morpheus.hooks')


class HookRegistry:
    """
    Lightweight ordered event bus.

    Usage:
        # Register (in plugin.ready()):
        hook_registry.register('order.placed', handler, priority=10)

        # Fire (in service layer):
        hook_registry.fire('order.placed', order=order)

        # Filter (transform a value through a chain):
        price = hook_registry.filter('product.price', value=base_price, product=product)
    """

    def __init__(self):
        # { event_name: [ (priority, handler), ... ] }
        self._handlers: dict[str, list[tuple[int, Callable]]] = defaultdict(list)

    def register(self, event: str, handler: Callable, priority: int = 50) -> None:
        """Register a handler for an event. Lower priority = runs first."""
        self._handlers[event].append((priority, handler))
        self._handlers[event].sort(key=lambda x: x[0])
        logger.debug(f"Hook registered: {event} → {handler.__qualname__} (priority={priority})")

    def unregister(self, event: str, handler: Callable) -> None:
        """Remove a handler from an event."""
        self._handlers[event] = [
            (p, h) for p, h in self._handlers[event] if h != handler
        ]

    def fire(self, event: str, **kwargs: Any) -> list[Any]:
        """
        Fire an event. All registered handlers are called in priority order.
        Also dispatches asynchronous HTTP webhooks to Remote Plugins.
        Returns list of non-None return values from handlers.
        """
        results: list[Any] = []

        self._dispatch_remote(event, kwargs)

        for _priority, handler in self._handlers.get(event, []):
            try:
                result = handler(**kwargs)
            except Exception as e:  # noqa: BLE001 — handler isolation, logged with traceback
                logger.error(
                    "Hook handler error: event=%s handler=%s error=%s",
                    event, handler.__qualname__, e,
                    exc_info=True,
                )
                continue
            if result is not None:
                results.append(result)
        return results

    def filter(self, event: str, value: Any, **kwargs: Any) -> Any:
        """
        Filter an event — each handler receives the (potentially modified) value
        and returns a new value. Builds a transformation pipeline.
        """
        for _priority, handler in self._handlers.get(event, []):
            try:
                result = handler(value=value, **kwargs)
            except Exception as e:  # noqa: BLE001 — filter isolation, logged with traceback
                logger.error(
                    "Hook filter error: event=%s handler=%s error=%s",
                    event, handler.__qualname__, e,
                    exc_info=True,
                )
                continue
            if result is not None:
                value = result
        return value

    # ── Internal helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _serialize_payload(kwargs: dict[str, Any]) -> dict[str, Any]:
        import decimal
        import json as _json
        from django.core.serializers.json import DjangoJSONEncoder
        from django.db import models
        from django.db.models.query import QuerySet

        class WebhookEncoder(DjangoJSONEncoder):
            def default(self, o):
                if isinstance(o, models.Model):
                    return {'id': str(o.pk), 'model': o.__class__.__name__}
                if isinstance(o, QuerySet):
                    return [
                        {'id': str(obj.pk), 'model': obj.__class__.__name__}
                        for obj in o
                    ]
                if isinstance(o, decimal.Decimal):
                    return str(o)
                if hasattr(o, 'amount') and hasattr(o, 'currency'):  # MoneyField
                    return {'amount': str(o.amount), 'currency': str(o.currency)}
                return super().default(o)

        return _json.loads(_json.dumps(kwargs, cls=WebhookEncoder))

    def _dispatch_remote(self, event: str, kwargs: dict[str, Any]) -> None:
        """
        Serialize the event payload and dispatch to (a) any subscribed
        WebhookEndpoints via Celery and (b) the transactional outbox for the
        NATS publisher. Designed to fail-soft: a broken webhook config must
        never break local handlers.
        """
        try:
            from django.apps import apps
            if not apps.ready:
                return
            from core.models import OutboxEvent, WebhookEndpoint
            from core.tasks import dispatch_webhook
        except ImportError as e:  # apps not loaded yet (e.g. during settings import)
            logger.debug("Skipping remote dispatch for %s — apps not ready: %s", event, e)
            return

        try:
            payload = self._serialize_payload(kwargs)
        except (TypeError, ValueError) as e:
            logger.error(
                "Failed to serialize payload for event=%s: %s", event, e, exc_info=True,
            )
            return

        try:
            endpoints = WebhookEndpoint.objects.filter(is_active=True)
            for endpoint in endpoints:
                if event in endpoint.events or '*' in endpoint.events:
                    dispatch_webhook.delay(endpoint.url, endpoint.secret, event, payload)
        except Exception as e:  # noqa: BLE001 — DB outage must not break local handlers
            logger.warning("Webhook dispatch failed for %s: %s", event, e, exc_info=True)

        try:
            OutboxEvent.objects.create(event_type=event, payload=payload)
        except Exception as e:  # noqa: BLE001 — outbox failure logged, do not abort
            logger.warning("Outbox write failed for %s: %s", event, e, exc_info=True)

    def has_handlers(self, event: str) -> bool:
        return bool(self._handlers.get(event))

    def list_handlers(self, event: str) -> list[str]:
        return [h.__qualname__ for _, h in self._handlers.get(event, [])]

    def clear(self, event: str | None = None) -> None:
        """Clear handlers. If event is None, clears all."""
        if event:
            self._handlers.pop(event, None)
        else:
            self._handlers.clear()


# Global singleton — import this everywhere
hook_registry = HookRegistry()


# ── Standard Morph events (for IDE autocompletion & discoverability) ──────────

class MorpheusEvents:
    """Catalogue of all built-in hook events."""

    # Orders
    ORDER_PLACED = 'order.placed'
    ORDER_CONFIRMED = 'order.confirmed'
    ORDER_PAID = 'order.paid'
    ORDER_CANCELLED = 'order.cancelled'
    ORDER_FULFILLED = 'order.fulfilled'

    # Payments
    PAYMENT_CAPTURED = 'payment.captured'
    PAYMENT_FAILED = 'payment.failed'
    PAYMENT_REFUNDED = 'payment.refunded'

    # Cart
    CART_CREATED = 'cart.created'
    CART_UPDATED = 'cart.updated'
    CART_ABANDONED = 'cart.abandoned'

    # Filters
    CART_CALCULATE_TOTAL = 'cart.calculate_total'   # filter
    CART_CALCULATE_BREAKDOWN = 'cart.calculate_breakdown'  # filter
    PRODUCT_CALCULATE_PRICE = 'product.calculate_price'  # filter

    # Catalog
    PRODUCT_VIEWED = 'product.viewed'
    PRODUCT_CREATED = 'product.created'
    PRODUCT_UPDATED = 'product.updated'
    CATEGORY_UPDATED = 'category.updated'

    # Customers
    CUSTOMER_REGISTERED = 'customer.registered'
    CUSTOMER_LOGIN = 'customer.login'

    # Inventory
    PRODUCT_LOW_STOCK = 'product.low_stock'
    PRODUCT_OUT_OF_STOCK = 'product.out_of_stock'

    # Search
    SEARCH_PERFORMED = 'search.performed'

    # AI
    AI_DESCRIPTION_GENERATED = 'ai.description_generated'
    AI_RECOMMENDATION_REQUESTED = 'ai.recommendation_requested'
