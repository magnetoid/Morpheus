from morpheus import Plugin


class CustomersPlugin(Plugin):
    name = "customers"
    label = "Customers"
    version = "1.0.0"
    description = "Customer accounts, addresses, and authentication."
    has_models = True

    def ready(self):
        self.register_graphql_extension('plugins.installed.customers.graphql.queries')
        self.register_graphql_extension('plugins.installed.customers.graphql.mutations')
        self.register_hook('customer.registered', self.on_customer_registered, priority=10)
        from plugins.installed.customers import signals  # noqa

    def on_customer_registered(self, customer, **kwargs):
        from plugins.installed.customers.tasks import send_welcome_email
        send_welcome_email.delay(str(customer.id))
