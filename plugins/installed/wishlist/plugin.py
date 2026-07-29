"""Wishlist plugin manifest."""

from __future__ import annotations

from morpheus.core import events
from morpheus.plugin import Plugin, StorefrontBlock


class WishlistPlugin(Plugin):
    name = 'wishlist'
    label = 'Wishlist'
    version = '1.0.0'
    description = (
        'Saved items per customer (or guest session). Storefront page, '
        'shareable links, agent tools for the Concierge to add items.'
    )
    has_models = True
    requires = ['catalog', 'customers']

    def ready(self) -> None:
        # GDPR slice: contribute this plugin's data to the export/erasure.
        from plugins.installed.wishlist import gdpr  # noqa: PLC0415

        self.register_hook(events.CUSTOMER_DATA_EXPORT, gdpr.on_customer_export, priority=40)
        self.register_hook(events.CUSTOMER_ANONYMISE, gdpr.on_customer_anonymise, priority=40)
        self.register_urls(
            'plugins.installed.wishlist.urls',
            prefix='wishlist/',
            namespace='wishlist',
        )

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='pdp_below_form',
                template='wishlist/blocks/save_button.html',
                priority=70,
            ),
        ]

    def contribute_agent_tools(self) -> list:
        from plugins.installed.wishlist.agent_tools import (
            add_to_wishlist_tool,
            wishlist_summary_tool,
        )

        return [add_to_wishlist_tool, wishlist_summary_tool]
