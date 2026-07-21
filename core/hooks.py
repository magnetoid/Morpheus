"""
Morpheus CMS — Hook Registry
The event bus that connects all plugins without tight coupling.
"""

# ruff: noqa: PLC0415, I001
# PLC0415: inline imports are intentional throughout this module — they
# guard against Django app-registry not being ready during settings import.
# I001: the import-order inside helper functions follows the lazy-load
# pattern, not module-top ordering.

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

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
        # { event_name: [ (priority, handler, mode, plugin), ... ] }
        # mode is 'sync' (default, runs in-request) or 'async' (deferred to
        # Celery so the request can return immediately). plugin is the owning
        # plugin name (None for core-owned handlers); a handler owned by an
        # INACTIVE plugin is skipped at fire/filter time — that's how a
        # disabled plugin's contributed cards/KPIs/feed items disappear (ADR
        # 0023), since deactivate() intentionally does not unwind ready()-wired
        # hooks.
        self._handlers: dict[str, list[tuple[int, Callable, str, str | None]]] = defaultdict(list)
        # Predicate (plugin_name) -> bool, set once by plugins.registry at boot
        # so core/hooks never imports plugins.* (keeps the core boundary clean).
        self._active_check: Callable[[str], bool] | None = None

    def set_active_check(self, fn: Callable[[str], bool]) -> None:
        """Wire the 'is this plugin active?' predicate (plugins.registry.is_active).
        Until set, no handler is gated (every handler runs — the boot default)."""
        self._active_check = fn

    @staticmethod
    def _unpack(entry: tuple) -> tuple[int, Callable, str, str | None]:
        """Normalise a handler entry to (priority, handler, mode, plugin),
        tolerating legacy 2-tuples (priority, handler) and 3-tuples (…, mode)."""
        priority, handler = entry[0], entry[1]
        mode = entry[2] if len(entry) > 2 else 'sync'
        plugin = entry[3] if len(entry) > 3 else None
        return priority, handler, mode, plugin

    def _owner_inactive(self, plugin: str | None) -> bool:
        """True when the handler is owned by a currently-disabled plugin."""
        return bool(plugin) and self._active_check is not None and not self._active_check(plugin)

    def register(
        self,
        event: str,
        handler: Callable,
        priority: int = 50,
        mode: str = 'sync',
        plugin: str | None = None,
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
        self._handlers[event].append((priority, handler, mode, plugin))
        self._handlers[event].sort(key=lambda x: x[0])
        logger.debug(
            'Hook registered: %s → %s (priority=%d, mode=%s)',
            event,
            handler.__qualname__,
            priority,
            mode,
        )

    def unregister(self, event: str, handler: Callable) -> None:
        """Remove a handler from an event."""
        self._handlers[event] = [entry for entry in self._handlers[event] if entry[1] != handler]

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
            _priority, handler, mode, plugin = self._unpack(entry)
            # A disabled plugin's handlers must not fire — this is what makes a
            # contributed surface vanish on disable (ADR 0023).
            if self._owner_inactive(plugin):
                continue

            if mode == 'async':
                self._enqueue_async(event, handler, kwargs)
                continue

            try:
                result = handler(**kwargs)
            except Exception as e:  # noqa: BLE001 — handler isolation, logged with traceback
                logger.error(
                    'Hook handler error: event=%s handler=%s error=%s',
                    event,
                    handler.__qualname__,
                    e,
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
                event,
                handler.__qualname__,
                exc,
            )
            try:
                handler(**kwargs)
            except Exception as e:  # noqa: BLE001
                logger.error(
                    'async-fallback-sync hook handler error: event=%s handler=%s error=%s',
                    event,
                    handler.__qualname__,
                    e,
                    exc_info=True,
                )

    def filter(self, event: str, value: Any, *, raise_errors: bool = False, **kwargs: Any) -> Any:
        """
        Filter an event — each handler receives the (potentially modified) value
        and returns a new value. Builds a transformation pipeline.

        Filters are ALWAYS sync — the value has to flow through synchronously
        for the caller to receive the transformed result. async mode on a
        filter is rejected at registration time? — not yet; for now we
        silently treat any handler registered for a filter event as sync.

        By default a raising handler is isolated (logged and skipped) so one
        buggy subscriber can't break the pipeline. Pass ``raise_errors=True``
        for *security-critical* filters (e.g. the MFA second-factor gate) that
        must fail CLOSED: a handler exception propagates to the caller instead
        of being swallowed and read as "no transformation".
        """
        for entry in self._handlers.get(event, []):
            _priority, handler, _mode, plugin = self._unpack(entry)
            if self._owner_inactive(plugin):
                continue
            try:
                result = handler(value=value, **kwargs)
            except Exception as e:  # noqa: BLE001 — filter isolation, logged with traceback
                logger.error(
                    'Hook filter error: event=%s handler=%s error=%s',
                    event,
                    handler.__qualname__,
                    e,
                    exc_info=True,
                )
                if raise_errors:
                    raise
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

        from django.http import HttpRequest

        class WebhookEncoder(DjangoJSONEncoder):
            def default(self, o):
                if isinstance(o, models.Model):
                    return {'id': str(o.pk), 'model': o.__class__.__name__}
                if isinstance(o, QuerySet):
                    return [{'id': str(obj.pk), 'model': obj.__class__.__name__} for obj in o]
                if isinstance(o, decimal.Decimal):
                    return str(o)
                if hasattr(o, 'amount') and hasattr(o, 'currency'):  # MoneyField
                    return {'amount': str(o.amount), 'currency': str(o.currency)}
                # WSGIRequest / ASGIRequest aren't JSON-serialisable. Hook
                # kwargs (e.g. agent.run.started) sometimes carry the
                # request through for downstream handlers — we don't want
                # to ship the whole object to a webhook anyway. Send a
                # minimal pointer (path + method) instead so subscribers
                # still know which request triggered the event.
                if isinstance(o, HttpRequest):
                    return {
                        'type': 'http_request',
                        'path': getattr(o, 'path', ''),
                        'method': getattr(o, 'method', ''),
                    }
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
            logger.debug('Skipping remote dispatch for %s — apps not ready: %s', event, e)
            return

        try:
            payload = self._serialize_payload(kwargs)
        except (TypeError, ValueError) as e:
            logger.error(
                'Failed to serialize payload for event=%s: %s',
                event,
                e,
                exc_info=True,
            )
            return

        try:
            from django.core.cache import cache
            from django.db import transaction

            # Skip the per-fire endpoint query on the common path (no webhooks
            # configured). Cached for 30s so a newly-added endpoint is picked up
            # quickly without hitting the DB on every hot-path event (cart-add,
            # product-view, …). None on a cache backend miss → fall through and
            # query, so correctness never depends on the cache.
            has_webhooks = cache.get('core:has_active_webhooks')
            if has_webhooks is None:
                has_webhooks = WebhookEndpoint.objects.filter(is_active=True).exists()
                cache.set('core:has_active_webhooks', has_webhooks, 30)
            endpoints = WebhookEndpoint.objects.filter(is_active=True) if has_webhooks else []
            for endpoint in endpoints:
                if event in endpoint.events or '*' in endpoint.events:
                    # Defer the Celery enqueue until the surrounding DB transaction
                    # commits, so a request that rolls back can't emit a phantom
                    # webhook. on_commit runs the callback immediately when no atomic
                    # block is open, so the non-transactional path is unchanged. Bind
                    # url/secret as defaults to dodge the late-binding closure trap.
                    transaction.on_commit(
                        lambda url=endpoint.url, secret=endpoint.secret: dispatch_webhook.delay(
                            url, secret, event, payload
                        )
                    )
        except Exception as e:  # noqa: BLE001 — DB outage must not break local handlers
            logger.warning('Webhook dispatch failed for %s: %s', event, e, exc_info=True)

        # Only write the transactional outbox when NATS is actually configured
        # to drain it. Prod ships without NATS, so this row would otherwise be
        # written on EVERY hook fire (cart-add, product-view, login, …) and NEVER
        # consumed — the table grew unbounded with the store's traffic. When NATS
        # is deployed, the outbox resumes; the only loss is transient events fired
        # while it was off, which have no consumer anyway.
        import os

        if os.environ.get('NATS_URL'):
            try:
                OutboxEvent.objects.create(event_type=event, payload=payload)
            except Exception as e:  # noqa: BLE001 — outbox failure logged, do not abort
                logger.warning('Outbox write failed for %s: %s', event, e, exc_info=True)

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

    # ── Stock gate (filter, fail-closed) ───────────────────────────────────
    # ORDER_RESERVE_STOCK — value=int, kwargs: order=Order. Fired via
    #   `filter(..., raise_errors=True)` INSIDE create_from_cart's transaction,
    #   before ORDER_PLACED. The inventory plugin's subscriber reserves stock and
    #   raises InsufficientStockError on a short, which propagates and rolls back
    #   the order (the plain ORDER_PLACED bus swallows handler exceptions, so a
    #   reservation fired there could never actually block checkout → oversell).
    #   No subscriber (inventory disabled) → value passes through, order proceeds.
    ORDER_RESERVE_STOCK = 'order.reserve_stock'

    # ── Payments (fire) ────────────────────────────────────────────────────
    # PAYMENT_CAPTURED  — kwargs: payment=Payment.
    # PAYMENT_FAILED    — kwargs: payment=Payment, error=str.
    # PAYMENT_REFUNDED  — kwargs: refund=Refund, order=Order, amount=Money,
    #                     actor=User|None. Fired by RefundService.process()
    #                     for every refund (admin-initiated OR return-driven).
    # STRIPE_WEBHOOK_EVENT — fire, kwargs: event_type=str, payload=dict (the full
    #                     Stripe event payload; named ``payload`` not ``event``
    #                     because fire() reserves ``event`` for the event name).
    #                     Fired by
    #                     payments.services.stripe.process_webhook for every
    #                     Stripe event type payments does NOT own itself (it
    #                     handles only payment_intent.succeeded /
    #                     payment_intent.payment_failed). Lets an OPTIONAL
    #                     consumer plugin (subscriptions' billing reconciler)
    #                     react to invoice.* / customer.subscription.* WITHOUT
    #                     payments importing it. Idempotent: the
    #                     StripeWebhookEvent unique-id guard upstream means a
    #                     redelivered event never re-fires. Fail-soft: the bus
    #                     isolates a broken subscriber.
    PAYMENT_CAPTURED = 'payment.captured'
    PAYMENT_FAILED = 'payment.failed'
    PAYMENT_REFUNDED = 'payment.refunded'
    STRIPE_WEBHOOK_EVENT = 'payments.stripe_webhook_event'  # fire

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
    # ACCOUNT_SUMMARY_FIELDS    — value=dict, kwargs: user=Customer. The
    #                             account-home summary dict (orders_count,
    #                             pending_returns, … see storefront
    #                             account._account_summary). Each plugin
    #                             subscriber folds ITS OWN field(s) into the
    #                             dict and returns it, so a disabled plugin's
    #                             tile simply never appears. Fail-soft: the
    #                             hook bus isolates a broken handler. This is
    #                             how a plugin contributes an account-home
    #                             tile without storefront editing its summary.
    # CUSTOMER_DETAIL_PANELS    — value=list[dict], kwargs: customer=Customer,
    #                             request=HttpRequest. The dashboard
    #                             customer-detail page (admin_dashboard
    #                             customer_edit) exposes this slot. Each
    #                             plugin subscriber appends ITS OWN panel dict
    #                             — {'label': str, 'html': SafeString,
    #                             'priority': int} — and returns the list, so
    #                             a disabled plugin's panel simply never
    #                             appears. marketplace contributes a Vendor
    #                             on/off panel; affiliates an Affiliate one.
    #                             admin_dashboard has ZERO vendor/affiliate
    #                             code. Fail-soft: the hook bus isolates a
    #                             broken handler so one bad panel can't break
    #                             the customer page.
    CART_CALCULATE_BREAKDOWN = 'cart.calculate_breakdown'  # filter
    PRODUCT_CALCULATE_PRICE = 'product.calculate_price'  # filter
    # PRODUCT_LIST_REORDER — filter, value=list[Product]. Per-visitor
    #   merchandising reorders a storefront product list by purchase-propensity.
    #   kwargs: request=HttpRequest, surface=str ('author'|'facet'|'related'|…).
    #   Subscribed by the personalisation plugin; consent-gated, no-op otherwise.
    PRODUCT_LIST_REORDER = 'product.list.reorder'  # filter
    # STOREFRONT_PRODUCTS — filter. The merchandising-takeover hook: storefront
    #   views fire it at every product placeholder so a merchandising owner
    #   (the dynamics plugin) can control WHAT renders there.
    #   kwargs: surface=str ('home_hero'|'home_featured'|'plp_default'|…),
    #   request=HttpRequest, limit=int. Two modes by ``value``:
    #     value=None        → free selection; subscriber returns list[Product]
    #                         (or None to leave the view's default in place).
    #     value=list[...]   → reorder-only (paginated slices); subscriber
    #                         returns the same items reordered/filtered.
    #   No subscriber / dynamics disabled → value passes through unchanged.
    STOREFRONT_PRODUCTS = 'storefront.products'  # filter
    # CHECKOUT_SHIPPING_RATES — filter, value=None. Checkout asks the shipping
    #   owner for rate options. kwargs: cart=Cart, address=dict. Subscriber
    #   (shipping) returns list[{'id','label','amount','currency'}] (may be
    #   empty). value left None (plugin off / handler broke) → checkout falls
    #   back to a free 'Standard delivery' rate so the flow never blocks.
    CHECKOUT_SHIPPING_RATES = 'checkout.shipping_rates'  # filter
    # CHECKOUT_GATEWAYS — filter, value=list. The checkout payment-method
    #   picker. Subscriber (payments) returns its enabled gateway dicts
    #   (payments.services.routing.picker_gateways). Plugin disabled → []
    #   and the picker renders no gateway choices.
    CHECKOUT_GATEWAYS = 'checkout.gateways'  # filter
    # SEARCH_RANKED_IDS — filter, value=list. Semantic/hybrid ranking for
    #   storefront search. kwargs: query=str, limit=int. Subscriber
    #   (ai_assistant) returns ranked product pks; empty/absent → storefront
    #   falls through to its SKU/metafield backstop.
    SEARCH_RANKED_IDS = 'storefront.search_ranked_ids'  # filter
    # SIMILAR_PRODUCTS — filter, value=list[Product]. 'You might also like'
    #   candidates for the PDP. kwargs: product=Product, limit=int.
    #   Subscriber (ai_assistant) returns content-similar products; absent →
    #   the PDP section self-hides.
    SIMILAR_PRODUCTS = 'storefront.similar_products'  # filter
    # CUSTOMER_DATA_EXPORT — filter, value=dict {filename: data}. The GDPR
    #   Art. 15 export: customers seeds account.json/addresses.json, then each
    #   plugin folds ITS OWN file(s) (orders.json, reviews.json, loyalty.json,
    #   …) into the dict. kwargs: customer=Customer. A disabled plugin's file
    #   simply never appears — the bus gates on active state.
    CUSTOMER_DATA_EXPORT = 'customer.data_export'  # filter
    # CUSTOMER_ANONYMISE — fire, kwargs: customer=Customer, sentinel_email=str.
    #   The GDPR Art. 17 erasure: each plugin scrubs/deletes ITS OWN rows for
    #   the customer (orders scrub PII but keep totals for fiscal hold,
    #   wishlist deletes, payments drops stored methods, …). customers then
    #   anonymises the Customer row itself. Handlers must be idempotent.
    CUSTOMER_ANONYMISE = 'customer.anonymise'  # fire
    CART_CALCULATE_TOTAL = 'cart.calculate_total'  # DEPRECATED — use CART_CALCULATE_BREAKDOWN
    ACCOUNT_SUMMARY_FIELDS = 'account.summary_fields'  # filter
    CUSTOMER_DETAIL_PANELS = 'customer.detail_panels'  # filter
    # PRODUCT_FORM_CARDS — filter, value=list[dict], kwargs: product=Product.
    #   A plugin appends {'template': '<path>', 'context': {...}, 'order': int}
    #   to contribute a card into the dashboard product-edit form WITHOUT
    #   admin_dashboard knowing about it (the modular alternative to hardcoding
    #   book/bookvault cards). The view renders each template with the product.
    PRODUCT_FORM_CARDS = 'product.form_cards'  # filter
    # PRODUCT_FORM_SAVED — fire, kwargs: product=Product, post=QueryDict,
    #   files=MultiValueDict. Fired after a product is saved in the dashboard so
    #   a plugin can persist its own product-form fields (its card's inputs).
    PRODUCT_FORM_SAVED = 'product.form_saved'  # fire
    # PRODUCT_LIST_COLUMNS — filter, value=list[dict], kwargs:
    #   products=list[Product], request=HttpRequest. A plugin appends
    #   {'label': str, 'cell_template': '<path>', 'order': int, optional
    #   'bulk_action': {'label', 'url', 'field', 'icon'}} to add a column to
    #   the dashboard product list without admin_dashboard importing it
    #   (ADR 0023 — the disable-safe replacement for the hardcoded bookvault
    #   column). The subscriber may annotate `products` in place for its cell
    #   template to read; the view pre-renders one cell per product.
    PRODUCT_LIST_COLUMNS = 'product.list_columns'  # filter
    # EMAIL_TEMPLATE_OVERRIDE — filter, value=(subject, text, html) tuple
    #   starting as (None, None, None), kwargs: key=str, ctx=dict. Lets a
    #   plugin supply merchant-edited copy for a transactional email
    #   (core.emails falls back to the filesystem template when every
    #   element stays None). cms subscribes with its EmailTemplate rows;
    #   first subscriber to fill the tuple wins.
    EMAIL_TEMPLATE_OVERRIDE = 'email.template_override'  # filter
    # STOREFRONT_PAGE_INTRO — filter, value=dict {'body': '', 'meta_description':
    #   ''}, kwargs: page=str (a stable key: 'products' | 'vendors' | 'journal').
    #   Supplies merchant-edited intro copy + meta for the built-in storefront
    #   LISTING pages, which own no model of their own (unlike a Category or a
    #   BookTaxonomyRoot) and so had their prose hardcoded in the theme with no
    #   way to edit it. cms subscribes with its Block rows (key
    #   '<page>_intro'); the view falls back to the theme's static copy while
    #   every element stays empty. Storefront fires it rather than importing
    #   cms, so a disabled cms degrades to the fallback instead of 500ing.
    STOREFRONT_PAGE_INTRO = 'storefront.page_intro'  # filter
    # ACTIVITY_FEED — filter, value=list[dict], kwargs: limit=int. The
    #   dashboard-home activity feed. Each plugin subscriber appends ITS OWN
    #   recent-event dicts — {'kind': str, 'icon': str, 'label': str,
    #   'hint': str, 'url': str, 'when': datetime} — and returns the list;
    #   admin_dashboard merges, sorts newest-first, and caps at `limit`.
    #   The modular alternative to home.py importing sibling-plugin models
    #   for its reviews / loyalty / newsletter tiles. Fail-soft: the hook
    #   bus isolates a broken handler so one bad source can't break home.
    ACTIVITY_FEED = 'dashboard.activity_feed'  # filter
    # DASHBOARD_KPIS — filter, value=list[dict] ({label, value, delta,
    #   trend, icon, series}), kwargs: date_range (duck-typed: .start,
    #   .end, .prev_start, .prev_end). The dashboard-home KPI row. Each
    #   plugin appends ITS OWN metric dicts; subscriber priority orders
    #   the tiles. orders (sales/orders/AOV) and catalog (active
    #   products) subscribe.
    DASHBOARD_KPIS = 'dashboard.kpis'  # filter
    # DASHBOARD_HOME_PANELS — filter, value=dict of home-template context
    #   keys, kwargs: date_range. Each plugin folds ITS OWN panel data —
    #   orders: recent_orders; catalog: top_products; ai_assistant:
    #   insights/pulse + the provider half of ai_summary; agent_core: the
    #   run-count half of ai_summary; inventory: low_stock(+threshold).
    #   ai_summary is merged via setdefault so either AI plugin can be
    #   disabled independently. A missing key renders an empty panel.
    DASHBOARD_HOME_PANELS = 'dashboard.home_panels'  # filter
    # DASHBOARD_SETUP_STEPS — filter, value=list[dict] ({key, label,
    #   hint, url, done}). The first-run merchant checklist; catalog,
    #   orders and ai_assistant contribute their step (the email step
    #   stays in home.py — it reads core settings, no plugin owns it).
    DASHBOARD_SETUP_STEPS = 'dashboard.setup_steps'  # filter
    # CHANNELS_OVERVIEW — filter, value=list[dict], no kwargs. The unified
    #   sales-channels dashboard (channels plugin). Each commerce-channel
    #   plugin (google_shopping, meta_commerce, tiktok_commerce, …) appends
    #   ITS OWN status row — {'name': str, 'label': str, 'icon': str,
    #   'connected': bool, 'pixel': 'on'|'off'|None, 'has_feed': bool,
    #   'feed_url': str|None, 'eligible': int|None, 'total': int|None,
    #   'coverage_pct': float|None, 'dashboard_url': str} — using only cheap
    #   local config/coverage reads (no live API calls). A disabled channel's
    #   row simply never appears. Fail-soft: the hook bus isolates a broken
    #   handler so one channel can't break the overview.
    CHANNELS_OVERVIEW = 'channels.overview'  # filter
    # ANALYTICS_AD_SPEND — filter, value=list[dict], no kwargs. Each ad-channel
    #   plugin appends its own {'channel': str, 'spend': number, 'days': int} for
    #   the trailing window; analytics snapshots it into AdSpendSnapshot for ROAS.
    ANALYTICS_AD_SPEND = 'analytics.collect_ad_spend'  # filter
    # CHANNELS_METRICS — filter, value=list[dict], no kwargs. EXPENSIVE: each
    #   channel plugin appends ITS OWN 30-day ads totals — {'name': str,
    #   'spend': float|None, 'clicks': float|None, 'conversions': float|None,
    #   'revenue': float|None, 'roas': float|None} — by calling its live ads
    #   report (or reading its already-cached async report). Because of the
    #   live API calls this filter is run ONLY by the channels.refresh_metrics
    #   daily task (which caches the result under channels:metrics:v1); the
    #   overview PAGE never triggers it. Fail-soft per channel.
    CHANNELS_METRICS = 'channels.metrics'  # filter
    # BRAIN_SIGNALS — filter, value=dict (the Morpheus Brain signal snapshot),
    #   no kwargs. The kernel aggregator (core/brain/signals.py) seeds the
    #   core-owned sections (plugin health, error-log + code-quality signals,
    #   the setup checklist) and fires this filter so each plugin merges ITS
    #   OWN read-only slice: seo → content.{low_seo,seo_avg,…,notfound} +
    #   storefront.{cwv,seo_flags}; catalog → content.catalog; ai_assistant →
    #   improvements.insights; morpheus_brain → reports. Handlers mutate/merge
    #   into value and return it (order-independent — the slices are disjoint).
    #   A disabled contributor's slice simply never appears (bus skips inactive
    #   owners), so its Brain panel vanishes. Keeps core importing no plugin
    #   model — the inverse of the old hard-coded imports (ADR 0017).
    BRAIN_SIGNALS = 'brain.signals'  # filter
    # AGENT_SYSTEM_PROMPT — filter, value=str (the assembled base system prompt
    #   for an agent/Linda), no kwargs. Fired as the LAST assembly step in
    #   core/agents/base.py:get_system_prompt and core/assistant/prompts.py:
    #   build_system_prompt. Subscribers may PREPEND a prefix (e.g. ai_content's
    #   brand voice — returns with_brand_voice(value)) and must return the full
    #   prompt string. Replaces the old core→ai_content import + try/except:
    #   the bus already isolates handler errors and skips inactive owners, so a
    #   disabled ai_content yields the plain prompt (ADR 0017 inversion).
    AGENT_SYSTEM_PROMPT = 'agent.system_prompt'  # filter

    # KNOWLEDGE_SOURCES — filter, value=list (accumulates knowledge documents
    #   for Linda's RAG index). Each subscriber APPENDS dicts of the shape
    #   {source: str, ref: str, title: str, text: str} for the unstructured
    #   knowledge it owns (docs, help articles, policies, product long-copy) and
    #   returns the list. The ai_assistant plugin ingests + embeds the result;
    #   a disabled contributor's slice simply never appears (bus skips inactive
    #   owners). Structured data (orders/inventory) stays on live tool-calls —
    #   this is only for text Linda can't otherwise see. See
    #   docs/plans/rag-knowledge-base.md.
    KNOWLEDGE_SOURCES = 'knowledge.sources'  # filter

    # AI_SURFACE_DISCLOSURE — filter, value=str (the disclosure text shown on a
    #   customer-facing conversational AI surface), kwargs: surface=str (which
    #   surface asked, e.g. 'ai_stylist'). EU AI Act Art. 50(1): a system that
    #   interacts with a natural person must disclose it is an AI. The DEFAULT
    #   text is a legal FLOOR baked into the core `{% ai_disclosure %}` tag
    #   (core/templatetags/morph.py) — it can't be a togglable plugin, so it
    #   never disappears when a plugin is disabled. Subscribers (gdpr) may
    #   REPLACE the wording with merchant-configured copy and return the string;
    #   a disabled subscriber falls back to the core default (bus skips inactive
    #   owners). The disclosure ships INSIDE each conversational surface's own
    #   template, so disabling that surface plugin removes chat + label together.
    AI_SURFACE_DISCLOSURE = 'ai.surface_disclosure'  # filter

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
    # CUSTOMER_SEGMENT_CHANGED — kwargs: customer=Customer, old=str, new=str.
    #                            Fired by customers.rfm on the nightly recompute
    #                            when a customer crosses into a different RFM segment;
    #                            the workflows plugin can trigger campaigns off it.
    CUSTOMER_SEGMENT_CHANGED = 'customer.segment_changed'
    # INVENTORY_OVERSTOCK_DETECTED — kwargs: variants=list[dict]. Fired by the daily
    #   stockout-forecast task for slow-moving / dead stock; workflows can trigger a
    #   markdown/promo campaign off it.
    INVENTORY_OVERSTOCK_DETECTED = 'inventory.overstock_detected'
    # LIVE_EVENT_STARTED / LIVE_EVENT_ENDED — kwargs: live_event=LiveEvent. Fired by
    #   the live_commerce dashboard "go live" / "end" actions; subscribers can
    #   push notifications, kick off a recording, or refresh a storefront cache.
    LIVE_EVENT_STARTED = 'live_commerce.event_started'
    LIVE_EVENT_ENDED = 'live_commerce.event_ended'

    # ── Auth (filter) ─────────────────────────────────────────────────────
    # AUTH_SECOND_FACTOR — filter, value=None|HttpResponse, kwargs:
    #   request=HttpRequest, user=Customer, next=str. Fired by core/auth
    #   otp_verify AFTER the email-OTP (first factor) succeeds but BEFORE
    #   login() establishes the session. A subscriber that needs a second
    #   factor (the staff_mfa plugin) stashes the pending user + next in the
    #   session and returns an HttpResponse — a redirect to its challenge
    #   view — and the filter short-circuits login with that response. With
    #   no subscriber the value stays None and login proceeds unchanged, so
    #   disabling the plugin reverts to single-factor email-OTP exactly.
    AUTH_SECOND_FACTOR = 'auth.second_factor'  # filter

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
    # 'refund.processed'  — RETIRED. RefundService.process now fires the
    #                       canonical PAYMENT_REFUNDED (kwargs: refund, order,
    #                       amount, actor). The old string had zero subscribers
    #                       while the real handlers waited on PAYMENT_REFUNDED,
    #                       so refund email/clawback/pixel never ran. Subscribe
    #                       to PAYMENT_REFUNDED.

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

    # ── Self-improvement engine (fire + subscribe) ────────────────────────
    # CSP_VIOLATION_REPORTED — kwargs: directive=str, blocked_uri=str,
    #                          document_uri=str, line=int|None, source_file=str.
    #                          Fired by api/views.csp_report on every report
    #                          the browser POSTs. Subscribed to by
    #                          core/self_improvement/collectors/csp.py.
    CSP_VIOLATION_REPORTED = 'csp.violation_reported'

    # ── CMS (fire) ────────────────────────────────────────────────────────
    CMS_FORM_SUBMITTED = 'cms.form_submitted'

    # ── Digital products (fire) ───────────────────────────────────────────
    # 'digital.tokens_issued' — kwargs: order=Order, tokens=list[DownloadToken].
