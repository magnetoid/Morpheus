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
        return value

    def get_config_schema(self):
        return {
            'type': 'object',
            'properties': {
                'enable_guest_checkout': {'type': 'boolean', 'default': True},
                'products_per_page': {'type': 'integer', 'default': 24},
                'show_out_of_stock': {'type': 'boolean', 'default': True},
                'enable_live_search': {'type': 'boolean', 'default': True},
                'enable_ai_chat': {'type': 'boolean', 'default': True},
                'maintenance_mode': {'type': 'boolean', 'default': False},
                'maintenance_message': {
                    'type': 'string',
                    'default': "We're upgrading the store. Back soon!",
                },
            },
        }

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
