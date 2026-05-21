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
        # { event_name: [ (priority, handler, mode), ... ] }
        # mode is 'sync' (default, runs in-request) or 'async' (deferred to
        # Celery so the request can return immediately).
        self._handlers: dict[str, list[tuple[int, Callable, str]]] = defaultdict(list)

    def register(
        self,
        event: str,
        handler: Callable,
        priority: int = 50,
        mode: str = 'sync',
    ) -> None:
        """Register a handler for an event. Lower priority = runs first.

        ``mode='sync'`` (default): handler runs in-request, in priority order.
        ``mode='async'``: handler runs on a Celery worker after the request
        returns. Use for analytics, embeddings, marketing emails, anything
        not in the critical path. Critical side effects (inventory decrement,
        order state transitions, fulfillment) must stay sync.

        Note: async mode requires JSON-serialisable kwargs. Pass model PKs
        + class names, not raw model instances. The async dispatcher
        re-resolves them inside the worker. Non-serialisable kwargs cause
        the handler to fall back to sync execution with a WARNING log.
        """
        if mode not in ('sync', 'async'):
            raise ValueError(f"Invalid hook mode {mode!r} — must be 'sync' or 'async'.")
        self._handlers[event].append((priority, handler, mode))
        self._handlers[event].sort(key=lambda x: x[0])
        logger.debug(
            "Hook registered: %s → %s (priority=%d, mode=%s)",
            event, handler.__qualname__, priority, mode,
        )

    def unregister(self, event: str, handler: Callable) -> None:
        """Remove a handler from an event."""
        self._handlers[event] = [
            entry for entry in self._handlers[event] if entry[1] != handler
        ]

    def fire(self, event: str, **kwargs: Any) -> list[Any]:
        """
        Fire an event. All registered handlers are called in priority order.
        Sync handlers run in-request; async handlers are enqueued to Celery.
        Also dispatches asynchronous HTTP webhooks to Remote Plugins.
        Returns list of non-None return values from SYNC handlers only
        (async handlers return their results to the worker, not the caller).
        """
        results: list[Any] = []

        self._dispatch_remote(event, kwargs)

        for entry in self._handlers.get(event, []):
            # Backwards-compat: pre-mode tuples were (priority, handler).
            # Unpack defensively so plugins registered the old way still work.
            if len(entry) == 3:
                _priority, handler, mode = entry
            else:
                _priority, handler = entry
                mode = 'sync'

            if mode == 'async':
                self._enqueue_async(event, handler, kwargs)
                continue

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

    def _enqueue_async(self, event: str, handler: Callable, kwargs: dict) -> None:
        """Send a hook-handler invocation to Celery.

        Falls back to sync execution if Celery is unavailable or if the
        kwargs aren't JSON-serialisable — degrading gracefully is more
        important than purity.
        """
        try:
            from core.tasks import run_hook_handler_async
            handler_path = f'{handler.__module__}.{handler.__qualname__}'
            # Best-effort serialisation check — bail to sync if anything's
            # non-trivial (Model instances, Decimal, datetime).
            serialisable = self._serialize_payload(kwargs)
            run_hook_handler_async.delay(event, handler_path, serialisable)
        except Exception as exc:  # noqa: BLE001 — never break the fire path
            logger.warning(
                'async hook dispatch failed for %s → %s; falling back to sync: %s',
                event, handler.__qualname__, exc,
            )
            try:
                handler(**kwargs)
            except Exception as e:  # noqa: BLE001
                logger.error(
                    'async-fallback-sync hook handler error: event=%s handler=%s error=%s',
                    event, handler.__qualname__, e, exc_info=True,
                )

    def filter(self, event: str, value: Any, **kwargs: Any) -> Any:
        """
        Filter an event — each handler receives the (potentially modified) value
        and returns a new value. Builds a transformation pipeline.

        Filters are ALWAYS sync — the value has to flow through synchronously
        for the caller to receive the transformed result. async mode on a
        filter is rejected at registration time? — not yet; for now we
        silently treat any handler registered for a filter event as sync.
        """
        for entry in self._handlers.get(event, []):
            if len(entry) == 3:
                _priority, handler, _mode = entry
            else:
                _priority, handler = entry
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
        out: list[str] = []
        for entry in self._handlers.get(event, []):
            handler = entry[1]
            out.append(handler.__qualname__)
        return out

    def clear(self, event: str | None = None) -> None:
        """Clear handlers. If event is None, clears all."""
        if event:
            self._handlers.pop(event, None)
        else:
            self._handlers.clear()


