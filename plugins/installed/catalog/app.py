from core.images import (
    ASPECT_RATIOS,
    DEFAULT_ASPECT_RATIO,
    DEFAULT_FIT,
    DEFAULT_QUALITY,
    FIT_MODES,
    MAX_QUALITY,
    MIN_QUALITY,
)
from morpheus.app import Plugin, SettingsPanel
from morpheus.core import events


class CatalogPlugin(Plugin):
    name = 'catalog'
    label = 'Product Catalog'
    version = '1.0.0'
    description = 'Products, categories, collections, variants, attributes, and reviews.'
    has_models = True

    def ready(self):
        self.register_graphql_extension('plugins.installed.catalog.graphql.queries')
        # GDPR slice: contribute this plugin's data to the export/erasure.
        from plugins.installed.catalog import gdpr  # noqa: PLC0415

        self.register_hook(events.CUSTOMER_DATA_EXPORT, gdpr.on_customer_export, priority=20)
        self.register_hook(events.CUSTOMER_ANONYMISE, gdpr.on_customer_anonymise, priority=20)
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
        """Store-wide image settings.

        Stored under PluginConfig['catalog'] and read through ONE resolver,
        `core/images.py`, so the dashboard, the themes and the variant
        pipeline cannot drift apart on what shape an image is.

        Two keys were removed in v0.71.0 because nothing read them — the
        "a settings field with no consumer is a lie" landmine, twice over:
        `grid_image_width/height` (the on-demand `/img/<fmt>/<w>/` resizer
        behind `seo_responsive_image` does listing sizes, so these were
        redundant) and `og_image_width/height` (nothing on this platform
        GENERATES an og:image — `SeoMeta.og_image` is a URL the merchant
        supplies, so a size setting described an image that never existed).
        """
        return {
            'type': 'object',
            'properties': {
                'image_aspect_ratio': {
                    'type': 'string',
                    'enum': list(ASPECT_RATIOS),
                    'default': DEFAULT_ASPECT_RATIO,
                    'title': 'Image shape',
                    'description': (
                        'The frame every product image is shown in — product list, '
                        'media library, cover slot and storefront cards. Square suits '
                        'most catalogues; portrait suits books and posters. "Original" '
                        'imposes no frame and lets each image keep its own proportions.'
                    ),
                },
                'image_fit': {
                    'type': 'string',
                    'enum': list(FIT_MODES),
                    'default': DEFAULT_FIT,
                    'title': 'How images fill the frame',
                    'description': (
                        'Fill crops the edges so the frame is never empty. Fit shows the '
                        'whole image and leaves margins — safer for artwork and labels '
                        'where an edge crop loses something.'
                    ),
                },
                'image_quality': {
                    'type': 'integer',
                    'default': DEFAULT_QUALITY,
                    'minimum': MIN_QUALITY,
                    'maximum': MAX_QUALITY,
                    'title': 'Image quality',
                    'description': (
                        'Encoder quality for generated variants, 40–100. Lower means '
                        'smaller files and faster pages; above ~90 the extra bytes buy '
                        'very little a shopper can see.'
                    ),
                },
                'crop_to_aspect_ratio': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Crop uploads to the chosen shape',
                    'description': (
                        'Off by default: the frame already crops visually without '
                        'altering the file. Turn this on to bake the crop into the '
                        'stored variant and save the bytes outside it — it cannot be '
                        'undone for images already processed.'
                    ),
                },
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
            products_update_price_tool,
            products_update_status_tool,
            translate_product_tool,
        )

        return [
            products_search_tool,
            products_count_tool,
            products_get_tool,
            products_update_status_tool,
            products_update_price_tool,
            translate_product_tool,
            list_translations_tool,
        ]

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='Images',
            description='The shape product images are shown in, how they fill their frame, and the format and quality of the variants generated on upload. One setting drives the dashboard, the storefront and the pipeline together.',
            schema=self.get_config_schema(),
            category='general',
        )
