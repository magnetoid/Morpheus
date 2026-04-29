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
        # Allauth's signup signal is bridged onto the hook bus in signals.py —
        # importing it here registers the `@receiver(user_signed_up)`.
        from plugins.installed.customers import signals  # noqa
