from morpheus import DashboardPage, Plugin


class MarketingPlugin(Plugin):
    name = 'marketing'
    label = 'Marketing'
    version = '1.1.0'
    description = 'Coupons, discount engine, email campaigns, abandoned-cart recovery.'
    has_models = True

    def ready(self):
        self.register_graphql_extension('plugins.installed.marketing.graphql.queries')
        self.register_graphql_extension('plugins.installed.marketing.graphql.mutations')
        self.register_hook('cart.abandoned', self.on_cart_abandoned, priority=30)

    def on_cart_abandoned(self, cart, **kwargs):
        from plugins.installed.marketing.tasks import trigger_cart_recovery_sequence

        trigger_cart_recovery_sequence.delay(str(cart.id))

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Coupons',
                slug='coupons',
                view='plugins.installed.marketing.dashboard.coupons_list',
                icon='ticket',
                section='marketing',
                order=10,
            ),
            DashboardPage(
                label='Campaigns',
                slug='campaigns',
                view='plugins.installed.marketing.dashboard.campaigns_list',
                icon='megaphone',
                section='marketing',
                order=20,
            ),
        ]
