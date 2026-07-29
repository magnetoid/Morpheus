from morpheus.plugin import Plugin


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
        self.register_urls('plugins.installed.storefront.urls', prefix='')
        # NOTE: order-confirmation email is owned by the core transactional spine
        # (core/emails/handlers.on_order_placed). The storefront used to subscribe
        # ORDER_PLACED to send a second, duplicate copy — removed.

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
