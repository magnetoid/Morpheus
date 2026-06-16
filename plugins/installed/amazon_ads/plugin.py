"""Amazon Ads plugin — Amazon Advertising API (campaigns + reporting).

Amazon is structurally different from the shopping-feed channels: there's no
off-Amazon shopping feed (marketplace listing is the Selling Partner API, a
separate integration) and no simple public conversion pixel. So this plugin is
purely the Amazon Advertising API — Sponsored Products campaign management +
async performance reporting — over clean REST (Login with Amazon OAuth).
"""

from __future__ import annotations

import logging

from morpheus import DashboardPage, Plugin, SettingsPanel

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
