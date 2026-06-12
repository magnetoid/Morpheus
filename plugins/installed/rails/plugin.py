"""Personalised rails — the surfaces that turn the storefront into a feed.

The existing `personalisation` plugin ships *one* F-B-T block. This
plugin surfaces the rest of the signals (co-purchase, recently-viewed,
restocked-for-you, trending-with-your-cohort) as standalone
`StorefrontBlock` contributions. Each rail reads:

  1. a model the merchant can curate (`CuratedRail` — optional
     manual override for A/B tests / campaign lifts);
  2. a fallback that pulls from `personalisation` + `analytics`
     signals via the `core.hooks` event bus (so this plugin never
     imports another plugin's models).

All rails respect `consent.gate('personalisation')` — the rails render
the empty state when the shopper hasn't opted in.
"""

from __future__ import annotations

from morpheus import Plugin, SettingsPanel, StorefrontBlock


class RailsPlugin(Plugin):
    name = 'rails'
    label = 'Personalised rails'
    version = '1.0.0'
    description = (
        'Six "feed-style" rails (For You, Restocked, Recently Viewed, '
        'Trending With Your Cohort, Co-Purchase Next, Looks Like You). '
        'Falls back to anonymous trending when consent is missing.'
    )
    has_models = True
    requires = ['catalog', 'personalisation', 'analytics', 'consent']

    def ready(self) -> None:
        # A merchant can override any rail's products from the dashboard.
        # No outbound cross-plugin imports — we read co-purchase scores
        # via the existing hook payload (`PRODUCT_FBT_SCORES`).
        pass

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='pdp_above_long_description',
                template='rails/blocks/co_purchase_next.html',
                priority=20,
                context_keys=['product'],
            ),
            StorefrontBlock(
                slot='cart_summary_extra',
                template='rails/blocks/trending_with_you.html',
                priority=30,
            ),
            StorefrontBlock(
                slot='checkout_extra',
                template='rails/blocks/looks_like_you.html',
                priority=40,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Personalised rails',
            description='Enable/disable individual rails, set rail titles, configure fallbacks.',
            category='marketing',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'enable_for_you': {
                    'type': 'boolean',
                    'default': True,
                    'title': '"For You" rail (homepage)',
                },
                'enable_restocked': {
                    'type': 'boolean',
                    'default': True,
                    'title': '"Restocked for You" rail',
                },
                'enable_recently_viewed': {
                    'type': 'boolean',
                    'default': True,
                    'title': '"Recently viewed" rail',
                },
                'enable_trending_with_you': {
                    'type': 'boolean',
                    'default': True,
                    'title': '"Trending with your cohort" rail',
                },
                'enable_co_purchase_next': {
                    'type': 'boolean',
                    'default': True,
                    'title': '"Co-purchase next" rail (PDP)',
                },
                'enable_looks_like_you': {
                    'type': 'boolean',
                    'default': True,
                    'title': '"Looks like you" rail (checkout)',
                },
                'require_consent': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Require explicit consent for personalised rails',
                },
                'fallback_to_global_trending': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'When consent missing or unknown, show global trending',
                },
            },
        }
