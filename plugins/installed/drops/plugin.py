"""Live drops + waitlist.

Scheduled release times, raffle-by-waitlist for limited stock,
push notification on the PWA, and a stock-equalising queue so
everyone gets the same chance (the Supreme / Glossier model).
Waitlists persist post-sellout ("we'll email you when it's back").

Drops are *built* from anticipation; the *waiting* is the product.
"""

from __future__ import annotations

from morpheus.plugin import Plugin, SettingsPanel, StorefrontBlock


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
            'properties': {
                'queue_mode': {
                    'type': 'string',
                    'enum': ['fifo', 'raffle'],
                    'default': 'fifo',
                    'title': 'Queue mode (FIFO for tech drops, raffle for fashion)',
                },
                'waitlist_after_sellout': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Allow post-sellout waitlist (email me when back)',
                },
                'push_opt_in': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Offer PWA push opt-in during the drop window',
                },
                'countdown_copy': {
                    'type': 'string',
                    'default': 'Dropping soon',
                    'title': 'Pre-drop countdown copy',
                },
            },
        }
