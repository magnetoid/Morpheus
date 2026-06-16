"""Amazon Ads plugin — Amazon Advertising API (campaigns + reporting).

Amazon is structurally different from the shopping-feed channels: there's no
off-Amazon shopping feed (marketplace listing is the Selling Partner API, a
separate integration) and no simple public conversion pixel. So this plugin is
purely the Amazon Advertising API — Sponsored Products campaign management +
async performance reporting — over clean REST (Login with Amazon OAuth).
"""

from __future__ import annotations

import logging

from morpheus import DashboardPage, Plugin, SettingsPanel, events

logger = logging.getLogger('morpheus.amazon_ads')


class AmazonAdsPlugin(Plugin):
    name = 'amazon_ads'
    label = 'Amazon Ads'
    version = '0.1.0'
    description = (
        'Amazon Advertising: Sponsored Products campaign management (list / pause '
        '/ enable / create) + async performance reporting (cost, clicks, '
        'purchases, sales), over the Amazon Ads API with Login-with-Amazon OAuth. '
        'No catalog feed / pixel — Amazon has no off-Amazon shopping feed and '
        'marketplace listing is the separate Selling Partner API.'
    )
    has_models = True
    requires = ['catalog']

    def ready(self) -> None:
        self.register_celery_tasks('plugins.installed.amazon_ads.tasks')
        self.register_celery_beat(
            'amazon_ads:fetch_report',
            {'task': 'amazon_ads.fetch_report', 'schedule': 60 * 60 * 24},
        )
        self.register_hook(events.CHANNELS_OVERVIEW, self._channels_row, priority=70)
        self.register_hook(events.CHANNELS_METRICS, self._channels_metrics, priority=70)

    def _channels_row(self, value, **_):
        row = {
            'name': 'amazon_ads',
            'label': 'Amazon',
            'icon': 'shopping-cart',
            'connected': False,
            'pixel': None,
            'has_feed': False,
            'eligible': None,
            'total': None,
            'coverage_pct': None,
            'dashboard_url': '/dashboard/apps/amazon_ads/ads/',
        }
        try:
            from plugins.installed.amazon_ads.services.oauth import is_connected  # noqa: PLC0415

            row['connected'] = is_connected()
        except Exception as e:  # noqa: BLE001
            logger.debug('amazon_ads: channels row failed: %s', e)
        value.append(row)
        return value

    def _channels_metrics(self, value, **_):
        try:
            from plugins.installed.amazon_ads.services.reporting import (  # noqa: PLC0415
                cached_metrics,
            )

            cached = cached_metrics()
            if cached and cached.get('ok'):
                m = (cached.get('metrics') or {}).values()
                spend = sum(c.get('cost') or 0 for c in m)
                revenue = sum(c.get('sales') or 0 for c in m)
                value.append(
                    {
                        'name': 'amazon_ads',
                        'spend': round(spend, 2),
                        'clicks': sum(c.get('clicks') or 0 for c in m),
                        'conversions': round(sum(c.get('purchases') or 0 for c in m), 1),
                        'revenue': round(revenue, 2),
                        'roas': round(revenue / spend, 2) if spend else None,
                    }
                )
        except Exception as e:  # noqa: BLE001
            logger.debug('amazon_ads: channels metrics failed: %s', e)
        return value

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Amazon Ads',
                slug='ads',
                view='plugins.installed.amazon_ads.views.ads_dashboard',
                icon='shopping-cart',
                section='marketing',
                order=70,
                nav='main',
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Amazon Ads',
            description=(
                'Amazon Advertising API. Add a Login-with-Amazon OAuth client + '
                'refresh token, your advertising profile ID and region. Campaign '
                'management is live; metrics come from the async Reporting API.'
            ),
            schema=self.get_config_schema(),
            category='channels',
        )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.amazon_ads.agent_tools import (
            amazon_ads_report_tool,
            amazon_campaigns_tool,
        )

        return [amazon_campaigns_tool, amazon_ads_report_tool]

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'client_id': {'type': 'string', 'title': 'LWA client ID', 'default': ''},
                'client_secret': {
                    'type': 'string',
                    'title': 'LWA client secret',
                    'format': 'password',
                    'default': '',
                },
                'refresh_token': {
                    'type': 'string',
                    'title': 'OAuth refresh token',
                    'format': 'password',
                    'default': '',
                },
                'profile_id': {
                    'type': 'string',
                    'title': 'Advertising profile ID',
                    'description': 'From GET /v2/profiles — the advertiser/marketplace profile.',
                    'default': '',
                },
                'region': {
                    'type': 'string',
                    'title': 'Region',
                    'enum': ['na', 'eu', 'fe'],
                    'default': 'na',
                },
            },
        }
