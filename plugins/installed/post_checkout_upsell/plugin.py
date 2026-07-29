"""Post-checkout one-click upsell.

A *single* in-checkout upsell (the "before you pay" shoe-lace
add-on, the travel-size add-on) and a *single* post-checkout
upsell (the "complete the protection plan" or "upgrade to
express") on the receipt page.

A *single* upsell doesn't fragment the experience — which is the
vibe-coded take on it.

The merchant authors the upsell target from a settings panel;
the storefront renders it inline in checkout and on the receipt.
The post-checkout upsell ships with a *single* one-tap "add to my
order" button that creates a follow-up order in the same session.
"""

from __future__ import annotations

from morpheus.plugin import Plugin, SettingsPanel, StorefrontBlock


class PostCheckoutUpsellPlugin(Plugin):
    name = 'post_checkout_upsell'
    label = 'Post-checkout upsell'
    version = '1.0.0'
    description = (
        'A single in-checkout upsell and a single post-checkout upsell, '
        'hand-picked by the merchant from a settings panel. The post-'
        'checkout upsell creates a one-tap follow-up order in the same '
        'session. No fragmentation — one upsell at a time.'
    )
    has_models = False
    requires = ['orders', 'catalog']

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='checkout_extra',
                template='post_checkout_upsell/blocks/in_checkout.html',
                priority=25,
            ),
            StorefrontBlock(
                slot='order_receipt_extra',
                template='post_checkout_upsell/blocks/post_order.html',
                priority=20,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Post-checkout upsell',
            description='In-checkout + post-checkout upsell target (a single product slug each).',
            category='payments',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'in_checkout_upsell_slug': {
                    'type': 'string',
                    'default': '',
                    'title': 'In-checkout upsell product slug (one product)',
                },
                'post_order_upsell_slug': {
                    'type': 'string',
                    'default': '',
                    'title': 'Post-order upsell product slug (one product)',
                },
                'in_checkout_copy': {
                    'type': 'string',
                    'default': 'Add a little something extra?',
                    'title': 'In-checkout upsell copy',
                },
                'post_order_copy': {
                    'type': 'string',
                    'default': 'P.S. One more thing that pairs well — one-tap add.',
                    'title': 'Post-order upsell copy',
                },
            },
        }
