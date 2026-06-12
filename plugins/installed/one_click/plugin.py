"""One-click returning shopper (Shop Pay analogue).

After a customer's first successful checkout, the plugin emails a
"saved your info" link. The next visit shows a one-tap button on
the cart that posts a single device-keyed token to the
`mutateOneClickCheckout` GraphQL mutation; the order is created
without a fresh form.

Encryption: tokens are AES-GCM, key lives in `settings.ONE_CLICK_KEY`
(env). Tokens rotate every 30 days and on every checkout, with the
last 3 retained per customer to support multi-device.
"""

from __future__ import annotations

from morpheus import Plugin, SettingsPanel, StorefrontBlock


class OneClickPlugin(Plugin):
    name = 'one_click'
    label = 'One-click returning shopper'
    version = '1.0.0'
    description = (
        'After a first successful checkout, customers can opt in to a '
        'one-tap returning-shopper experience. AES-GCM device tokens, '
        'rotated per checkout, last 3 retained for multi-device.'
    )
    has_models = True
    requires = ['customers', 'orders', 'payments', 'consent']

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='cart_summary_extra',
                template='one_click/blocks/button.html',
                priority=50,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='One-click returning shopper',
            description='Master switch, token rotation period, offer-after-N-orders threshold.',
            category='checkout',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'enabled': {'type': 'boolean', 'default': True, 'title': 'Master switch'},
                'min_completed_orders': {
                    'type': 'integer',
                    'default': 1,
                    'minimum': 1,
                    'title': 'Only show after N completed orders',
                },
                'token_rotation_days': {
                    'type': 'integer',
                    'default': 30,
                    'title': 'Token rotation period (days)',
                },
                'retained_tokens_per_customer': {
                    'type': 'integer',
                    'default': 3,
                    'title': 'Active device tokens per customer',
                },
            },
        }
