from morpheus.app import DashboardCard, DashboardPage, Plugin


class MarketingPlugin(Plugin):
    name = 'marketing'
    label = 'Marketing'
    version = '1.1.0'
    description = 'Coupons, discount engine, email campaigns, abandoned-cart recovery.'
    has_models = True

    def ready(self):
        self.register_graphql_extension('plugins.installed.marketing.graphql.queries')
        self.register_graphql_extension('plugins.installed.marketing.graphql.mutations')
        # Cart-recovery email is owned solely by the cart_abandonment plugin's
        # consent-checked drip — marketing no longer subscribes to cart.abandoned.

    def contribute_dashboard_cards(self) -> list:
        # A card on the Marketing landing, beside other apps' cards.
        return [
            DashboardCard(
                section='marketing',
                title='Coupons',
                data='plugins.installed.marketing.cards.coupons_card',
                url='/dashboard/marketing/coupons/',
                cta='Manage coupons',
                icon='ticket',
                order=10,
                capability='marketing.read',
            )
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Coupons',
                slug='coupons',
                view='plugins.installed.marketing.dashboard.coupons_list',
                icon='ticket',
                section='marketing',
                order=10,
                url='/dashboard/marketing/coupons/',
            ),
            DashboardPage(
                label='Campaigns',
                slug='campaigns',
                view='plugins.installed.marketing.dashboard.campaigns_list',
                icon='megaphone',
                section='marketing',
                order=20,
                nav='hidden',
            ),
        ]
