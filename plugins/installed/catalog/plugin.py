from morpheus import Plugin, SettingsPanel, events


class CatalogPlugin(Plugin):
    name = 'catalog'
    label = 'Product Catalog'
    version = '1.0.0'
    description = 'Products, categories, collections, variants, attributes, and reviews.'
    has_models = True

    def ready(self):
        self.register_graphql_extension('plugins.installed.catalog.graphql.queries')
        self.register_graphql_extension('plugins.installed.catalog.graphql.mutations')
        # Dashboard-home tiles: active-products KPI, top-products panel,
        # first-product setup step.
        self.register_hook(events.DASHBOARD_KPIS, self.on_dashboard_kpis, priority=20)
        self.register_hook(events.DASHBOARD_HOME_PANELS, self.on_dashboard_panels, priority=20)
        self.register_hook(events.DASHBOARD_SETUP_STEPS, self.on_setup_steps, priority=10)
        # Morpheus Brain: contribute the catalog content-gap counts.
        self.register_hook(events.BRAIN_SIGNALS, self.on_brain_signals, priority=50)
        from plugins.installed.catalog import signals  # noqa - register signals

    def on_brain_signals(self, value, **kwargs):
        """Merge the catalog content-gap slice into the Brain snapshot —
        active-product count and how many lack a description (→ content.catalog)."""
        from contextlib import suppress  # noqa: PLC0415

        with suppress(Exception):
            from django.db.models import Q  # noqa: PLC0415

            from plugins.installed.catalog.models import Product  # noqa: PLC0415

            active = Product.objects.filter(status='active')
            value.setdefault('content', {})['catalog'] = {
                'total': active.count(),
                'missing_desc': active.filter(
                    Q(description__isnull=True) | Q(description='')
                ).count(),
            }
        return value

    def on_dashboard_kpis(self, value, date_range=None, **kwargs):
        """Append the active-products KPI tile."""
        from plugins.installed.catalog.models import Product  # noqa: PLC0415

        value.append(
            {
                'label': 'Active products',
                'value': f'{Product.objects.filter(status="active").count():,}',
                'delta': '',
                'trend': 'flat',
                'icon': 'package',
                'series': None,
                'hint': 'Number of products currently visible on the storefront.',
            }
        )
        return value

    def on_dashboard_panels(self, value, date_range=None, **kwargs):
        """Fold the top-products panel into the home context."""
        from plugins.installed.catalog.models import Product  # noqa: PLC0415

        value['top_products'] = list(
            Product.objects.filter(status='active').order_by('-created_at')[:5]
        )
        return value

    def on_setup_steps(self, value, **kwargs):
        """Append the 'add your first product' first-run step."""
        from plugins.installed.catalog.models import Product  # noqa: PLC0415

        value.append(
            {
                'key': 'product',
                'label': 'Add your first product',
                'hint': 'Create a product to put on the shelf.',
                'url': '/dashboard/products/new/',
                'done': Product.objects.exists(),
            }
        )
        return value

    def get_config_schema(self):
        """Store-wide image defaults — apply to every uploaded product
        image, OG / Twitter card, and cover slot.

        Phase 4 of docs/plans/product-slider.md. Stored under
        PluginConfig['catalog']; read by the image variant generator
        on upload and the storefront responsive image tag at serve
        time.
        """
        return {
            'type': 'object',
            'properties': {
                'default_image_format': {
                    'type': 'string',
                    'enum': ['webp', 'avif', 'jpg'],
                    'default': 'webp',
                    'title': 'Default image format',
                    'description': 'Pre-generated variant served from the storefront. WebP works everywhere; AVIF is smaller but slightly newer.',
                },
                'pdp_image_width': {
                    'type': 'integer',
                    'default': 800,
                    'title': 'PDP image width (px)',
                    'description': 'Width of the product detail page hero variant. Portrait books typically pair with 1200 height.',
                },
                'pdp_image_height': {
                    'type': 'integer',
                    'default': 1200,
                    'title': 'PDP image height (px)',
                },
                'grid_image_width': {
                    'type': 'integer',
                    'default': 400,
                    'title': 'Grid (PLP) image width (px)',
                },
                'grid_image_height': {
                    'type': 'integer',
                    'default': 600,
                    'title': 'Grid (PLP) image height (px)',
                },
                'og_image_width': {
                    'type': 'integer',
                    'default': 1200,
                    'title': 'Open Graph image width (px)',
                    'description': '1200×630 is the recommended Facebook / LinkedIn / Twitter card size.',
                },
                'og_image_height': {
                    'type': 'integer',
                    'default': 630,
                    'title': 'Open Graph image height (px)',
                },
                'lazy_load_below_fold': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Lazy-load images below the fold',
                },
                'enable_avif_variant': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Generate AVIF alongside WebP',
                    'description': 'AVIF is smaller but takes longer to encode and has spottier browser support. Off by default.',
                },
            },
        }

    def contribute_agent_tools(self) -> list:
        from plugins.installed.catalog.agent_tools import (  # noqa: PLC0415
            list_translations_tool,
            products_count_tool,
            products_get_tool,
            products_search_tool,
            translate_product_tool,
        )

        return [
            products_search_tool,
            products_count_tool,
            products_get_tool,
            translate_product_tool,
            list_translations_tool,
        ]

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='Image defaults',
            description='Store-wide defaults for product image variants — format, sizes, lazy-load, AVIF. Applied to every uploaded image at variant-generation time and at storefront serve time.',
            schema=self.get_config_schema(),
            category='general',
        )
