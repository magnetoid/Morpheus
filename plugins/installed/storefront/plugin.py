from morpheus import Plugin


class StorefrontPlugin(Plugin):
    name = "storefront"
    label = "Storefront"
    version = "1.0.0"
    description = (
        "Theme-powered customer-facing storefront. "
        "Consumes the GraphQL API internally — never touches the ORM directly."
    )
    has_models = False  # No models — purely views + templates
    requires = ["catalog", "orders", "customers"]

    def ready(self):
        self.register_urls('plugins.installed.storefront.urls', prefix='')
        self.register_hook('order.placed', self.on_order_placed, priority=20)

    def on_order_placed(self, order, **kwargs):
        from plugins.installed.storefront.tasks import send_order_confirmation
        send_order_confirmation.delay(str(order.id))

    def get_config_schema(self):
        return {
            "type": "object",
            "properties": {
                "enable_guest_checkout": {"type": "boolean", "default": True},
                "products_per_page": {"type": "integer", "default": 24},
                "show_out_of_stock": {"type": "boolean", "default": True},
                "enable_live_search": {"type": "boolean", "default": True},
                "enable_ai_chat": {"type": "boolean", "default": True},
                "maintenance_mode": {"type": "boolean", "default": False},
                "maintenance_message": {
                    "type": "string",
                    "default": "We're upgrading the store. Back soon!"
                },
            },
        }
