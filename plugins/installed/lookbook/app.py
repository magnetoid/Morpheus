"""Lookbook / Outfit builder.

A `Lookbook` is an editorial bundle of 2-6 products. The look has
its own PDP at `/looks/<slug>/` and can be added to cart as a
single line (or as the individual products, the shopper's choice).

The merchant can:
  * hand-author a lookbook from the dashboard;
  * turn on AI auto-look ("complete the look" suggestions pulled
    from the existing `personalisation` co-purchase graph).

Lookbooks are the *editorial* surface — the difference between a
shop and a brand.
"""

from __future__ import annotations

from morpheus.app import Plugin, StorefrontBlock


class LookbookPlugin(Plugin):
    name = 'lookbook'
    label = 'Lookbook'
    version = '1.0.0'
    description = (
        'Editorial product bundles. Each look has its own PDP at '
        '/looks/<slug>/ and can be added to cart as a single line or as '
        'individual products. AI auto-look uses the personalisation '
        'co-purchase graph to suggest the rest of the outfit.'
    )
    has_models = True
    requires = ['catalog', 'personalisation']

    def ready(self) -> None:
        # The look page at /looks/<slug>/ this plugin has always advertised —
        # in its own description and in the PDP block's "See the full look"
        # link — but never actually routed, so every such link 404'd.
        self.register_urls(
            'plugins.installed.lookbook.urls',
            prefix='',
            namespace='lookbook',
        )

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='pdp_above_long_description',
                template='lookbook/blocks/in_this_look.html',
                priority=25,
                context_keys=['product'],
            ),
        ]
