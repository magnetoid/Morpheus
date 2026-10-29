"""Tracking plugin — GA4 (server) + GTM (client) for Morpheus.

* Server-side: subscribes to the hook bus and POSTs to the GA4
  Measurement Protocol v2.
* Client-side: contributes the GTM container (or GA4's gtag.js when no
  container is set) to every theme's `global_head`, plus per-event
  dataLayer push partials.
* Backend control center at `/dashboard/tracking/` with tabs for
  Connection / Event firing / Consent / Identity / Filters / Tests.
"""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin, SettingsPanel, StorefrontBlock
from morpheus.core import events

logger = logging.getLogger('morpheus.tracking')


def _is_crawler(request) -> bool:
    from core.utils.crawlers import is_crawler_user_agent  # noqa: PLC0415

    ua = (request.META.get('HTTP_USER_AGENT') or '') if request is not None else ''
    return is_crawler_user_agent(ua)


def _tracking_settings():
    try:
        from plugins.installed.tracking.models import TrackingSettings

        return TrackingSettings.get_solo()
    except Exception:  # noqa: BLE001 — table missing pre-migration: send nothing
        return None


def _filtered(s, request) -> bool:
    """Settings → Tracking → Filters: a blocked path or a listed user agent."""
    if request is None:
        return False
    if s.is_path_blocked(getattr(request, 'path', '') or ''):
        return True
    ua = (request.META.get('HTTP_USER_AGENT') or '').lower()
    return any(p.lower() in ua for p in (s.bot_patterns or []) if p)


