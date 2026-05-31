"""Personalisation plugin manifest."""

from __future__ import annotations

from morpheus import Plugin, StorefrontBlock


class PersonalisationPlugin(Plugin):
    name = 'personalisation'
    label = 'Personalisation'
    version = '1.0.0'
    description = (
        'Co-purchase recommendations on PDPs. Reads consent-gated '
        'CoPurchaseScore precomputed nightly from paid orders.'
    )

    def contribute_storefront_blocks(self) -> list[StorefrontBlock]:
        return [
            StorefrontBlock(
                slot='pdp_above_long_description',
                template='personalisation/blocks/frequently_bought_together.html',
                priority=40,
                context_keys=['product'],
            ),
        ]
