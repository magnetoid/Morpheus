"""Digital Products plugin manifest.

Wires download delivery for digital order lines (library.py has the rule):

  * When an order is delivered (paid; placed to be paid later; fulfilled), create a
    ``DownloadToken`` for every digital line and fire ``digital.tokens_issued`` so
    the email layer mails the links.
  * Answers ``ORDER_LINE_DELIVERY`` so the order pages show each line's download.
  * Exposes ``/digital/download/<token>/`` — token-protected file serve
    with expiry + download-count limits.
  * Configurable defaults via the schema panel: token TTL (hours) and
    max downloads per token.
"""

# Handlers use lazy imports (load-order-safe; the established plugin pattern).
# ruff: noqa: PLC0415, I001
from __future__ import annotations

import logging

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock
from morpheus.core import events

logger = logging.getLogger('morpheus.digital_products')


class DigitalProductsPlugin(Plugin):
    name = 'digital_products'
    label = 'Digital Products'
    version = '0.1.0'
    description = (
        'Sell digital downloads — token-protected delivery, expiry, '
        'count limits, automatic email after payment.'
    )
    has_models = True
    requires = ['orders', 'catalog']

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.digital_products.urls',
            prefix='digital/',
            namespace='digital_products',
        )
        # Own /account/downloads/ at the site root — only while enabled (ADR 0013).
        self.register_urls(
            'plugins.installed.digital_products.storefront_urls',
            prefix='',
            namespace='digital_products_account',
        )
        self.register_celery_tasks('plugins.installed.digital_products.tasks')
        self.register_hook(events.ORDER_PAID, self.on_order_paid, priority=80)
        # An order paid later (cash on delivery, bank transfer) delivers when placed.
        self.register_hook(events.ORDER_PLACED, self.on_order_placed, priority=80)
        # Fulfilling or shipping an order delivers its digital lines (library.py).
        self.register_hook(events.ORDER_FULFILLED, self.on_order_paid, priority=80)
        # Contribute the size of the customer's library into the account summary —
        # only while enabled, so disabling the plugin removes the Library tile
        # (ADR 0013) instead of storefront hard-coding the query.
        self.register_hook(events.ACCOUNT_SUMMARY_FIELDS, self.on_account_summary, priority=40)
        self.register_hook(events.ORDER_LINE_DELIVERY, self.on_line_delivery, priority=50)
        self._register_beat_schedule()

    def contribute_storefront_blocks(self) -> list:
        # Account-home tile → /account/downloads/ (the library). Lives with the plugin so a
        # disabled plugin drops the tile (registry-gated contribution).
        return [
            StorefrontBlock(
                slot='account_nav',
                template='digital_products/blocks/account_nav.html',
                priority=45,
            ),
        ]

    def on_line_delivery(self, value, order_item=None, **kwargs):
        if order_item is None:
            return value
        try:
            from plugins.installed.digital_products.library import line_delivery

            return line_delivery(order_item) or value
        except Exception as exc:  # noqa: BLE001 — an order page must still render
            logger.warning('order line delivery failed: %s', exc, exc_info=True)
            return value

    def on_order_placed(self, order, **kwargs) -> None:
        """ORDER_PLACED fires inside checkout's transaction: issue the links once it
        commits, so a rolled-back checkout mails nothing and a failure here cannot
        abort the order."""
        from django.db import transaction

        order_id = order.pk

        def issue():
            from plugins.installed.orders.models import Order

            placed = Order.objects.filter(pk=order_id).first()
            if placed is not None:
                self.on_order_paid(placed)

        transaction.on_commit(issue)

    def on_account_summary(self, value, user=None, **kwargs):
        """Fold the size of this customer's library into the account summary.
        Mutate the dict + return it; fail-soft — never break the account page."""
        if user is None:
            return value
        try:
            from plugins.installed.digital_products.library import count

            n = count(user)
            if n:
                value['library_count'] = n
        except Exception as exc:  # noqa: BLE001
            logging.getLogger('morpheus.digital_products').warning(
                'account_summary library fold failed: %s', exc, exc_info=True
            )
        return value

    def _register_beat_schedule(self) -> None:
        from django.conf import settings as dj_settings
        from celery.schedules import crontab

        schedule = getattr(dj_settings, 'CELERY_BEAT_SCHEDULE', None)
        if schedule is None:
            return
        # Daily at 03:30 — quiet hours, after most order activity.
        schedule.setdefault(
            'digital_products.cleanup_expired_tokens',
            {
                'task': 'digital_products.cleanup_expired_tokens',
                'schedule': crontab(hour=3, minute=30),
            },
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'token_ttl_hours': {
                    'type': 'integer',
                    'title': 'Token expiry (hours)',
                    'default': 168,
                    'minimum': 1,
                    'description': 'How long a download link stays valid. Default 7 days.',
                },
                'max_downloads_per_token': {
                    'type': 'integer',
                    'title': 'Max downloads per token',
                    'default': 5,
                    'minimum': 1,
                    'description': 'How many times a single link can be used.',
                },
            },
        }

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Digital downloads',
            description='Token expiry and download limits for digital products.',
            schema=self.get_config_schema(),
            category='general',
        )

    def on_order_paid(self, order, **kwargs) -> None:
        """Mint a DownloadToken for each delivered digital line that has a file, and
        fire ``digital.tokens_issued`` so the email layer sends the links.

        Runs on payment, on placing an order paid later and on fulfilment
        (``library.is_delivered``). Idempotent per line:
        a line that already has a link gets none, so a second payment or a fulfil
        after payment sends nothing twice, while an audiobook narrated after the
        payment gets its link on the next delivery event.
        """
        from datetime import timedelta
        from django.utils import timezone
        from plugins.installed.digital_products.library import (
            delivery_file,
            is_delivered,
            is_digital,
        )
        from plugins.installed.digital_products.models import DownloadToken

        if not is_delivered(order):
            return
        cfg = self.get_config()
        ttl_hours = int(cfg.get('token_ttl_hours', 168) or 168)
        max_dl = int(cfg.get('max_downloads_per_token', 5) or 5)
        expires_at = timezone.now() + timedelta(hours=ttl_hours)

        done = set(
            DownloadToken.objects.filter(order=order).values_list('order_item_id', flat=True)
        )
        tokens = []
        for item in order.items.select_related('product', 'variant'):
            product = item.product
            if product is None or item.pk in done:
                continue
            if not is_digital(item) or not delivery_file(item):
                continue
            tokens.append(
                DownloadToken.objects.create(
                    order=order,
                    order_item=item,
                    product=product,
                    expires_at=expires_at,
                    max_downloads=max_dl,
                )
            )

        if not tokens:
            return

        from morpheus.core import hooks

        try:
            hooks.fire('digital.tokens_issued', order=order, tokens=tokens)
        except Exception as e:  # noqa: BLE001 — never block payment finalisation
            logger.warning('digital.tokens_issued fire failed: %s', e, exc_info=True)