class TrackingPlugin(Plugin):
    name = 'tracking'
    label = 'Tracking (GA4 + GTM)'
    version = '0.1.0'
    description = (
        'Comprehensive Google Analytics 4 + Google Tag Manager integration. '
        'Server-side firing via Measurement Protocol v2, client-side via '
        'GTM (or GA4 gtag.js) on every theme. Consent Mode v2, per-event toggles, audit '
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
        # The visit's GA ids go on the order early, so a later subscriber that
        # saves the order keeps them.
        self.register_hook(events.ORDER_PLACED, self.on_order_placed, priority=5)
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

    def on_order_placed(self, order=None, **_):
        """Remember the shopper's GA client and session on the order: the purchase
        is usually confirmed by a payment webhook, where no browser is present."""
        from core.errors.context import current_request
        from plugins.installed.tracking.services.identity import ga_ids

        s = _tracking_settings()
        request = current_request.get()
        if order is None or s is None or request is None:
            return
        ids = ga_ids(request, s.measurement_id)
        if not ids:
            return
        order.metadata = {**(order.metadata or {}), 'ga': ids}
        try:
            # Not save(): the order's own save signals have run for this order already.
            type(order).objects.filter(pk=order.pk).update(metadata=order.metadata)
        except Exception as exc:  # noqa: BLE001 — tracking never breaks checkout
            logger.warning('tracking: could not stamp GA ids on %s: %s', order.pk, exc)

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

    def on_add_to_cart(
        self, cart=None, item=None, product=None, variant=None, quantity=1, request=None, **_
    ):
        if product is None:
            return
        self._fire(
            'add_to_cart',
            cart=cart,
            item=item,
            product=product,
            variant=variant,
            quantity=quantity,
            request=request,
        )

    def on_remove_from_cart(
        self, cart=None, item=None, product=None, quantity=1, request=None, **_
    ):
        if product is None:
            return
        self._fire(
            'remove_from_cart',
            cart=cart,
            item=item,
            product=product,
            quantity=quantity,
            request=request,
        )

    def on_begin_checkout(self, cart=None, request=None, **_):
        if cart is None:
            return
        self._fire('begin_checkout', cart=cart, request=request)

    def on_product_viewed(self, product=None, request=None, **_):
        # A product page is a GET, so crawlers fire this as often as shoppers
        # (~9 in 10 hits on the live stores). GA4 filters known bots only for
        # hits it sees from the browser; a Measurement Protocol hit carries our
        # server's user agent, so the crawler check has to happen here.
        if product is None or _is_crawler(request):
            return
        self._fire('view_item', product=product, request=request)

    def on_signup(self, customer=None, **_):
        self._fire('sign_up', customer=customer)

    def on_login(self, customer=None, request=None, **_):
        self._fire('login', customer=customer, request=request)

    def on_search(self, search_term='', request=None, **_):
        self._fire('search', search_term=search_term, request=request)

    def _fire(self, event_kind: str, **ctx) -> None:  # noqa: PLR0912, PLR0911, C901
        """Build the GA4 payload and POST via Measurement Protocol.

        Wrapped in a broad try so tracking failures never block the
        order flow. Each `event_kind` maps to a builder in
        `services.event_mapping` with a known signature.
        """
        from core.consent import allowed
        from plugins.installed.tracking.templatetags.tracking import browser_tagging

        request = ctx.pop('request', None)
        s = _tracking_settings()
        # Nothing to send to: no queued task and no error row per product view.
        if s is None or not s.server_side_enabled or not (s.measurement_id and s.api_secret):
            return
        if _filtered(s, request):
            return
        # The browser's tag sends view_item from the product page; a second copy
        # from here would count every product view twice.
        if event_kind == 'view_item' and browser_tagging(s):
            return
        # Consent (core/consent.py): the order's stamp, else the visitor's
        # request, else the store — a store that manages consent sends nothing
        # it cannot show the shopper agreed to (sign_up has neither: not sent).
        order = ctx.get('order')
        override = bool(s.consent_override)
        if not (override or allowed('analytics', order=order, request=request)):
            return
        ads = (
            'GRANTED'
            if override or allowed('marketing', order=order, request=request)
            else 'DENIED'
        )
        try:
            identity = self._identity(s, order=order, request=request, customer=ctx.get('customer'))
        except Exception as exc:  # noqa: BLE001 — an unjoined hit beats none
            logger.warning('tracking: identity for %s failed: %s', event_kind, exc)
            identity = {}

        try:
            from plugins.installed.tracking.services import event_mapping
            from plugins.installed.tracking.tasks import send_event_task
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

        # Queued, not sent: the POST to Google must never hold the shopper's
        # request (product page, add to cart, checkout) open.
        try:
            send_event_task.delay(
                event_name=event_name,
                params=params,
                transaction_id=transaction_id,
                consent={'ad_user_data': ads, 'ad_personalization': ads},
                **identity,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning('tracking: could not queue %s: %s', event_name, exc)

    @staticmethod
    def _identity(s, *, order=None, request=None, customer=None) -> dict:
        """client_id / session_id (the browser's, else the order's stamp) and the
        hashed user_id when Settings → Tracking → Identity turns it on."""
        from plugins.installed.tracking.services.identity import ga_ids, user_id

        ids = ga_ids(request, s.measurement_id) if request is not None else {}
        if not ids and order is not None:
            stamp = (getattr(order, 'metadata', None) or {}).get('ga')
            ids = {k: str(v) for k, v in stamp.items()} if isinstance(stamp, dict) else {}
        out = {k: ids[k] for k in ('client_id', 'session_id') if ids.get(k)}
        if s.user_id_enabled:
            pk = getattr(order, 'customer_id', None) if order is not None else None
            if pk is None and customer is not None:
                pk = getattr(customer, 'pk', None)
            if pk is None and request is not None:
                user = getattr(request, 'user', None)
                pk = user.pk if getattr(user, 'is_authenticated', False) else None
            if pk is not None:
                out['user_id'] = user_id(pk)
        return out

    def contribute_storefront_blocks(self) -> list[StorefrontBlock]:
        # Every theme emits both slots (themes/test_global_slots.py), so every
        # store gets the tags, and a disabled app takes them along. Priority 0:
        # the Consent Mode defaults must precede every other Google tag.
        return [
            StorefrontBlock(slot='global_head', template='tracking/blocks/head.html', priority=0),
            StorefrontBlock(
                slot='global_below_body', template='tracking/blocks/noscript.html', priority=0
            ),
        ]

    def contribute_dashboard_pages(self) -> list:
        # A tool card on Settings › Sales channels, beside the Google Ads
        # conversions panel, linking the control centre at /dashboard/tracking/
        # (register_urls above). The shell used to hardcode this card; an app
        # page has to leave with its app.
        return [
            DashboardPage(
                label='Tracking',
                slug='overview',
                view='plugins.installed.tracking.views.overview',
                icon='activity',
                section='channels',
                nav='settings',
                order=40,
                url='/dashboard/tracking/',
                hint='GA4 and GTM, event firing, consent',
            )
        ]

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
