from morpheus.app import DashboardCard, DashboardPage, Plugin
from morpheus.core import events


class MarketingPlugin(Plugin):
    name = 'marketing'
    label = 'Marketing'
    version = '1.1.0'
    description = 'Coupons, discount engine, email campaigns, abandoned-cart recovery.'
    has_models = True
    requires = ['catalog']

    def ready(self):
        self.register_hook(events.DASHBOARD_SEARCH, self.on_dashboard_search)
        self.register_graphql_extension('plugins.installed.marketing.graphql.queries')
        self.register_graphql_extension('plugins.installed.marketing.graphql.mutations')
        # Cart-recovery email is owned solely by the cart_abandonment plugin's
        # consent-checked drip — marketing no longer subscribes to cart.abandoned.

    def on_dashboard_search(self, value, query='', words=None, **kwargs):
        """Coupons (by code or name) in the dashboard's search box."""
        from plugins import dashboard_search as ds
        from plugins.installed.marketing.models import Coupon

        return ds.add(
            value,
            Coupon,
            query,
            words,
            fields=('code', 'name'),
            section='Coupons',
            kind='coupon',
            icon='ticket',
            capability='marketing.write',
            label=lambda c: c.code,
            hint=lambda c: ' · '.join(x for x in (c.name, '' if c.is_active else 'off') if x),
            url=lambda c: f'/dashboard/marketing/coupons/{c.pk}/',
        )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.marketing.agent_tools import (
            create_coupon_tool,
            list_coupons_tool,
            update_coupon_tool,
        )

        return [list_coupons_tool, create_coupon_tool, update_coupon_tool]

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
