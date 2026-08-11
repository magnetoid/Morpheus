"""Referrals — the merchant-funded CAC.

A customer-unique URL; double-sided reward (referrer + referee) paid
in **store credit** (via the `loyalty_points` ledger) so the merchant
has zero cash exposure. A contest layer on top ("top referrers this
month get a free [product]").

This is distinct from `affiliates` (B2B/influencer) and from
`loyalty_points` (the store-credit ledger it consumes).
"""

from __future__ import annotations

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock


class ReferralsPlugin(Plugin):
    name = 'referrals'
    label = 'Referrals'
    version = '1.0.0'
    description = (
        'Give-5 / Get-5 customer referral program. Double-sided reward '
        'paid in store credit (via loyalty_points ledger). Optional '
        'contest layer ("top referrers get a free product").'
    )
    has_models = True
    requires = ['customers', 'orders', 'loyalty_points', 'consent']

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='account_summary_extra',
                template='referrals/blocks/dashboard.html',
                priority=20,
            ),
            StorefrontBlock(
                slot='checkout_extra',
                template='referrals/blocks/credit_credit.html',
                priority=20,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Referrals',
            description='Reward amounts, double-sided, contest layer, anti-fraud.',
            category='marketing',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'enabled': {'type': 'boolean', 'default': True, 'title': 'Master switch'},
                'referrer_reward_cents': {
                    'type': 'integer',
                    'default': 500,
                    'title': 'Referrer reward (cents in store credit)',
                },
                'referee_reward_cents': {
                    'type': 'integer',
                    'default': 500,
                    'title': 'Referee reward (cents in store credit)',
                },
                'min_order_subtotal_cents': {
                    'type': 'integer',
                    'default': 2000,
                    'title': 'Minimum order subtotal to trigger reward',
                },
                'enable_contest': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Contest layer (top referrers get a free product)',
                },
                'contest_period': {
                    'type': 'string',
                    'enum': ['monthly', 'quarterly'],
                    'default': 'monthly',
                    'title': 'Contest period',
                },
                'antifraud_max_referrals_per_ip_per_day': {
                    'type': 'integer',
                    'default': 3,
                    'title': 'Max referrals per IP per day (anti-fraud)',
                },
            },
        }
