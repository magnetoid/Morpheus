"""Trust signals plugin manifest.

Surfaces conversion-critical signals on every PDP:
  - Star rating + total review count (clickable → reviews section)
  - Verified-buyer share (e.g. "84% verified purchases")
  - Recent-purchases ticker ("12 ordered in the last 24h")

Each signal is opt-in via PluginConfig; merchants who don't want to
display low review counts (e.g. a brand-new shop) can hide individual
elements until they have enough data.

Why this exists as a separate plugin (not part of reviews/):
  - A/B-testable in isolation (turn off the whole strip, measure delta)
  - The recent-purchases signal isn't review-derived, it's order-derived
  - Different shops want different trust signals; keeping the surface
    in one place makes it easy to add new ones later (e.g. SSL badge,
    money-back guarantee, awards)
"""

from __future__ import annotations

from morpheus.plugin import Plugin, SettingsPanel, StorefrontBlock


class TrustSignalsPlugin(Plugin):
    name = 'trust_signals'
    label = 'Trust signals'
    version = '1.0.0'
    description = (
        'PDP trust strip — star rating, verified-buyer percentage, '
        'recent-purchases ticker. Cheapest CRO uplift; no DB changes.'
    )

    def contribute_storefront_blocks(self) -> list[StorefrontBlock]:
        return [
            StorefrontBlock(
                slot='pdp_below_price',
                template='trust_signals/blocks/trust_strip.html',
                priority=30,  # ahead of low_stock_badge (priority=20)
                context_keys=['product'],
                # `product` already in PDP context; block fetches the
                # rest of its data via the `trust_data` templatetag.
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Trust signals',
            category='general',
            description='Per-store control over which trust signals to render on PDPs.',
            schema={
                'show_rating': {
                    'type': 'boolean',
                    'title': 'Show star rating + review count',
                    'default': True,
                },
                'min_reviews_for_rating': {
                    'type': 'integer',
                    'title': 'Minimum reviews before showing rating',
                    'minimum': 0,
                    'maximum': 100,
                    'default': 3,
                    'description': (
                        'Hide the rating until the product has at least this '
                        'many reviews. Low-N ratings hurt trust more than '
                        'they help.'
                    ),
                },
                'show_verified_share': {
                    'type': 'boolean',
                    'title': 'Show verified-buyer percentage',
                    'default': True,
                },
                'show_recent_purchases': {
                    'type': 'boolean',
                    'title': 'Show recent-purchases ticker',
                    'default': True,
                },
                'recent_purchases_window_hours': {
                    'type': 'integer',
                    'title': 'Recent-purchases lookback (hours)',
                    'minimum': 1,
                    'maximum': 168,
                    'default': 72,
                    'description': '"X ordered in the last N hours". 72h is the sweet spot.',
                },
                'min_recent_purchases': {
                    'type': 'integer',
                    'title': 'Minimum recent purchases to show the ticker',
                    'minimum': 1,
                    'maximum': 100,
                    'default': 3,
                    'description': (
                        'Hide the ticker if fewer than N people bought it. '
                        '"1 ordered today" reads as desperate, not popular.'
                    ),
                },
            },
        )
