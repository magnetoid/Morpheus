"""Post-purchase journey plugin manifest."""

from __future__ import annotations

from morpheus.app import DashboardCard, DashboardPage, Plugin, SettingsPanel, StorefrontBlock
from morpheus.core import events


class PostPurchasePlugin(Plugin):
    name = 'post_purchase'
    label = 'Post-purchase journey'
    version = '1.0.0'
    description = (
        'Schedules a tracking, delivered, review-request and NPS step per order, '
        'runs the NPS survey and report, and suggests one product on the order '
        'confirmation page.'
    )
    requires = ['orders', 'catalog']

    def ready(self) -> None:
        from plugins.installed.post_purchase.handlers import (  # noqa: PLC0415
            on_order_fulfilled,
            on_order_placed,
        )

        # Owned, so the bus stops calling them while the app is off.
        self.register_hook(events.ORDER_PLACED, on_order_placed, priority=60)
        self.register_hook(events.ORDER_FULFILLED, on_order_fulfilled, priority=60)
        self.register_urls(
            'plugins.installed.post_purchase.urls',
            prefix='post-purchase/',
            namespace='post_purchase',
        )

    def contribute_dashboard_cards(self) -> list:
        # A card on the Analytics landing, beside other apps' cards.
        return [
            DashboardCard(
                section='analytics',
                title='NPS',
                data='plugins.installed.post_purchase.cards.nps_card',
                url='/dashboard/apps/post_purchase/nps/',
                cta='Open report',
                icon='smile',
                order=60,
                capability='analytics.read',
            )
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='NPS',
                slug='nps',
                view='plugins.installed.post_purchase.views_dashboard.nps_dashboard',
                icon='smile',
                section='analytics',
                order=60,
                nav='hidden',
            ),
        ]

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='order_receipt_extra',
                template='post_purchase/blocks/post_order.html',
                priority=20,
            ),
        ]

    def get_config_schema(self) -> dict:
        # The journey's timing runs on the defaults in handlers.py: nothing sends
        # its emails yet, so the page offers no controls for them.
        return {
            'type': 'object',
            'properties': {
                'post_order_upsell_slug': {
                    'type': 'string',
                    'default': '',
                    'title': 'Post-order upsell product slug (one product)',
                },
                'post_order_copy': {
                    'type': 'string',
                    'default': 'P.S. One more thing that pairs well.',
                    'title': 'Post-order upsell copy',
                },
            },
        }

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Post-purchase',
            category='marketing',
            description='The one product suggested on the order confirmation page.',
            schema=self.get_config_schema(),
        )
