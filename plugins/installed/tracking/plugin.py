"""Tracking plugin — GA4 (server) + GTM (client) for Morpheus.

* Server-side: subscribes to the hook bus and POSTs to the GA4
  Measurement Protocol v2.
* Client-side: contributes a `{% gtm_head %}` template tag and
  per-event dataLayer push partials.
* Backend control center at `/dashboard/tracking/` with tabs for
  Connection / Event firing / Consent / Identity / Filters / Tests.
"""

from __future__ import annotations

import logging

from morpheus import Plugin, SettingsPanel, events

logger = logging.getLogger('morpheus.tracking')


class TrackingPlugin(Plugin):
    name = 'tracking'
    label = 'Tracking (GA4 + GTM)'
    version = '0.1.0'
    description = (
        'Comprehensive Google Analytics 4 + Google Tag Manager integration. '
        'Server-side firing via Measurement Protocol v2, client-side via '
        'GTM dataLayer pushes. Consent Mode v2, per-event toggles, audit '
        'log, GTM container export, test bench. Backend control center at '
        '/dashboard/tracking/.'
    )
    has_models = True
    requires = ['orders', 'catalog']

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.tracking.urls',
            prefix='dashboard/tracking/',
            namespace='tracking',
        )
        # Server-side firing. Priority 95 — runs before analytics (99)
        # so we capture in flight without depending on its session row.
        self.register_hook(events.ORDER_PAID, self.on_order_paid, priority=95)
        self.register_hook(events.PAYMENT_REFUNDED, self.on_refund, priority=95)
        self.register_hook(events.ADD_TO_CART, self.on_add_to_cart, priority=95)
        self.register_hook(events.REMOVE_FROM_CART, self.on_remove_from_cart, priority=95)
        self.register_hook(events.BEGIN_CHECKOUT, self.on_begin_checkout, priority=95)
        self.register_hook(events.PRODUCT_VIEWED, self.on_product_viewed, priority=95)
        self.register_hook(events.CUSTOMER_REGISTERED, self.on_signup, priority=95)
        self.register_hook(events.CUSTOMER_LOGIN, self.on_login, priority=95)
        self.register_hook(events.SEARCH_PERFORMED, self.on_search, priority=95)

    # ── Hook handlers (all swallow exceptions; tracking must never
    #     break the order flow).

    def on_order_paid(self, order=None, **_):
        if order is None:
            return
        self._fire(
            'purchase',
            order=order,
            transaction_id=str(getattr(order, 'order_number', '') or order.pk),
        )

    def on_refund(self, order=None, amount=None, **_):
        if order is None:
            return
        self._fire(
            'refund',
            order=order,
            amount=amount,
            transaction_id=str(getattr(order, 'order_number', '') or order.pk),
        )

    def on_add_to_cart(self, cart=None, item=None, product=None, variant=None, quantity=1, **_):
        if product is None:
            return
        self._fire(
            'add_to_cart', cart=cart, item=item, product=product, variant=variant, quantity=quantity
        )

    def on_remove_from_cart(self, cart=None, item=None, product=None, quantity=1, **_):
        if product is None:
            return
        self._fire('remove_from_cart', cart=cart, item=item, product=product, quantity=quantity)

    def on_begin_checkout(self, cart=None, **_):
        if cart is None:
            return
        self._fire('begin_checkout', cart=cart)

    def on_product_viewed(self, product=None, **_):
        if product is None:
            return
        self._fire('view_item', product=product)

    def on_signup(self, customer=None, **_):
        self._fire('sign_up', customer=customer)

    def on_login(self, customer=None, **_):
        self._fire('login', customer=customer)

    def on_search(self, search_term='', **_):
        self._fire('search', search_term=search_term)

    def _fire(self, event_kind: str, **ctx) -> None:  # noqa: PLR0912
        """Build the GA4 payload and POST via Measurement Protocol.

        Wrapped in a broad try so tracking failures never block the
        order flow. Each `event_kind` maps to a builder in
        `services.event_mapping` with a known signature.
        """
        try:
            from plugins.installed.tracking.services import event_mapping
            from plugins.installed.tracking.services.measurement_protocol import send_event
        except Exception as exc:  # noqa: BLE001
            logger.warning('tracking: import failed for %s: %s', event_kind, exc)
            return

        transaction_id = ctx.pop('transaction_id', '')
        try:
            if event_kind == 'purchase':
                event_name, params = event_mapping.purchase(ctx['order'])
            elif event_kind == 'refund':
                event_name, params = event_mapping.refund(
                    order=ctx['order'],
                    amount=ctx.get('amount'),
                )
            elif event_kind == 'view_item':
                event_name, params = event_mapping.view_item(ctx['product'])
            elif event_kind == 'add_to_cart':
                event_name, params = event_mapping.add_to_cart(
                    cart=ctx.get('cart'),
                    item=ctx.get('item'),
                    product=ctx['product'],
                    variant=ctx.get('variant'),
                    quantity=ctx.get('quantity', 1),
                )
            elif event_kind == 'remove_from_cart':
                event_name, params = event_mapping.remove_from_cart(
                    cart=ctx.get('cart'),
                    item=ctx.get('item'),
                    product=ctx['product'],
                    quantity=ctx.get('quantity', 1),
                )
            elif event_kind == 'begin_checkout':
                event_name, params = event_mapping.begin_checkout(ctx['cart'])
            elif event_kind == 'sign_up':
                event_name, params = 'sign_up', {'method': 'storefront'}
            elif event_kind == 'login':
                event_name, params = 'login', {'method': 'storefront'}
            elif event_kind == 'search':
                event_name, params = 'search', {'search_term': ctx.get('search_term') or ''}
            else:
                logger.debug('tracking: unknown event_kind %s', event_kind)
                return
        except Exception as exc:  # noqa: BLE001
            logger.warning('tracking: %s builder failed: %s', event_kind, exc)
            return

        try:
            send_event(event_name=event_name, params=params, transaction_id=transaction_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning('tracking: send_event(%s) failed: %s', event_name, exc)

    def contribute_dashboard_pages(self) -> list:
        # No DashboardPage — Tracking lives at /dashboard/tracking/ via
        # register_urls above and is hardcoded in admin_dashboard/base.html's
        # settings sidebar. The previous nav='hidden' DashboardPage was a
        # duplicate URL surface (/dashboard/apps/tracking/overview/) that
        # only existed to surface a card in /dashboard/apps/.
        return []

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Google Ads conversions',
            description=(
                'Optional. Fires a Google Ads conversion event on the order '
                'confirmation page. GA4 + GTM main settings live at '
                '/dashboard/tracking/ — these knobs are the Ads-specific bolt-on.'
            ),
            schema=self.get_config_schema(),
            category='channels',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                # GA4/GTM main settings live on the TrackingSettings model at
                # /dashboard/tracking/ — no mirror fields here (editing a
                # mirror was a silent no-op; nothing ever read it back).
                # Google Ads — live ONLY in PluginConfig (no model migration
                # needed). Read by the conversion-pixel template tag below.
                'google_ads_conversion_id': {
                    'type': 'string',
                    'title': 'Google Ads conversion ID',
                    'description': 'Format: AW-123456789. Leave blank to disable Ads conversion firing.',
                    'default': '',
                },
                'google_ads_purchase_label': {
                    'type': 'string',
                    'title': 'Purchase conversion label',
                    'description': 'The label half of the AW-XXX/yyy pair, e.g. "abc123XYZ".',
                    'default': '',
                },
            },
        }
