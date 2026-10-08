"""Pinterest Commerce plugin — Catalog feed + Pinterest Tag/Conversions API + Ads.

Owns the whole Pinterest channel (clean slate). Catalog feed at
/feeds/pinterest-catalog.xml, the Pinterest Tag + server-side Conversions API,
and the Ads API v5 (campaign reporting + management). Connection is a single
Bearer access token + ad-account/feed/tag IDs in PluginConfig.
"""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin, SettingsPanel, StorefrontBlock
from morpheus.core import events

logger = logging.getLogger('morpheus.pinterest_commerce')


class PinterestCommercePlugin(Plugin):
    name = 'pinterest_commerce'
    label = 'Pinterest Commerce'
    version = '0.1.0'
    description = (
        'Pinterest commerce: product catalog feed at /feeds/pinterest-catalog.xml, '
        'the Pinterest Tag + server-side Conversions API (content_ids matched to '
        'the catalog), and the Ads API v5 for campaign reporting + management. '
        'Reuses catalog price, images, inventory, identifiers and book metadata. '
        'Connection via a Bearer access token.'
    )
    has_models = True
    requires = ['catalog']

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.pinterest_commerce.urls', prefix='', namespace='pinterest_commerce'
        )
        self.register_celery_tasks('plugins.installed.pinterest_commerce.tasks')
        self.register_celery_beat(
            'pinterest_commerce:rebuild_feed',
            {'task': 'pinterest_commerce.rebuild_feed', 'schedule': 60 * 60 * 6},
        )
        for evt in (events.PRODUCT_CREATED, events.PRODUCT_UPDATED):
            self.register_hook(evt, self._bust_feed_cache, priority=80)
        self.register_hook(events.ORDER_PAID, self._on_order_paid, priority=90)
        self.register_hook(events.ADD_TO_CART, self._on_add_to_cart, priority=90)
        self.register_hook(events.CHANNELS_OVERVIEW, self._channels_row, priority=40)
        self.register_hook(events.CHANNELS_METRICS, self._channels_metrics, priority=40)

    def _channels_row(self, value, **_):
        row = {
            'name': 'pinterest_commerce',
            'label': 'Pinterest',
            'icon': 'image',
            'connected': False,
            'pixel': 'off',
            'has_feed': True,
            'eligible': None,
            'total': None,
            'coverage_pct': None,
            'dashboard_url': '/dashboard/apps/pinterest_commerce/overview/',
        }
        try:
            from plugins.installed.pinterest_commerce.services.api import (  # noqa: PLC0415
                has_token,
            )
            from plugins.installed.pinterest_commerce.services.coverage import (  # noqa: PLC0415
                coverage_report,
            )
            from plugins.installed.pinterest_commerce.services.settings import (  # noqa: PLC0415
                pinterest_settings,
            )

            row['connected'] = has_token()
            row['pixel'] = 'on' if pinterest_settings().tag_enabled else 'off'
            rep = coverage_report()
            row['eligible'] = rep.get('eligible')
            row['total'] = rep.get('total')
            row['coverage_pct'] = rep.get('eligible_pct')
        except Exception as e:  # noqa: BLE001
            logger.debug('pinterest_commerce: channels row failed: %s', e)
        value.append(row)
        return value

    def _channels_metrics(self, value, **_):
        try:
            from plugins.installed.pinterest_commerce.services.ads_api import (  # noqa: PLC0415
                campaign_report,
            )

            rep = campaign_report(days=30)
            if rep.get('ok'):
                t = rep.get('totals') or {}
                value.append(
                    {
                        'name': 'pinterest_commerce',
                        'spend': t.get('spend'),
                        'clicks': t.get('clicks'),
                        'conversions': t.get('conversions'),
                        'revenue': t.get('value') or t.get('revenue'),
                        'roas': t.get('roas'),
                    }
                )
        except Exception as e:  # noqa: BLE001
            logger.debug('pinterest_commerce: channels metrics failed: %s', e)
        return value

    def _bust_feed_cache(self, **_):
        try:
            from django.core.cache import cache  # noqa: PLC0415

            from plugins.installed.pinterest_commerce.views import FEED_CACHE_KEY  # noqa: PLC0415

            cache.delete(FEED_CACHE_KEY)
        except Exception as e:  # noqa: BLE001
            logger.debug('pinterest_commerce: cache bust failed: %s', e)

    def _on_order_paid(self, order=None, **_):
        if order is not None:
            self._capi(lambda m: m.send_checkout(order), 'checkout')

    def _on_add_to_cart(self, product=None, variant=None, quantity=1, **_):
        if product is not None or variant is not None:
            self._capi(
                lambda m: m.send_add_to_cart(product=product, variant=variant, quantity=quantity),
                'add_to_cart',
            )

    def _capi(self, fn, label: str) -> None:
        try:
            from plugins.installed.pinterest_commerce.services import capi  # noqa: PLC0415

            fn(capi)
        except Exception as e:  # noqa: BLE001 — never block the order/cart flow
            logger.debug('pinterest_commerce: capi %s failed: %s', label, e)

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='global_below_body',
                template='pinterest_commerce/blocks/tag.html',
                priority=70,
            ),
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Pinterest Commerce',
                slug='overview',
                view='plugins.installed.pinterest_commerce.views.dashboard',
                icon='image',
                section='channels',
                order=50,
                nav='main',
                group='Pinterest',
            ),
            DashboardPage(
                label='Pinterest Ads',
                slug='ads',
                view='plugins.installed.pinterest_commerce.views.ads_dashboard',
                icon='line-chart',
                section='channels',
                order=51,
                nav='main',
                group='Pinterest',
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Pinterest Commerce',
            description=(
                'Pinterest catalog feed + Tag/Conversions API + Ads. Add a Bearer '
                'access token + ad-account/tag IDs from Pinterest. The feed '
                '(/feeds/pinterest-catalog.xml) works with no credentials.'
            ),
            schema=self.get_config_schema(),
            category='channels',
        )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.pinterest_commerce.agent_tools import (
            pinterest_ads_report_tool,
            pinterest_feed_coverage_tool,
            pinterest_feed_diagnostics_tool,
            pinterest_feed_url_tool,
        )

        return [
            pinterest_feed_coverage_tool,
            pinterest_feed_url_tool,
            pinterest_feed_diagnostics_tool,
            pinterest_ads_report_tool,
        ]

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'enabled': {'type': 'boolean', 'title': 'Catalog feed enabled', 'default': True},
                'access_token': {
                    'type': 'string',
                    'title': 'Access token (Bearer)',
                    'format': 'password',
                    'description': 'Pinterest API v5 access token (Catalogs + Ads + Conversions).',
                    'default': '',
                },
                'ad_account_id': {'type': 'string', 'title': 'Ad account ID', 'default': ''},
                'catalog_feed_id': {'type': 'string', 'title': 'Catalog feed ID', 'default': ''},
                'tag_id': {'type': 'string', 'title': 'Pinterest Tag ID', 'default': ''},
                'tag_enabled': {
                    'type': 'boolean',
                    'title': 'Enable Pinterest Tag on the storefront',
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
