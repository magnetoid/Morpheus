"""Checkout-experience plugin manifest.

Drives the storefront checkout end-to-end against the existing
`complete_order` GraphQL mutation. The plugin owns:

* the storefront-side `{% checkout_flow %}` block (renders a
  one-page / multi-step form bound to the existing cart);
* Apple Pay / Google Pay / Link / Klarna express buttons (degrade
  gracefully when the merchant hasn't enabled them);
* the address-autocomplete wiring that uses
  `settings.GOOGLE_PLACES_API_KEY`;
* a settings panel where the merchant picks which express methods
  to advertise and whether to show the one-column or two-column
  layout.

No models — purely a delivery + UX layer that consumes the canonical
orders/tax/shipping/promotions hooks. Disable it and the storefront
falls back to its pre-existing (read-only) template behaviour.
"""
from __future__ import annotations

from morpheus import Plugin, SettingsPanel, StorefrontBlock


class CheckoutExperiencePlugin(Plugin):
    name = 'checkout_experience'
    label = 'Checkout experience'
    version = '1.0.0'
    description = (
        'One-page + express-pay checkout for the storefront. Drives the '
        'existing complete_order mutation, supports Apple Pay / Google Pay '
        '/ Link / Klarna, address autocomplete, and emits a vibe-coded '
        'motion / motion-reduced variant of the layout.'
    )
    has_models = False
    requires = ['orders', 'tax', 'shipping', 'promotions']

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='checkout_extra',
                template='checkout_experience/blocks/flow.html',
                priority=10,
                context_keys=['cart', 'breakdown', 'addresses'],
            ),
            StorefrontBlock(
                slot='global_below_body',
                template='checkout_experience/blocks/loader.html',
                priority=15,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Checkout experience',
            description=(
                'Express-pay methods, layout density, motion preferences. '
                'Address autocomplete uses GOOGLE_PLACES_API_KEY.'
            ),
            category='general',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'layout': {
                    'type': 'string',
                    'enum': ['one-page', 'multi-step', 'two-column'],
                    'default': 'one-page',
                    'title': 'Checkout layout',
                },
                'express_methods': {
                    'type': 'array',
                    'items': {
                        'type': 'string',
                        'enum': ['apple_pay', 'google_pay', 'link', 'klarna'],
                    },
                    'default': ['apple_pay', 'google_pay'],
                    'title': 'Express-pay methods to advertise',
                },
                'show_address_autocomplete': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Address autocomplete (uses GOOGLE_PLACES_API_KEY)',
                },
                'reduced_motion_default': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Default to reduced motion (respects prefers-reduced-motion client-side too)',
                },
            },
        }
