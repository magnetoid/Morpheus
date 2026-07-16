"""Returns portal — a *retention* surface, not a transaction.

Extends the canonical return flow (``orders.ReturnRequest`` +
``ReturnService`` in plugins/installed/orders/refunds.py) with
**"exchange or store credit"** as first-class resolutions (exchanges
retain ~70 % of the original order value, per Narvar) and a "we
learned something" feedback box that routes to the CRM plugin's lead
pipeline. The return itself — RMA numbers, state machine, refunds,
store-credit ledger — stays owned by orders; this plugin only attaches
``ReturnResolution`` / ``ReturnFeedback`` rows to it.

Returns are the most emotionally loaded moment in the journey.
The opposite of vibe-coding is a generic UPS label email.
"""

from __future__ import annotations

from morpheus import Plugin, SettingsPanel, StorefrontBlock


class ReturnsPortalPlugin(Plugin):
    name = 'returns_portal'
    label = 'Returns portal'
    version = '1.0.0'
    description = (
        'Retention layer over the canonical orders return flow: '
        '"exchange or store credit" as first-class resolutions '
        '(exchanges retain ~70 % of the original order value) plus a '
        "feedback box routed to the CRM plugin's lead pipeline."
    )
    has_models = True
    requires = ['orders', 'loyalty_points', 'customers', 'consent']

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='account_summary_extra',
                template='returns_portal/blocks/cta.html',
                priority=10,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Returns portal',
            description='Return window, exchange preference, store-credit incentive copy.',
            category='payments',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'return_window_days': {
                    'type': 'integer',
                    'default': 30,
                    'title': 'Return window (days)',
                },
                'default_resolution': {
                    'type': 'string',
                    'enum': ['refund', 'exchange', 'store_credit'],
                    'default': 'exchange',
                    'title': 'Default resolution (exchange retains more revenue than refund)',
                },
                'store_credit_bonus_pct': {
                    'type': 'integer',
                    'default': 10,
                    'title': 'Store-credit bonus % (the nudge to pick store credit)',
                },
                'feedback_to_crm': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Route "why" feedback to the CRM lead pipeline',
                },
            },
        }
