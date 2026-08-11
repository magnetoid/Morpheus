"""Meta Commerce plugin — Meta (Facebook/Instagram) Catalog + Pixel/CAPI + Ads.

Owns the whole Meta surface (clean slate; `tracking` is Google-only): the product
catalog feed at /feeds/meta-catalog.xml, Catalog API push, the Meta Pixel +
Conversions API, and the Marketing API (campaign reporting + management).
Connection is a single long-lived System User access token + IDs in PluginConfig.
"""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin, SettingsPanel, StorefrontBlock
from morpheus.core import events

logger = logging.getLogger('morpheus.meta_commerce')


class MetaCommercePlugin(Plugin):
    name = 'meta_commerce'
    label = 'Meta Commerce'
    version = '0.1.0'
    description = (
        'Meta (Facebook/Instagram) commerce: product catalog feed at '
        '/feeds/meta-catalog.xml + Catalog API push, the Meta Pixel + '
        'Conversions API (content_ids matched to the catalog), and the Marketing '
        'API for campaign reporting + management. Reuses catalog price, images, '
        'inventory, identifiers and book metadata. Connection via a System User '
        'access token in settings.'
    )
    has_models = True
    requires = ['catalog']

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.meta_commerce.urls', prefix='', namespace='meta_commerce'
        )
        self.register_celery_tasks('plugins.installed.meta_commerce.tasks')
        self.register_celery_beat(
            'meta_commerce:catalog_push',
            {'task': 'meta_commerce.push_catalog', 'schedule': 60 * 60 * 6},
        )
        for evt in (events.PRODUCT_CREATED, events.PRODUCT_UPDATED):
            self.register_hook(evt, self._bust_feed_cache, priority=80)
        # Server-side Conversions API funnel — iOS-safe, ad-blocker-proof signal
        # that sharpens dynamic-ads / Advantage+ optimisation.
        self.register_hook(events.ORDER_PAID, self._on_order_paid, priority=90)
        self.register_hook(events.ADD_TO_CART, self._on_add_to_cart, priority=90)
        self.register_hook(events.BEGIN_CHECKOUT, self._on_begin_checkout, priority=90)
        self.register_hook(events.CHANNELS_OVERVIEW, self._channels_row, priority=20)
        self.register_hook(events.CHANNELS_METRICS, self._channels_metrics, priority=20)
        self.register_hook(events.ANALYTICS_AD_SPEND, self._ad_spend, priority=20)

    def _ad_spend(self, value, **_):
        """Contribute Meta's 30-day ad spend to the attribution ROAS pipeline."""
        try:
            from plugins.installed.meta_commerce.services.ads_api import (  # noqa: PLC0415
                campaign_report,
            )

            rep = campaign_report(days=30)
            spend = (rep.get('totals') or {}).get('spend') if rep.get('ok') else None
            if spend:
                value.append({'channel': 'meta', 'spend': spend, 'days': 30})
        except Exception as e:  # noqa: BLE001
            logger.debug('meta_commerce: ad_spend failed: %s', e)
        return value

    def _channels_row(self, value, **_):
        row = {
            'name': 'meta_commerce',
            'label': 'Meta',
            'icon': 'facebook',
            'connected': False,
            'pixel': 'off',
            'has_feed': True,
            'eligible': None,
            'total': None,
            'coverage_pct': None,
            'dashboard_url': '/dashboard/apps/meta_commerce/overview/',
        }
        try:
            from plugins.installed.meta_commerce.services.coverage import (  # noqa: PLC0415
                coverage_report,
            )
            from plugins.installed.meta_commerce.services.graph import has_token  # noqa: PLC0415
            from plugins.installed.meta_commerce.services.settings import (  # noqa: PLC0415
                meta_settings,
            )

            row['connected'] = has_token()
            row['pixel'] = 'on' if meta_settings().pixel_enabled else 'off'
            rep = coverage_report()
            row['eligible'] = rep.get('eligible')
            row['total'] = rep.get('total')
            row['coverage_pct'] = rep.get('eligible_pct')
        except Exception as e:  # noqa: BLE001
            logger.debug('meta_commerce: channels row failed: %s', e)
        value.append(row)
        return value

    def _channels_metrics(self, value, **_):
        try:
            from plugins.installed.meta_commerce.services.ads_api import (  # noqa: PLC0415
                campaign_report,
            )

            rep = campaign_report(days=30)
            if rep.get('ok'):
                t = rep.get('totals') or {}
                value.append(
                    {
                        'name': 'meta_commerce',
                        'spend': t.get('spend'),
                        'clicks': t.get('clicks'),
                        'conversions': t.get('conversions'),
                        'revenue': t.get('value') or t.get('revenue'),
                        'roas': t.get('roas'),
                    }
                )
        except Exception as e:  # noqa: BLE001
            logger.debug('meta_commerce: channels metrics failed: %s', e)
        return value

    def _bust_feed_cache(self, **_):
        try:
            from django.core.cache import cache  # noqa: PLC0415

            from plugins.installed.meta_commerce.views import FEED_CACHE_KEY  # noqa: PLC0415

            cache.delete(FEED_CACHE_KEY)
        except Exception as e:  # noqa: BLE001
            logger.debug('meta_commerce: cache bust failed: %s', e)

    def _on_order_paid(self, order=None, **_):
        if order is None:
            return
        self._capi(lambda m: m.send_purchase(order), 'purchase')

    def _on_add_to_cart(self, product=None, variant=None, quantity=1, **_):
        if product is None and variant is None:
            return
        self._capi(
            lambda m: m.send_add_to_cart(product=product, variant=variant, quantity=quantity),
            'add_to_cart',
        )

    def _on_begin_checkout(self, cart=None, **_):
        if cart is None:
            return
        self._capi(lambda m: m.send_initiate_checkout(cart), 'begin_checkout')

    def _capi(self, fn, label: str) -> None:
        """Run a CAPI send, swallowing every error — must never block the flow."""
        try:
            from plugins.installed.meta_commerce.services import capi  # noqa: PLC0415

            fn(capi)
        except Exception as e:  # noqa: BLE001
            logger.debug('meta_commerce: CAPI %s failed: %s', label, e)

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='global_below_body',
                template='meta_commerce/blocks/pixel.html',
                priority=70,
            ),
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Meta Commerce',
                slug='overview',
                view='plugins.installed.meta_commerce.views.dashboard',
                icon='facebook',
                section='marketing',
                order=62,
                nav='main',
            ),
            DashboardPage(
                label='Meta Ads',
                slug='ads',
                view='plugins.installed.meta_commerce.views.ads_dashboard',
                icon='trending-up',
                section='marketing',
                order=63,
                nav='main',
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Meta Commerce',
            description=(
                'Meta catalog feed + Pixel/CAPI + Ads. Add a System User access '
                'token + IDs from Business Settings. The feed (/feeds/meta-catalog.xml) '
                'works with no credentials; the API push, Pixel and Ads need the token.'
            ),
            schema=self.get_config_schema(),
            category='channels',
        )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.meta_commerce.agent_tools import (
            meta_ads_report_tool,
            meta_catalog_diagnostics_tool,
            meta_feed_coverage_tool,
            meta_feed_url_tool,
            meta_rebuild_feed_tool,
            meta_sync_audience_tool,
        )

        return [
            meta_feed_coverage_tool,
            meta_feed_url_tool,
            meta_rebuild_feed_tool,
            meta_catalog_diagnostics_tool,
            meta_ads_report_tool,
            meta_sync_audience_tool,
        ]

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'enabled': {'type': 'boolean', 'title': 'Catalog feed enabled', 'default': True},
                'access_token': {
                    'type': 'string',
                    'title': 'System User access token',
                    'format': 'password',
                    'description': 'Long-lived token from Business Settings → System Users (Catalog + Ads + CAPI).',
                    'default': '',
                },
                'catalog_id': {'type': 'string', 'title': 'Catalog ID', 'default': ''},
                'ad_account_id': {
                    'type': 'string',
                    'title': 'Ad account ID',
                    'description': 'Digits only or act_… — used by the Marketing API.',
                    'default': '',
                },
                'pixel_id': {'type': 'string', 'title': 'Pixel ID', 'default': ''},
                'business_id': {'type': 'string', 'title': 'Business ID (optional)', 'default': ''},
                'pixel_enabled': {
                    'type': 'boolean',
                    'title': 'Enable Meta Pixel on the storefront',
                    'default': False,
                },
                'country': {'type': 'string', 'title': 'Target country (ISO)', 'default': 'US'},
                'default_brand': {'type': 'string', 'title': 'Default brand', 'default': ''},
                'default_condition': {
                    'type': 'string',
                    'title': 'Default condition',
                    'enum': ['new', 'refurbished', 'used'],
                    'default': 'new',
                },
                'include_out_of_stock': {
                    'type': 'boolean',
                    'title': 'Include out-of-stock products',
                    'default': True,
                },
                'feed_title': {'type': 'string', 'title': 'Feed title', 'default': 'Dot Books'},
            },
        }
