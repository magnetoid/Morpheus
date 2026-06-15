"""Google Shopping plugin — Google Merchant Center product feed + Google Ads.

Phase 1–2 (shipped): the Merchant Center RSS product feed at
`/feeds/google-merchant.xml`, a feed/coverage dashboard, settings panel, and
agent tools so Linda can audit Shopping eligibility.

Boundary: the `tracking` plugin owns Google Ads CONVERSION pixels + GA4/GTM.
This plugin owns the product FEED, feed config, and (later) Content API sync +
Ads campaign management. It never emits conversion tags.
"""

from __future__ import annotations

import logging

from morpheus import DashboardPage, Plugin, SettingsPanel, StorefrontBlock, events

logger = logging.getLogger('morpheus.google_shopping')


class GoogleShoppingPlugin(Plugin):
    name = 'google_shopping'
    label = 'Google Shopping'
    version = '0.1.0'
    description = (
        'Google Merchant Center product feed + Google Ads layer. Generates the '
        'Shopping RSS feed at /feeds/google-merchant.xml (reusing catalog price, '
        'images, inventory, ISBN/GTIN identifiers and book metadata), with a '
        'coverage dashboard, per-product google.* attribute overrides, and agent '
        'tools to audit Shopping eligibility. Conversion tracking stays in the '
        'tracking plugin.'
    )
    has_models = True
    requires = ['catalog']

    def ready(self) -> None:
        # Public feed endpoint, mounted at site root (/feeds/google-merchant.xml).
        self.register_urls(
            'plugins.installed.google_shopping.urls', prefix='', namespace='google_shopping'
        )
        self.register_celery_tasks('plugins.installed.google_shopping.tasks')
        # Periodic Content API push (no-op until Google is connected).
        self.register_celery_beat(
            'google_shopping:content_push',
            {'task': 'google_shopping.push_content_api', 'schedule': 60 * 60 * 6},
        )
        # Bust the cached feed whenever the catalog changes.
        for evt in (events.PRODUCT_CREATED, events.PRODUCT_UPDATED):
            self.register_hook(evt, self._bust_feed_cache, priority=80)

    def _bust_feed_cache(self, **_):
        try:
            from django.core.cache import cache  # noqa: PLC0415

            from plugins.installed.google_shopping.views import FEED_CACHE_KEY  # noqa: PLC0415

            cache.delete(FEED_CACHE_KEY)
        except Exception as e:  # noqa: BLE001
            logger.debug('google_shopping: cache bust failed: %s', e)

    def contribute_storefront_blocks(self) -> list:
        # Dynamic remarketing tag on every storefront page (renders nothing
        # until a remarketing AW- id is configured + enabled). Conversion
        # pixels stay in the tracking plugin.
        return [
            StorefrontBlock(
                slot='global_below_body',
                template='google_shopping/blocks/remarketing.html',
                priority=70,
            ),
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Google Shopping',
                slug='overview',
                view='plugins.installed.google_shopping.views.dashboard',
                icon='shopping-bag',
                section='marketing',
                order=60,
                nav='main',
            ),
            DashboardPage(
                label='Google Ads',
                slug='ads',
                view='plugins.installed.google_shopping.views.ads_dashboard',
                icon='megaphone',
                section='marketing',
                order=61,
                nav='main',
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Google Shopping feed',
            description=(
                'Google Merchant Center product feed. Submit the feed URL '
                '(/feeds/google-merchant.xml) in Merchant Center. Per-product '
                'overrides live in the google.* metafield namespace.'
            ),
            schema=self.get_config_schema(),
            category='channels',
        )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.google_shopping.agent_tools import (
            google_ads_report_tool,
            google_feed_coverage_tool,
            google_feed_url_tool,
            google_rebuild_feed_tool,
        )

        return [
            google_feed_coverage_tool,
            google_feed_url_tool,
            google_rebuild_feed_tool,
            google_ads_report_tool,
        ]

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'enabled': {'type': 'boolean', 'title': 'Feed enabled', 'default': True},
                'merchant_id': {
                    'type': 'string',
                    'title': 'Merchant Center ID',
                    'description': 'Your Google Merchant Center account ID (for Content API later).',
                    'default': '',
                },
                'country': {'type': 'string', 'title': 'Target country (ISO)', 'default': 'US'},
                'language': {'type': 'string', 'title': 'Content language (ISO)', 'default': 'en'},
                'currency': {
                    'type': 'string',
                    'title': 'Currency override (ISO)',
                    'description': "Leave blank to use each product's own currency.",
                    'default': '',
                },
                'default_brand': {
                    'type': 'string',
                    'title': 'Default brand',
                    'description': 'Used when a product has no brand/publisher of its own.',
                    'default': '',
                },
                'default_google_product_category': {
                    'type': 'string',
                    'title': 'Default Google product category',
                    'description': 'e.g. "Media > Books". Per-product google.google_product_category overrides this.',
                    'default': '',
                },
                'default_condition': {
                    'type': 'string',
                    'title': 'Default condition',
                    'enum': ['new', 'refurbished', 'used'],
                    'default': 'new',
                },
                'free_shipping_over': {
                    'type': 'string',
                    'title': 'Free shipping over (amount)',
                    'default': '',
                },
                'include_out_of_stock': {
                    'type': 'boolean',
                    'title': 'Include out-of-stock products',
                    'default': True,
                },
                'feed_title': {'type': 'string', 'title': 'Feed title', 'default': 'Dot Books'},
                'feed_description': {
                    'type': 'string',
                    'title': 'Feed description',
                    'default': 'Product feed for Google Merchant Center.',
                },
                'remarketing_enabled': {
                    'type': 'boolean',
                    'title': 'Enable Google Ads dynamic remarketing tag',
                    'default': False,
                },
                'remarketing_id': {
                    'type': 'string',
                    'title': 'Google Ads remarketing/conversion ID',
                    'description': 'Format: AW-123456789. Builds Shopping/PMax remarketing audiences. Obeys Consent Mode set by the tracking plugin.',
                    'default': '',
                },
                # ── Google connection (Content API + Ads API). Stored only in
                #    PluginConfig — never settings.py. OAuth2 refresh-token flow.
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
                    'description': 'Authorises Content API (Merchant) + Ads API. Obtain once via the Google OAuth consent screen.',
                    'default': '',
                },
                'ads_developer_token': {
                    'type': 'string',
                    'title': 'Google Ads developer token',
                    'format': 'password',
                    'default': '',
                },
                'ads_customer_id': {
                    'type': 'string',
                    'title': 'Google Ads customer ID',
                    'description': 'The account whose campaigns you manage (digits, dashes ok).',
                    'default': '',
                },
                'ads_login_customer_id': {
                    'type': 'string',
                    'title': 'Google Ads login customer ID (MCC)',
                    'description': 'Optional — your manager (MCC) account ID, if access is via a manager account.',
                    'default': '',
                },
            },
        }
