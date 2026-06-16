"""Microsoft / Bing Commerce plugin — Merchant Center feed + UET tag.

Owns the Microsoft Advertising commerce surface that's reliably buildable over a
feed URL + client-side tag: the product catalog feed at
/feeds/microsoft-catalog.xml (Microsoft Merchant Center ingests it) and the UET
(Universal Event Tracking) conversion tag.

NOTE: Ads campaign reporting/management is intentionally NOT built — the
Microsoft Advertising API is SOAP with async (submit→poll→download) reporting,
which can't be implemented reliably/verifiably over plain REST. The feed +
UET cover what gets products onto Bing Shopping and tracks conversions; campaign
ops stay in Microsoft Advertising's own UI until a verified API path exists.
"""

from __future__ import annotations

import logging

from morpheus import DashboardPage, Plugin, SettingsPanel, StorefrontBlock, events

logger = logging.getLogger('morpheus.microsoft_commerce')


class MicrosoftCommercePlugin(Plugin):
    name = 'microsoft_commerce'
    label = 'Microsoft / Bing Commerce'
    version = '0.1.0'
    description = (
        'Microsoft Advertising (Bing) commerce: product catalog feed at '
        '/feeds/microsoft-catalog.xml for Microsoft Merchant Center + the UET '
        'conversion tag. Reuses catalog price, images, inventory, identifiers and '
        'book metadata. (Campaign ops stay in Microsoft Advertising — its API is '
        'SOAP, not built here.)'
    )
    has_models = True
    requires = ['catalog']

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.microsoft_commerce.urls', prefix='', namespace='microsoft_commerce'
        )
        self.register_celery_tasks('plugins.installed.microsoft_commerce.tasks')
        self.register_celery_beat(
            'microsoft_commerce:rebuild_feed',
            {'task': 'microsoft_commerce.rebuild_feed', 'schedule': 60 * 60 * 6},
        )
        # Refresh Ads performance metrics daily (no-op until connected).
        self.register_celery_beat(
            'microsoft_commerce:fetch_ads_report',
            {'task': 'microsoft_commerce.fetch_ads_report', 'schedule': 60 * 60 * 24},
        )
        for evt in (events.PRODUCT_CREATED, events.PRODUCT_UPDATED):
            self.register_hook(evt, self._bust_feed_cache, priority=80)

    def _bust_feed_cache(self, **_):
        try:
            from django.core.cache import cache  # noqa: PLC0415

            from plugins.installed.microsoft_commerce.views import FEED_CACHE_KEY  # noqa: PLC0415

            cache.delete(FEED_CACHE_KEY)
        except Exception as e:  # noqa: BLE001
            logger.debug('microsoft_commerce: cache bust failed: %s', e)

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='global_below_body',
                template='microsoft_commerce/blocks/uet.html',
                priority=70,
            ),
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Microsoft / Bing',
                slug='overview',
                view='plugins.installed.microsoft_commerce.views.dashboard',
                icon='search',
                section='marketing',
                order=68,
                nav='main',
            ),
            DashboardPage(
                label='Microsoft Ads',
                slug='ads',
                view='plugins.installed.microsoft_commerce.views.ads_dashboard',
                icon='target',
                section='marketing',
                order=69,
                nav='main',
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Microsoft / Bing Commerce',
            description=(
                'Microsoft Merchant Center feed + UET tag. Submit the feed URL '
                '(/feeds/microsoft-catalog.xml) in Microsoft Merchant Center; add '
                'your UET tag ID for conversion tracking. The feed works with no '
                'credentials.'
            ),
            schema=self.get_config_schema(),
            category='channels',
        )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.microsoft_commerce.agent_tools import (
            microsoft_campaigns_tool,
            microsoft_feed_coverage_tool,
            microsoft_feed_url_tool,
        )

        return [microsoft_feed_coverage_tool, microsoft_feed_url_tool, microsoft_campaigns_tool]

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'enabled': {'type': 'boolean', 'title': 'Catalog feed enabled', 'default': True},
                'uet_tag_id': {
                    'type': 'string',
                    'title': 'UET tag ID',
                    'description': 'Microsoft Advertising → Conversion tracking → UET tag (numeric).',
                    'default': '',
                },
                'uet_enabled': {
                    'type': 'boolean',
                    'title': 'Enable UET tag on the storefront',
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
                # ── Microsoft Advertising API (campaign management, SOAP) ──
                'oauth_client_id': {'type': 'string', 'title': 'OAuth client ID', 'default': ''},
                'oauth_client_secret': {
                    'type': 'string',
                    'title': 'OAuth client secret',
                    'format': 'password',
                    'default': '',
                },
                'oauth_refresh_token': {
                    'type': 'string',
                    'title': 'OAuth refresh token',
                    'format': 'password',
                    'default': '',
                },
                'developer_token': {
                    'type': 'string',
                    'title': 'Developer token',
                    'format': 'password',
                    'default': '',
                },
                'customer_id': {'type': 'string', 'title': 'Customer ID', 'default': ''},
                'account_id': {'type': 'string', 'title': 'Account ID', 'default': ''},
            },
        }
