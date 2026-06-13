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
        # Storefront routes: taxonomy index pages (/authors/, /publishers/,
        # /series/, /imprints/) listing every term, plus per-value facet pages
        # (/publisher/<slug>/, /series/, /imprint/, /format/, /language/) — each
        # listing the books carrying that attribute value.
        self.register_urls(
            'plugins.installed.book_product.urls', prefix='', namespace='book_product'
        )
        # Dashboard: Book taxonomies (per-term SEO editing) under Products.
        self.register_urls(
            'plugins.installed.book_product.urls_dashboard',
            prefix='dashboard/book-taxonomies/',
            namespace='book_product_dashboard',
        )

    def contribute_dashboard_pages(self) -> list:
        from morpheus import DashboardPage  # noqa: PLC0415

        return [
            DashboardPage(
                label='Book taxonomies',
                slug='book-taxonomies',
                view='plugins.installed.book_product.dashboard_taxonomies.taxonomies_list',
                icon='tags',
                # section='products' renders this as a child of the hardcoded
                # Products nav group (just below Collections, via order) — the
                # plugin owns its placement; no hardcoded link in base.html (ADR 0016).
                section='products',
                order=10,
                nav='main',
                url='/dashboard/book-taxonomies/',
            ),
        ]

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
            category='general',
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
