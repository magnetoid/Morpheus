from morpheus.app import Plugin


class StorefrontPlugin(Plugin):
    name = 'storefront'
    label = 'Storefront'
    version = '1.0.0'
    description = (
        'Theme-powered customer-facing storefront. '
        'Consumes the GraphQL API internally — never touches the ORM directly.'
    )
    has_models = False  # No models — purely views + templates
    requires = ['catalog', 'orders', 'customers']

    def ready(self):
        from morpheus.core import MorpheusEvents

        self.register_urls('plugins.installed.storefront.urls', prefix='')
        # /csrf/ is a machine endpoint: never language-prefixed.
        self.register_urls(
            'plugins.installed.storefront.urls_chrome',
            prefix='',
            namespace='storefront_chrome',
            surface='chrome',
        )
        # NOTE: order-confirmation email is owned by the core transactional spine
        # (core/emails/handlers.on_order_placed). The storefront used to subscribe
        # ORDER_PLACED to send a second, duplicate copy — removed.
        self.register_hook(MorpheusEvents.SEO_ROBOTS_RULES, self.on_robots_rules)
        # The storefront's own index/content pages, listed only while they have
        # something on them — seo cannot know that, the owner can.
        from plugins.installed.storefront.sitemap import (
            claim_cms_page_path,
            contribute_sitemap_urls,
        )

        self.register_hook(MorpheusEvents.SITEMAP_URLS, contribute_sitemap_urls, priority=50)
        # The CMS policy pages this app renders at /shipping/ and /returns/:
        # one url per page (cms 301s /p/<slug>/ here, the sitemap lists these).
        self.register_hook(MorpheusEvents.CMS_PAGE_PATH, claim_cms_page_path, priority=50)
        self.register_hook(MorpheusEvents.HEALTH_CHECKS, self.on_health_checks, priority=40)

    def on_health_checks(self, value, **kwargs):
        """HEALTH_CHECKS: the pages a purchase goes through load for a visitor."""
        from plugins.installed.storefront.health import public_pages_check  # noqa: PLC0415

        value.append(public_pages_check())
        return value

    def on_robots_rules(self, value, **kwargs):
        """The storefront's own private paths, in the storefront's own file.

        These lines lived in the seo app, which owns none of these routes:
        moving checkout, or adding a private surface here, meant editing another
        app to keep robots.txt honest. The set is deliberately unchanged from
        what seo hardcoded — this moves ownership, not policy.

        `/search/` is deliberately NOT among them. Site search is already
        `noindex, follow` through its page kind, and a `Disallow` would stop a
        crawler ever *seeing* that directive — freezing any search URL already
        in an index instead of removing it.
        """
        for path in ('/auth/', '/cart/', '/checkout/'):
            value.disallow(path)
        # A filter panel's list (product_list ?facet_panel=<key>, JSON): crawlers read
        # data-options-url like a path, and each fetch runs the panel's counts.
        value.disallow('/*?*facet_panel=')
        return value

    def contribute_settings_panel(self):
        from plugins.contributions import SettingsPanel

        # Only the shop-closing switch is a Storefront-page control. The rest of this
        # app's keys are the Caching page's (Settings -> Caching), which saves them
        # itself; they are listed in the schema so a reader's key is declared, but a
        # panel built from the whole schema would offer them twice.
        schema = self.get_config_schema()
        keep = ('maintenance_mode', 'maintenance_message')
        return SettingsPanel(
            label='Maintenance',
            description='Close the shop to shoppers while you work on it. Staff still see everything.',
            category='storefront',
            schema={
                'type': 'object',
                'properties': {k: schema['properties'][k] for k in keep},
            },
        )

    def get_config_schema(self):
        # Every key here has a reader: the maintenance middleware, or the cache
        # and speed settings on Settings -> Caching. Defaults are what the readers
        # fall back to, except four where the schema holds the Caching page's
        # displayed value and the reader falls back differently: html_cache_control
        # (the reader sends no header when blank; the page shows the 2026 baseline),
        # and home_cache_ttl, product_cache_ttl and category_cache_ttl (the reader
        # adds no s-maxage override when unset; the page shows 600, 300 and 180).
        return {
            'type': 'object',
            'properties': {
                'maintenance_mode': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Close the shop for maintenance',
                    'description': (
                        'Shoppers see a "back shortly" page. Staff, the dashboard, '
                        'payment webhooks and health checks stay open.'
                    ),
                },
                'maintenance_message': {
                    'type': 'string',
                    'default': "We're upgrading the store. Back soon!",
                    'title': 'Message shoppers see',
                    'description': 'Shown on the "back shortly" page while the shop is closed.',
                },
                'html_cache_control': {
                    'type': 'string',
                    'default': (
                        'public, max-age=0, s-maxage=300, must-revalidate, '
                        'stale-while-revalidate=86400, stale-if-error=86400'
                    ),
                },
                'graphql_edge_cache_ttl': {'type': 'integer', 'default': 0},
                'lazy_load_images': {'type': 'boolean', 'default': True},
                'preload_lcp': {'type': 'boolean', 'default': True},
                'preconnect_origins': {'type': 'string', 'default': ''},
                'dns_prefetch_origins': {'type': 'string', 'default': ''},
                'service_worker_enabled': {'type': 'boolean', 'default': False},
                'offline_page_path': {'type': 'string', 'default': '/offline/'},
                'defer_non_critical_js': {'type': 'boolean', 'default': True},
                'font_display': {'type': 'string', 'default': 'swap'},
                'preload_fonts': {'type': 'string', 'default': ''},
                'home_cache_ttl': {'type': 'integer', 'default': 600},
                'product_cache_ttl': {'type': 'integer', 'default': 300},
                'category_cache_ttl': {'type': 'integer', 'default': 180},
                'search_cache_ttl': {'type': 'integer', 'default': 0},
                'post_deploy_warmup': {'type': 'boolean', 'default': False},
                'warmup_top_n': {'type': 'integer', 'default': 20},
            },
        }

    def contribute_storefront_blocks(self) -> list:
        from plugins.contributions import StorefrontBlock

        # Forms on edge-cached pages post with the visitor's own CSRF token
        # (views/csrf.py); every theme emits global_head.
        return [
            StorefrontBlock(
                slot='global_head',
                template='storefront/blocks/csrf_refresh.html',
                priority=5,
            ),
        ]

    def contribute_hardcoded_pages(self):
        """Functional storefront pages that live in code (views + theme
        templates) — surfaced in the CMS Pages list as locked "managed in code"
        rows so that list stays the registry of every storefront page."""
        return [
            {'title': 'Home', 'url': '/'},
            {'title': 'Cart', 'url': '/cart/'},
            {'title': 'Checkout', 'url': '/checkout/'},
            {'title': 'My account', 'url': '/account/'},
            {'title': 'Contact', 'url': '/contact/'},
        ]
