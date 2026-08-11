"""Immersive PDP — a sticky, on-page add-to-cart for the product page.

Contributes (via `StorefrontBlock(slot=…)`):

  * `pdp_below_form`      — a sticky "buy box" that follows the shopper: product
    title + price, an edition selector (only when a book has 2+ editions), a
    quantity field, and a one-tap add-to-cart posting to the GraphQL
    `addToCart` mutation.
  * `global_below_body`   — the small JS runtime that wires the buy box up.

No models — pure delivery + UX; the `sticky_buybox` setting toggles it.

History: this plugin used to also ship a video hero and "story blocks", but
both were written against data the storefront never provided and targeted theme
slots that aren't rendered, so they never appeared. Story blocks now live in the
real `product_stories` plugin; the dead video hero / story_rail were retired.
"""

from __future__ import annotations

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock


class ImmersivePdpPlugin(Plugin):
    name = 'immersive_pdp'
    label = 'Immersive PDP'
    version = '1.1.0'
    description = (
        'A sticky, theme-styled add-to-cart bar for the product page — '
        'edition picker (only when needed), quantity, one-tap add to bag.'
    )
    has_models = False
    requires = ['catalog', 'orders']

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='pdp_below_form',
                template='immersive_pdp/blocks/sticky_buybox.html',
                priority=10,
                context_keys=['product', 'variants'],
            ),
            StorefrontBlock(
                slot='global_below_body',
                template='immersive_pdp/blocks/buybox_runtime.html',
                priority=10,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Immersive PDP',
            description='The sticky product-page buy box.',
            category='general',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'sticky_buybox': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Sticky buy box (mobile + desktop)',
                },
            },
        }
