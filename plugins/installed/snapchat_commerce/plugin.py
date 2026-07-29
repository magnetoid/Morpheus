"""Snapchat Commerce plugin — Snap Catalog feed + Pixel + Conversions API + Ads.

Owns the whole Snapchat channel. Product catalog feed at
/feeds/snapchat-catalog.xml (for Dynamic Ads), the Snap Pixel (snaptr) +
server-side Conversions API (item_ids matched to the catalog), and the Snapchat
Marketing API (campaign reporting + management). Connection is an OAuth refresh
token + ad account/pixel IDs in PluginConfig.
"""

from __future__ import annotations

import logging

from morpheus.core import events
from morpheus.plugin import DashboardPage, Plugin, SettingsPanel, StorefrontBlock

logger = logging.getLogger('morpheus.snapchat_commerce')


class SnapchatCommercePlugin(Plugin):
    name = 'snapchat_commerce'
    label = 'Snapchat Commerce'
    version = '0.1.0'
    description = (
        'Snapchat for Business commerce: product catalog feed at '
        '/feeds/snapchat-catalog.xml (Dynamic Ads), the Snap Pixel + '
        'server-side Conversions API (item_ids matched to the catalog), and the '
        'Marketing API for campaign reporting + management. Reuses catalog price, '
        'images, inventory, identifiers and book metadata. Connection via OAuth.'
    )
    has_models = True
    requires = ['catalog']

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.snapchat_commerce.urls', prefix='', namespace='snapchat_commerce'
        )
        self.register_celery_tasks('plugins.installed.snapchat_commerce.tasks')
        self.register_celery_beat(
            'snapchat_commerce:rebuild_feed',
            {'task': 'snapchat_commerce.rebuild_feed', 'schedule': 60 * 60 * 6},
        )
        for evt in (events.PRODUCT_CREATED, events.PRODUCT_UPDATED):
            self.register_hook(evt, self._bust_feed_cache, priority=80)
        self.register_hook(events.ORDER_PAID, self._on_order_paid, priority=90)
        self.register_hook(events.CHANNELS_OVERVIEW, self._channels_row, priority=55)
        self.register_hook(events.CHANNELS_METRICS, self._channels_metrics, priority=55)

    def _channels_row(self, value, **_):
        row = {
            'name': 'snapchat_commerce',
            'label': 'Snapchat',
            'icon': 'ghost',
            'connected': False,
            'pixel': 'off',
            'has_feed': True,
            'eligible': None,
            'total': None,
            'coverage_pct': None,
            'dashboard_url': '/dashboard/apps/snapchat_commerce/overview/',
        }
        try:
            from plugins.installed.snapchat_commerce.services.coverage import (  # noqa: PLC0415
                coverage_report,
            )
            from plugins.installed.snapchat_commerce.services.oauth import (  # noqa: PLC0415
                is_connected,
            )
            from plugins.installed.snapchat_commerce.services.settings import (  # noqa: PLC0415
                snapchat_settings,
            )

            row['connected'] = is_connected()
            row['pixel'] = 'on' if snapchat_settings().pixel_enabled else 'off'
            rep = coverage_report()
            row['eligible'] = rep.get('eligible')
            row['total'] = rep.get('total')
            row['coverage_pct'] = rep.get('eligible_pct')
        except Exception as e:  # noqa: BLE001
            logger.debug('snapchat_commerce: channels row failed: %s', e)
        value.append(row)
        return value

    def _channels_metrics(self, value, **_):
        try:
            from plugins.installed.snapchat_commerce.services.ads_api import (  # noqa: PLC0415
                campaign_report,
            )

            rep = campaign_report(days=30)
            if rep.get('ok'):
                t = rep.get('totals') or {}
                value.append(
                    {
                        'name': 'snapchat_commerce',
                        'spend': t.get('spend'),
                        'clicks': t.get('clicks'),
                        'conversions': t.get('conversions'),
                        'revenue': t.get('value') or t.get('revenue'),
                        'roas': t.get('roas'),
                    }
                )
        except Exception as e:  # noqa: BLE001
            logger.debug('snapchat_commerce: channels metrics failed: %s', e)
        return value

    def _bust_feed_cache(self, **_):
        try:
            from django.core.cache import cache  # noqa: PLC0415

            from plugins.installed.snapchat_commerce.views import FEED_CACHE_KEY  # noqa: PLC0415

            cache.delete(FEED_CACHE_KEY)
        except Exception as e:  # noqa: BLE001
            logger.debug('snapchat_commerce: cache bust failed: %s', e)

    def _on_order_paid(self, order=None, **_):
        if order is None:
            return
        try:
            from plugins.installed.snapchat_commerce.services import capi  # noqa: PLC0415

            capi.send_purchase(order)
        except Exception as e:  # noqa: BLE001 — never block the order flow
            logger.debug('snapchat_commerce: CAPI purchase failed: %s', e)

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='global_below_body',
                template='snapchat_commerce/blocks/pixel.html',
                priority=70,
            ),
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Snapchat Commerce',
                slug='overview',
                view='plugins.installed.snapchat_commerce.views.dashboard',
                icon='ghost',
                section='marketing',
                order=66,
                nav='main',
            ),
            DashboardPage(
                label='Snapchat Ads',
                slug='ads',
                view='plugins.installed.snapchat_commerce.views.ads_dashboard',
                icon='bar-chart-3',
                section='marketing',
                order=67,
                nav='main',
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Snapchat Commerce',
            description=(
                'Snapchat catalog feed + Pixel/Conversions API + Ads. Add an OAuth '
                'refresh token + ad account/pixel IDs from Snapchat Business. The feed '
                '(/feeds/snapchat-catalog.xml) works with no credentials.'
            ),
            schema=self.get_config_schema(),
            category='channels',
        )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.snapchat_commerce.agent_tools import (
            snapchat_ads_report_tool,
            snapchat_feed_coverage_tool,
            snapchat_feed_url_tool,
        )

        return [
            snapchat_feed_coverage_tool,
            snapchat_feed_url_tool,
            snapchat_ads_report_tool,
        ]

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'enabled': {'type': 'boolean', 'title': 'Catalog feed enabled', 'default': True},
                'client_id': {'type': 'string', 'title': 'OAuth client ID', 'default': ''},
                'client_secret': {
                    'type': 'string',
                    'title': 'OAuth client secret',
                    'format': 'password',
                    'default': '',
                },
                'refresh_token': {
                    'type': 'string',
                    'title': 'OAuth refresh token',
                    'format': 'password',
                    'description': 'Long-lived Snapchat Marketing API refresh token.',
                    'default': '',
                },
                'ad_account_id': {'type': 'string', 'title': 'Ad account ID', 'default': ''},
                'pixel_id': {'type': 'string', 'title': 'Pixel ID', 'default': ''},
                'pixel_enabled': {
                    'type': 'boolean',
                    'title': 'Enable Snap Pixel on the storefront',
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
