"""Book Product plugin manifest."""

# ruff: noqa: PLC0415
from __future__ import annotations

from morpheus import Plugin, SettingsPanel, StorefrontBlock


class BookProductPlugin(Plugin):
    name = 'book_product'
    label = 'Book Product'
    version = '0.1.0'
    description = (
        'Book product-type extension: author, print/paper type, page count, '
        'a cover-PDF 3D preview, and a dashboard book widget. Book attributes '
        'live on a real model instead of meta tags.'
    )
    has_models = True
    requires = ['catalog']

    def ready(self) -> None:
        # Full GraphQL control: bookProduct query + setBookProduct mutation.
        self.register_graphql_extension('plugins.installed.book_product.graphql.queries')
        self.register_graphql_extension('plugins.installed.book_product.graphql.mutations')

    def contribute_storefront_blocks(self) -> list[StorefrontBlock]:
        # Book details + 3D cover preview on the PDP. Self-gates on a
        # BookProduct existing (the template renders nothing otherwise), so it
        # disappears with the plugin.
        return [
            StorefrontBlock(
                slot='pdp_below_form',
                template='storefront/blocks/_book_pdp.html',
                priority=40,
                context_keys=['product'],
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        # Lives under Settings → Product Types (the category is declared in
        # admin_dashboard.settings_categories). Disabling the plugin removes it.
        return SettingsPanel(
            label='Books',
            description='Defaults for the Book product type.',
            schema=self.get_config_schema(),
            category='product_types',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'default_print_type': {
                    'type': 'string',
                    'default': 'paperback',
                    'title': 'Default print type',
                    'description': 'Pre-selected when a book has no print type set.',
                },
                'default_paper_type': {
                    'type': 'string',
                    'default': '',
                    'title': 'Default paper type',
                },
                'enable_3d_preview': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Enable the 3D cover preview on product pages',
                },
            },
        }
