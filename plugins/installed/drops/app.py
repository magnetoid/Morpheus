"""Live drops + waitlist.

Scheduled release times, raffle-by-waitlist for limited stock,
push notification on the PWA, and a stock-equalising queue so
everyone gets the same chance (the Supreme / Glossier model).
Waitlists persist post-sellout ("we'll email you when it's back").

Drops are *built* from anticipation; the *waiting* is the product.
"""

from __future__ import annotations

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock


class DropsPlugin(Plugin):
    name = 'drops'
    label = 'Drops'
    version = '1.0.0'
    description = (
        'Scheduled drops, raffle-by-waitlist for limited stock, PWA push '
        'notifications, stock-equalising queue, and post-sellout waitlists.'
    )
    has_models = True
    requires = ['catalog', 'inventory', 'pwa', 'consent']

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='pdp_below_form',
                template='drops/blocks/drop_indicator.html',
                priority=20,
                context_keys=['product'],
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Drops',
            description='Drop schedule, queue mode (FIFO vs raffle), push opt-in copy.',
            category='marketing',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {},
        }
