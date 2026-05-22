from morpheus import Plugin, SettingsPanel


class CatalogPlugin(Plugin):
    name = "catalog"
    label = "Product Catalog"
    version = "1.0.0"
    description = "Products, categories, collections, variants, attributes, and reviews."
    has_models = True

    def ready(self):
        self.register_graphql_extension('plugins.installed.catalog.graphql.queries')
        self.register_graphql_extension('plugins.installed.catalog.graphql.mutations')
        from plugins.installed.catalog import signals  # noqa - register signals

    def get_config_schema(self):
        """Store-wide image defaults — apply to every uploaded product
        image, OG / Twitter card, and cover slot.

        Phase 4 of docs/plans/product-slider.md. Stored under
        PluginConfig['catalog']; read by the image variant generator
        on upload and the storefront responsive image tag at serve
        time.
        """
        return {
            "type": "object",
            "properties": {
                "default_image_format": {
                    "type": "string",
                    "enum": ["webp", "avif", "jpg"],
                    "default": "webp",
                    "title": "Default image format",
                    "description": "Pre-generated variant served from the storefront. WebP works everywhere; AVIF is smaller but slightly newer.",
                },
                "pdp_image_width": {
                    "type": "integer",
                    "default": 800,
                    "title": "PDP image width (px)",
                    "description": "Width of the product detail page hero variant. Portrait books typically pair with 1200 height.",
                },
                "pdp_image_height": {
                    "type": "integer",
                    "default": 1200,
                    "title": "PDP image height (px)",
                },
                "grid_image_width": {
                    "type": "integer",
                    "default": 400,
                    "title": "Grid (PLP) image width (px)",
                },
                "grid_image_height": {
                    "type": "integer",
                    "default": 600,
                    "title": "Grid (PLP) image height (px)",
                },
                "og_image_width": {
                    "type": "integer",
                    "default": 1200,
                    "title": "Open Graph image width (px)",
                    "description": "1200×630 is the recommended Facebook / LinkedIn / Twitter card size.",
                },
                "og_image_height": {
                    "type": "integer",
                    "default": 630,
                    "title": "Open Graph image height (px)",
                },
                "lazy_load_below_fold": {
                    "type": "boolean",
                    "default": True,
                    "title": "Lazy-load images below the fold",
                },
                "enable_avif_variant": {
                    "type": "boolean",
                    "default": False,
                    "title": "Generate AVIF alongside WebP",
                    "description": "AVIF is smaller but takes longer to encode and has spottier browser support. Off by default.",
                },
            },
        }

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='Image defaults',
            description='Store-wide defaults for product image variants — format, sizes, lazy-load, AVIF. Applied to every uploaded image at variant-generation time and at storefront serve time.',
            schema=self.get_config_schema(),
            category='general',
        )