# Global singleton — import this everywhere
hook_registry = HookRegistry()


# ── Standard Morph events ─────────────────────────────────────────────────────
#
# The catalogue below is the canonical contract for every built-in hook
# event: when it fires, what kwargs flow through, and (for filter events)
# what `value` is. Subscribers depend on these names + payload shapes —
# don't rename in place, deprecate and add new constants.
#
# Two flavours:
#   * **fire** events     — fan-out, no return value used.
#                            Subscribers run for side effects only.
#   * **filter** events   — pipeline, each handler returns a (possibly
#                            modified) `value` that's passed to the next.
#
# String value is the over-the-wire name (also used by webhooks, NATS,
# and remote plugins) — that's the stable bit. The Python attribute on
# this class is just a typed alias.


class MorpheusEvents:
    """Catalogue of all built-in hook events."""

    # ── Orders (fire) ──────────────────────────────────────────────────────
    # ORDER_PLACED      — kwargs: order=Order. Customer's order has been
    #                      created from cart. Inventory reserved. Payment
    #                      not yet captured.
    # ORDER_CONFIRMED   — kwargs: order=Order. Reserved. Currently unused.
    # ORDER_PAID        — kwargs: order=Order. Payment captured. Fired
    #                      EXACTLY ONCE per order via the select_for_update
    #                      gate in payments.services.stripe. Subscribers:
    #                      inventory commit, CDP rollups, digital token
    #                      mint, transactional email, webhook fanout.
    # ORDER_CANCELLED   — kwargs: order=Order. Releases stock reservation.
    # ORDER_FULFILLED   — kwargs: order=Order, fulfillment=Fulfillment.
    ORDER_PLACED = 'order.placed'
    ORDER_CONFIRMED = 'order.confirmed'
    ORDER_PAID = 'order.paid'
    ORDER_CANCELLED = 'order.cancelled'
    ORDER_FULFILLED = 'order.fulfilled'

    # ── Payments (fire) ────────────────────────────────────────────────────
    # PAYMENT_CAPTURED  — kwargs: payment=Payment.
    # PAYMENT_FAILED    — kwargs: payment=Payment, error=str.
    # PAYMENT_REFUNDED  — kwargs: refund=Refund, order=Order, amount=Money,
    #                     actor=User|None. Fired by RefundService.process()
    #                     for every refund (admin-initiated OR return-driven).
    PAYMENT_CAPTURED = 'payment.captured'
    PAYMENT_FAILED = 'payment.failed'
    PAYMENT_REFUNDED = 'payment.refunded'

    # ── Cart (fire) ────────────────────────────────────────────────────────
    # CART_CREATED      — kwargs: cart=Cart.
    # CART_UPDATED      — kwargs: cart=Cart.
    # CART_ABANDONED    — kwargs: cart=Cart, email=str|None. Fired by
    #                     cart_abandonment/tasks.py and inventory/tasks.py
    #                     after a configurable idle period. Subscribers
    #                     handle recovery email, AI cart-summary,
    #                     CRM follow-up tasks. `email` is None when the
    #                     cart has no customer and no captured email.
    # ADD_TO_CART       — kwargs: cart=Cart, item=CartItem, product=Product,
    #                      variant=ProductVariant|None, quantity=int. Fires
    #                      from storefront cart_add view AFTER the item is
    #                      persisted. Subscribers: GA4 add_to_cart event.
    # REMOVE_FROM_CART  — kwargs: cart=Cart, item=CartItem (pre-delete),
    #                      product=Product, quantity=int.
    # BEGIN_CHECKOUT    — kwargs: cart=Cart, customer=User|None. Fires once
    #                      per session when the customer hits /checkout/.
    CART_CREATED = 'cart.created'
    CART_UPDATED = 'cart.updated'
    CART_ABANDONED = 'cart.abandoned'
    ADD_TO_CART = 'cart.item_added'
    REMOVE_FROM_CART = 'cart.item_removed'
    BEGIN_CHECKOUT = 'checkout.started'

    # ── Filters ───────────────────────────────────────────────────────────
    # CART_CALCULATE_BREAKDOWN — value=dict (subtotal/shipping/tax/discount/
    #                            total/currency/meta), kwargs: cart, address,
    #                            billing_address, shipping_rate_id, coupon,
    #                            channel, customer. CANONICAL cart pricing
    #                            event. Subscribers (promotions, shipping,
    #                            tax) layer their components onto the dict.
    # PRODUCT_CALCULATE_PRICE  — value=Money, kwargs: product, customer.
    #                            Lets AI dynamic pricing / B2B price lists
    #                            adjust the displayed price.
    # CART_CALCULATE_TOTAL     — DEPRECATED. Predecessor to BREAKDOWN.
    #                            Retained as a constant for any external
    #                            plugin still subscribed; OrderService no
    #                            longer fires it. Will be removed once the
    #                            in-tree subscribers are migrated (done).
    CART_CALCULATE_BREAKDOWN = 'cart.calculate_breakdown'  # filter
    PRODUCT_CALCULATE_PRICE = 'product.calculate_price'    # filter
    CART_CALCULATE_TOTAL = 'cart.calculate_total'          # DEPRECATED — use CART_CALCULATE_BREAKDOWN

    # ── Catalog (fire) ────────────────────────────────────────────────────
    # PRODUCT_VIEWED    — kwargs: product=Product, customer=User|None,
    #                     session_key=str. Fires from the storefront PDP.
    # PRODUCT_CREATED   — kwargs: product=Product.
    # PRODUCT_UPDATED   — kwargs: product=Product.
    # CATEGORY_UPDATED  — kwargs: category=Category.
    PRODUCT_VIEWED = 'product.viewed'
    PRODUCT_CREATED = 'product.created'
    PRODUCT_UPDATED = 'product.updated'
    CATEGORY_UPDATED = 'category.updated'

    # ── Customers (fire) ──────────────────────────────────────────────────
    # CUSTOMER_REGISTERED — kwargs: customer=Customer.
    # CUSTOMER_LOGIN      — kwargs: customer=Customer.
    CUSTOMER_REGISTERED = 'customer.registered'
    CUSTOMER_LOGIN = 'customer.login'

    # ── Inventory (fire) ──────────────────────────────────────────────────
    PRODUCT_LOW_STOCK = 'product.low_stock'
    PRODUCT_OUT_OF_STOCK = 'product.out_of_stock'

    # ── Returns (fire) ────────────────────────────────────────────────────
    # 'return.requested'  — kwargs: return_request=ReturnRequest.
    # 'return.approved'   — kwargs: return_request=ReturnRequest.
    # 'return.rejected'   — kwargs: return_request=ReturnRequest.
    # 'return.refunded'   — kwargs: return_request=ReturnRequest,
    #                       refund=Refund|None, store_credit=Money|None.
    #                       Fired ONCE the return is fully closed (either
    #                       money refund OR store-credit issued). Distinct
    #                       from PAYMENT_REFUNDED — that fires per refund
    #                       (including direct admin refunds, no RMA);
    #                       'return.refunded' fires per RMA closure.
    #                       Inventory subscribes to restock the items.
    # 'refund.processed'  — kwargs: refund=Refund, order=Order, amount=Money,
    #                       actor=User|None. Same payload as
    #                       PAYMENT_REFUNDED — they're aliases for now.
    #                       New code SHOULD subscribe to PAYMENT_REFUNDED.

    # ── Search (fire) ─────────────────────────────────────────────────────
    SEARCH_PERFORMED = 'search.performed'

    # ── AI (fire) ─────────────────────────────────────────────────────────
    AI_DESCRIPTION_GENERATED = 'ai.description_generated'
    AI_RECOMMENDATION_REQUESTED = 'ai.recommendation_requested'

    # ── Agent intents (fire) — emitted by plugins/installed/ai_assistant ──
    AGENT_INTENT_PROPOSED = 'agent.intent.proposed'
    AGENT_INTENT_AUTHORIZED = 'agent.intent.authorized'
    AGENT_INTENT_REJECTED = 'agent.intent.rejected'
    AGENT_INTENT_COMPLETED = 'agent.intent.completed'
    AGENT_INTENT_FAILED = 'agent.intent.failed'

    # ── CMS (fire) ────────────────────────────────────────────────────────
    CMS_FORM_SUBMITTED = 'cms.form_submitted'

    # ── Digital products (fire) ───────────────────────────────────────────
    # 'digital.tokens_issued' — kwargs: order=Order, tokens=list[DownloadToken].
