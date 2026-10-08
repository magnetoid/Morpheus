"""Smart shipping + carbon display.

Extends `shipping` with:

  * carrier integrations (EasyPost / Shippo behind a clean
    interface; the merchant picks which to enable);
  * live rates at checkout (the freight cost was always going to
    be paid — the *surprise* is the bug, per Baymard);
  * a *lowest-carbon* badge on the rate list with a per-rate
    emissions estimate;
  * persistence of the shipper's choice on the order (downstream
    review, supplier rebate, customer comms).

The plugin never reads another plugin's models directly — it
contributes a `shipping_rates_for_cart` GraphQL extension and
reacts to the existing `ORDER_PLACED` hook to persist the
shipper's choice.
"""

from __future__ import annotations

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock


class SmartShippingPlugin(Plugin):
    name = 'smart_shipping'
    label = 'Smart shipping'
    version = '1.0.0'
    description = (
        'Carrier integration (EasyPost / Shippo), live rates at checkout, '
        'and a per-rate carbon-emissions estimate with a "lowest-carbon" '
        "badge. Persists the shopper's rate choice on the order."
    )
    has_models = True
    requires = ['shipping', 'orders']

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='checkout_extra',
                template='smart_shipping/blocks/rate_list.html',
                priority=15,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Smart shipping',
            description='Carrier adapters, emissions source, lowest-carbon badge copy.',
            category='shipping',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'show_lowest_carbon_badge': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Show "lowest carbon" badge on the rate list',
                },
            },
        }
