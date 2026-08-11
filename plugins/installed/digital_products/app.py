"""Digital Products plugin manifest.

Wires download fulfilment for `product_type == 'digital'` items:

  * On `events.ORDER_PAID`, create a ``DownloadToken`` for every digital
    order line and fire the ``digital.tokens_issued`` event so the email
    layer can mail the customer.
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
        # Contribute the customer's active-download count into the account
        # summary — only while enabled, so disabling the plugin removes the
        # Downloads tile (ADR 0013) instead of storefront hard-coding the query.
        self.register_hook(events.ACCOUNT_SUMMARY_FIELDS, self.on_account_summary, priority=40)
        self._register_beat_schedule()

    def contribute_storefront_blocks(self) -> list:
        # Account-home tile → /account/downloads/. Lives with the plugin so a
        # disabled plugin drops the tile (registry-gated contribution).
        return [
            StorefrontBlock(
                slot='account_nav',
                template='digital_products/blocks/account_nav.html',
                priority=45,
            ),
        ]

    def on_account_summary(self, value, user=None, **kwargs):
        """Fold this customer's active download count into the account summary.
        Mutate the dict + return it; fail-soft — never break the account page."""
        if user is None:
            return value
        try:
            from django.utils import timezone

            from plugins.installed.digital_products.models import DownloadToken

            count = DownloadToken.objects.filter(
                order__customer=user,
                expires_at__gt=timezone.now(),
                revoked_at__isnull=True,
            ).count()
            if count:
                value['download_count'] = count
        except Exception as exc:  # noqa: BLE001
            logging.getLogger('morpheus.digital_products').warning(
                'account_summary download fold failed: %s', exc, exc_info=True
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
        """Mint DownloadTokens for each digital line on a paid order, fire
        the ``digital.tokens_issued`` event so the email layer ships them.
        """
        from datetime import timedelta
        from django.utils import timezone
        from plugins.installed.digital_products.models import DownloadToken

        # Idempotent: ORDER_PAID can fire more than once (a manual "mark paid"
        # after a gateway payment, a second successful transaction) and this used
        # to mint a fresh set of tokens + send a duplicate download email each
        # time. If this order already has tokens, do nothing.
        if DownloadToken.objects.filter(order=order).exists():
            return

        cfg = self.get_config()
        ttl_hours = int(cfg.get('token_ttl_hours', 168) or 168)
        max_dl = int(cfg.get('max_downloads_per_token', 5) or 5)
        expires_at = timezone.now() + timedelta(hours=ttl_hours)

        tokens = []
        for item in order.items.all():
            product = getattr(item, 'product', None)
            if product is None:
                continue
            variant = getattr(item, 'variant', None)

            # Resolve the actual file to deliver. Variant-level file wins
            # (lets a single product sell PDF + EPUB + MP3 as separate
            # variants); falls back to the product-level digital_file
            # (single-SKU digital products).
            variant_is_digital = bool(
                variant and getattr(variant, 'variant_type', '') in ('digital', 'audiobook')
            )
            variant_has_file = bool(variant and getattr(variant, 'digital_file', None))
            product_has_file = bool(getattr(product, 'digital_file', None))

            # Issue a token when there's actually a file to deliver:
            #   - product_type='digital' + product.digital_file set, OR
            #   - the ordered variant is variant_type='digital' + has its
            #     own digital_file (most common case for multi-format books).
            ptype = getattr(product, 'product_type', '')
            if variant_is_digital and variant_has_file:
                # variant-level digital — fine regardless of product_type
                pass
            elif ptype == 'digital' and product_has_file:
                # single-SKU digital — legacy / simple case
                pass
            else:
                continue

            tok = DownloadToken.objects.create(
                order=order,
                order_item=item,
                product=product,
                expires_at=expires_at,
                max_downloads=max_dl,
            )
            tokens.append(tok)

        if not tokens:
            return

        from morpheus.core import hooks

        try:
            hooks.fire('digital.tokens_issued', order=order, tokens=tokens)
        except Exception as e:  # noqa: BLE001 — never block payment finalisation
            logger.warning('digital.tokens_issued fire failed: %s', e, exc_info=True)
