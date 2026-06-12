"""Subscriptions / Replenish — the LTV multiplier.

Self-serve pause / skip / swap is the thing that defines modern
subscriptions. We model two flavours:

  * **Replenish** — re-runs an order every N days (consumables
    like coffee, vitamins, dog food). The customer picks the
    cadence.
  * **Curated** — fixed cadence with a merchant-rotating box.
    Customers see what ships next, can skip, can swap individual
    items.

Hooks into `inventory` (allocator changes), `loyalty_points`
(points on subscription payments), `affiliates` (subscription-
aware commission), `experiments` (paywall vs skip vs swap).
"""

from __future__ import annotations

from morpheus import Plugin, SettingsPanel, StorefrontBlock


class SubscriptionsPlusPlugin(Plugin):
    name = 'subscriptions_plus'
    label = 'Subscriptions Plus'
    version = '1.0.0'
    description = (
        'Replenish (consumables, every N days) + Curated (rotating box, '
        'fixed cadence). Self-serve pause / skip / swap. Loyalty points '
        'on subscription payments. Subscription-aware affiliate commission.'
    )
    has_models = True
    requires = ['orders', 'inventory', 'loyalty_points', 'affiliates']

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='pdp_below_form',
                template='subscriptions_plus/blocks/subscribe_save.html',
                priority=15,
                context_keys=['product'],
            ),
            StorefrontBlock(
                slot='account_summary_extra',
                template='subscriptions_plus/blocks/dashboard.html',
                priority=5,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Subscriptions Plus',
            description='Default cadences, swap-window, churn-save prompt, points multiplier.',
            category='checkout',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'default_cadence_days': {
                    'type': 'integer',
                    'default': 30,
                    'title': 'Default cadence (days)',
                },
                'allowed_cadences_days': {
                    'type': 'array',
                    'items': {'type': 'integer'},
                    'default': [14, 30, 45, 60, 90],
                    'title': 'Cadences offered to the shopper',
                },
                'swap_window_days': {
                    'type': 'integer',
                    'default': 2,
                    'title': 'Swap window (days before next ship the customer can swap)',
                },
                'loyalty_points_multiplier': {
                    'type': 'number',
                    'default': 2.0,
                    'title': 'Loyalty-points multiplier for subscription payments',
                },
                'churn_save_prompt': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Show a churn-save prompt on pause / cancel',
                },
            },
        }
