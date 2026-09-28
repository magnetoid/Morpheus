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

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock


class PostCheckoutUpsellPlugin(Plugin):
    name = 'post_checkout_upsell'
    label = 'Post-checkout upsell'
    version = '1.0.0'
    description = (
        'Suggests one product on the order confirmation page: the one the '
        'merchant picks, or the newest active product the shopper did not just '
        'buy. (The in-checkout "add" button it used to show had nothing behind it.)'
    )
    has_models = False
    requires = ['orders', 'catalog']

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='order_receipt_extra',
                template='post_checkout_upsell/blocks/post_order.html',
                priority=20,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Post-checkout upsell',
            description='The one product suggested on the order confirmation page.',
            category='payments',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'post_order_upsell_slug': {
                    'type': 'string',
                    'default': '',
                    'title': 'Post-order upsell product slug (one product)',
                },
                'post_order_copy': {
                    'type': 'string',
                    'default': 'P.S. One more thing that pairs well.',
                    'title': 'Post-order upsell copy',
                },
            },
        }
