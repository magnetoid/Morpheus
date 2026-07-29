"""TikTok Commerce plugin — TikTok Catalog + Pixel/Events API + TikTok Ads.

Owns the whole TikTok channel (clean slate). Catalog feed at
/feeds/tiktok-catalog.xml, the TikTok Pixel + server-side Events API, and the
Marketing API (campaign reporting + management). Connection is a single access
token + advertiser/catalog/pixel IDs in PluginConfig.
"""

from __future__ import annotations

import logging

from morpheus.core import events
from morpheus.plugin import DashboardPage, Plugin, SettingsPanel, StorefrontBlock

logger = logging.getLogger('morpheus.tiktok_commerce')


class TiktokCommercePlugin(Plugin):
    name = 'tiktok_commerce'
    label = 'TikTok Commerce'
    version = '0.1.0'
    description = (
        'TikTok for Business commerce: product catalog feed at '
        '/feeds/tiktok-catalog.xml, the TikTok Pixel + server-side Events API '
        '(content_ids matched to the catalog), and the Marketing API for '
        'campaign reporting + management. Reuses catalog price, images, '
        'inventory, identifiers and book metadata. Connection via an access token.'
    )
    has_models = True
    requires = ['catalog']

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.tiktok_commerce.urls', prefix='', namespace='tiktok_commerce'
        )
        self.register_celery_tasks('plugins.installed.tiktok_commerce.tasks')
        self.register_celery_beat(
            'tiktok_commerce:rebuild_feed',
            {'task': 'tiktok_commerce.rebuild_feed', 'schedule': 60 * 60 * 6},
        )
        for evt in (events.PRODUCT_CREATED, events.PRODUCT_UPDATED):
            self.register_hook(evt, self._bust_feed_cache, priority=80)
        self.register_hook(events.ORDER_PAID, self._on_order_paid, priority=90)
        self.register_hook(events.ADD_TO_CART, self._on_add_to_cart, priority=90)
        self.register_hook(events.BEGIN_CHECKOUT, self._on_begin_checkout, priority=90)
        self.register_hook(events.CHANNELS_OVERVIEW, self._channels_row, priority=30)
        self.register_hook(events.CHANNELS_METRICS, self._channels_metrics, priority=30)

    def _channels_row(self, value, **_):
        row = {
            'name': 'tiktok_commerce',
            'label': 'TikTok',
            'icon': 'music',
            'connected': False,
            'pixel': 'off',
            'has_feed': True,
            'eligible': None,
            'total': None,
            'coverage_pct': None,
            'dashboard_url': '/dashboard/apps/tiktok_commerce/overview/',
        }
        try:
            from plugins.installed.tiktok_commerce.services.api import has_token  # noqa: PLC0415
            from plugins.installed.tiktok_commerce.services.coverage import (  # noqa: PLC0415
                coverage_report,
            )
            from plugins.installed.tiktok_commerce.services.settings import (  # noqa: PLC0415
                tiktok_settings,
            )

            row['connected'] = has_token()
            row['pixel'] = 'on' if tiktok_settings().pixel_enabled else 'off'
            rep = coverage_report()
            row['eligible'] = rep.get('eligible')
            row['total'] = rep.get('total')
            row['coverage_pct'] = rep.get('eligible_pct')
        except Exception as e:  # noqa: BLE001
            logger.debug('tiktok_commerce: channels row failed: %s', e)
        value.append(row)
        return value

    def _channels_metrics(self, value, **_):
        try:
            from plugins.installed.tiktok_commerce.services.ads_api import (  # noqa: PLC0415
                campaign_report,
            )

            rep = campaign_report(days=30)
            if rep.get('ok'):
                t = rep.get('totals') or {}
                value.append(
                    {
                        'name': 'tiktok_commerce',
                        'spend': t.get('spend'),
                        'clicks': t.get('clicks'),
                        'conversions': t.get('conversions'),
                        'revenue': t.get('value') or t.get('revenue'),
                        'roas': t.get('roas'),
                    }
                )
        except Exception as e:  # noqa: BLE001
            logger.debug('tiktok_commerce: channels metrics failed: %s', e)
        return value

    def _bust_feed_cache(self, **_):
        try:
            from django.core.cache import cache  # noqa: PLC0415

            from plugins.installed.tiktok_commerce.views import FEED_CACHE_KEY  # noqa: PLC0415

            cache.delete(FEED_CACHE_KEY)
        except Exception as e:  # noqa: BLE001
            logger.debug('tiktok_commerce: cache bust failed: %s', e)

    def _on_order_paid(self, order=None, **_):
        if order is not None:
            self._event(lambda m: m.send_complete_payment(order), 'complete_payment')

    def _on_add_to_cart(self, product=None, variant=None, quantity=1, **_):
        if product is not None or variant is not None:
            self._event(
                lambda m: m.send_add_to_cart(product=product, variant=variant, quantity=quantity),
                'add_to_cart',
            )

    def _on_begin_checkout(self, cart=None, **_):
        if cart is not None:
            self._event(lambda m: m.send_initiate_checkout(cart), 'begin_checkout')

    def _event(self, fn, label: str) -> None:
        try:
            from plugins.installed.tiktok_commerce.services import events_api  # noqa: PLC0415

            fn(events_api)
        except Exception as e:  # noqa: BLE001 — never block the order/cart flow
            logger.debug('tiktok_commerce: events %s failed: %s', label, e)

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='global_below_body',
                template='tiktok_commerce/blocks/pixel.html',
                priority=70,
            ),
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='TikTok Commerce',
                slug='overview',
                view='plugins.installed.tiktok_commerce.views.dashboard',
                icon='music',
                section='marketing',
                order=64,
                nav='main',
            ),
            DashboardPage(
                label='TikTok Ads',
                slug='ads',
                view='plugins.installed.tiktok_commerce.views.ads_dashboard',
                icon='bar-chart-3',
                section='marketing',
                order=65,
                nav='main',
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='TikTok Commerce',
            description=(
                'TikTok catalog feed + Pixel/Events API + Ads. Add an access token '
                '+ advertiser/catalog/pixel IDs from TikTok for Business. The feed '
                '(/feeds/tiktok-catalog.xml) works with no credentials.'
            ),
            schema=self.get_config_schema(),
            category='channels',
        )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.tiktok_commerce.agent_tools import (
            tiktok_ads_report_tool,
            tiktok_catalog_diagnostics_tool,
            tiktok_feed_coverage_tool,
            tiktok_feed_url_tool,
        )

        return [
            tiktok_feed_coverage_tool,
            tiktok_feed_url_tool,
            tiktok_catalog_diagnostics_tool,
            tiktok_ads_report_tool,
        ]

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'enabled': {'type': 'boolean', 'title': 'Catalog feed enabled', 'default': True},
                'access_token': {
                    'type': 'string',
                    'title': 'Access token',
                    'format': 'password',
                    'description': 'Long-lived TikTok for Business access token (Catalog + Ads + Events).',
                    'default': '',
                },
                'advertiser_id': {'type': 'string', 'title': 'Advertiser ID', 'default': ''},
                'catalog_id': {'type': 'string', 'title': 'Catalog ID', 'default': ''},
                'bc_id': {
                    'type': 'string',
                    'title': 'Business Center ID (optional)',
                    'description': 'Needed by the catalog diagnostics API for some catalog types.',
                    'default': '',
                },
                'pixel_code': {'type': 'string', 'title': 'Pixel code', 'default': ''},
                'pixel_enabled': {
                    'type': 'boolean',
                    'title': 'Enable TikTok Pixel on the storefront',
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
