"""Reddit Ads plugin — Reddit Pixel + Conversions API + Ads API.

Book-relevant channel (r/books, r/Fantasy, …). Full parity minus a catalog feed
(Reddit has no off-Reddit shopping feed): the Reddit Pixel + server-side
Conversions API (content/conversion ids align with orders) and the Ads API
(campaign management + reporting). Connection via Reddit OAuth.
"""

from __future__ import annotations

import logging

from morpheus.core import events
from morpheus.plugin import DashboardPage, Plugin, SettingsPanel, StorefrontBlock

logger = logging.getLogger('morpheus.reddit_ads')


class RedditAdsPlugin(Plugin):
    name = 'reddit_ads'
    label = 'Reddit Ads'
    version = '0.1.0'
    description = (
        'Reddit advertising: the Reddit Pixel (PageVisit / ViewContent / Purchase) '
        '+ server-side Conversions API (deduped by order id) + the Ads API for '
        'campaign management and reporting. Reaches engaged book communities. '
        'No catalog feed — Reddit has no off-Reddit shopping feed.'
    )
    has_models = True
    requires = ['catalog']

    def ready(self) -> None:
        self.register_hook(events.ORDER_PAID, self._on_order_paid, priority=90)
        self.register_hook(events.CHANNELS_OVERVIEW, self._channels_row, priority=60)
        self.register_hook(events.CHANNELS_METRICS, self._channels_metrics, priority=60)

    def _channels_row(self, value, **_):
        row = {
            'name': 'reddit_ads',
            'label': 'Reddit',
            'icon': 'message-circle',
            'connected': False,
            'pixel': 'off',
            'has_feed': False,
            'eligible': None,
            'total': None,
            'coverage_pct': None,
            'dashboard_url': '/dashboard/apps/reddit_ads/ads/',
        }
        try:
            from plugins.installed.reddit_ads.services.oauth import is_connected  # noqa: PLC0415
            from plugins.installed.reddit_ads.services.settings import (  # noqa: PLC0415
                pixel_enabled,
            )

            row['connected'] = is_connected()
            row['pixel'] = 'on' if pixel_enabled() else 'off'
        except Exception as e:  # noqa: BLE001
            logger.debug('reddit_ads: channels row failed: %s', e)
        value.append(row)
        return value

    def _channels_metrics(self, value, **_):
        try:
            from plugins.installed.reddit_ads.services.ads_api import (  # noqa: PLC0415
                campaign_report,
            )

            rep = campaign_report(days=30)
            if rep.get('ok'):
                t = rep.get('totals') or {}
                value.append(
                    {
                        'name': 'reddit_ads',
                        'spend': t.get('spend'),
                        'clicks': t.get('clicks'),
                        'conversions': t.get('conversions'),
                        'revenue': t.get('value') or t.get('revenue'),
                        'roas': t.get('roas'),
                    }
                )
        except Exception as e:  # noqa: BLE001
            logger.debug('reddit_ads: channels metrics failed: %s', e)
        return value

    def _on_order_paid(self, order=None, **_):
        if order is None:
            return
        try:
            from plugins.installed.reddit_ads.services import capi  # noqa: PLC0415

            capi.send_purchase(order)
        except Exception as e:  # noqa: BLE001 — never block the order flow
            logger.debug('reddit_ads: CAPI purchase failed: %s', e)

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='global_below_body',
                template='reddit_ads/blocks/pixel.html',
                priority=70,
            ),
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Reddit Ads',
                slug='ads',
                view='plugins.installed.reddit_ads.views.ads_dashboard',
                icon='message-circle',
                section='marketing',
                order=71,
                nav='main',
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Reddit Ads',
            description=(
                'Reddit Pixel + Conversions API + Ads. Add a Reddit OAuth client + '
                'refresh token, ad account ID and pixel ID. Enable the pixel for '
                'conversion tracking on the storefront.'
            ),
            schema=self.get_config_schema(),
            category='channels',
        )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.reddit_ads.agent_tools import (
            reddit_ads_report_tool,
            reddit_book_communities_tool,
            reddit_campaigns_tool,
        )

        return [reddit_campaigns_tool, reddit_book_communities_tool, reddit_ads_report_tool]

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
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
                    'default': '',
                },
                'account_id': {'type': 'string', 'title': 'Ad account ID', 'default': ''},
                'pixel_id': {'type': 'string', 'title': 'Pixel ID', 'default': ''},
                'pixel_enabled': {
                    'type': 'boolean',
                    'title': 'Enable Reddit Pixel on the storefront',
                    'default': False,
                },
            },
        }
