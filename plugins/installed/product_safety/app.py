"""product_safety manifest: a product's safety details for the EU GPSR."""

from __future__ import annotations

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock


class ProductSafetyPlugin(Plugin):
    name = 'product_safety'
    label = 'Product safety'
    version = '1.0.0'
    description = (
        "Shows each product's manufacturer, EU responsible person and warnings on its "
        'page and in its structured data (EU General Product Safety Regulation), from '
        "the product's own details or the store's."
    )
    has_models = False
    # The details are metafields on catalog Products (safety.py).
    requires = ['catalog', 'metafields']

    def ready(self) -> None:
        from morpheus.core import events  # noqa: PLC0415
        from plugins.installed.product_safety import seo_graph  # noqa: PLC0415

        self.register_hook(events.PRODUCT_FORM_CARDS, self.on_product_form_cards, priority=85)
        self.register_hook(events.PRODUCT_FORM_SAVED, self.on_product_form_saved, priority=85)
        # After the apps that add the page's Product node.
        self.register_hook(events.SEO_JSONLD_GRAPH, seo_graph.on_seo_jsonld_graph, priority=90)

    def on_product_form_cards(self, value, product=None, **kwargs):
        """The editor's "Product safety" card."""
        from plugins.installed.product_safety.safety import form_fields  # noqa: PLC0415

        value.append(
            {
                'template': 'product_safety/_product_form_card.html',
                'context': {'product_safety': {'fields': form_fields(product)}},
                'order': 85,
            }
        )
        return value

    def on_product_form_saved(self, product=None, post=None, **kwargs):
        from plugins.installed.product_safety.safety import save_from_form  # noqa: PLC0415

        save_from_form(product, post)

    def contribute_storefront_blocks(self) -> list:
        # Under the description, after the AI-text mark (priority 20).
        return [
            StorefrontBlock(
                slot='pdp_below_long_description',
                template='product_safety/blocks/safety_info.html',
                priority=30,
                context_keys=['product'],
            ),
        ]

    def contribute_agent_tools(self) -> list:
        from plugins.installed.product_safety.agent_tools import (  # noqa: PLC0415
            products_safety_info_tool,
            products_set_safety_info_tool,
        )

        return [products_safety_info_tool, products_set_safety_info_tool]

    def get_config_schema(self):
        """The store's own details, shown for goods that name none of their own."""
        from plugins.installed.product_safety.safety import (  # noqa: PLC0415
            MANUFACTURER,
            RESPONSIBLE,
        )

        hints = {
            'manufacturer_name': 'Your company, when you make or brand the goods you sell.',
            'manufacturer_address': 'One line: street, postcode, city, country.',
            'manufacturer_contact': 'An email address or a web address (https://…).',
            'responsible_name': (
                'The person or company in the EU that answers for the goods, needed '
                'when the manufacturer is outside the EU.'
            ),
            'responsible_address': 'One line: street, postcode, city, country.',
            'responsible_contact': 'An email address or a web address (https://…).',
        }
        return {
            'type': 'object',
            'properties': {
                key: {
                    'type': 'string',
                    'default': '',
                    'title': label,
                    'description': hints[key],
                    'maxLength': limit,
                }
                for key, label, limit in MANUFACTURER + RESPONSIBLE
            },
        }

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='Product safety',
            description=(
                "Your store's details as manufacturer and EU responsible person, shown "
                'on the page of every product sold as goods that names none of its own '
                '(EU General Product Safety Regulation).'
            ),
            schema=self.get_config_schema(),
            category='general',
        )
