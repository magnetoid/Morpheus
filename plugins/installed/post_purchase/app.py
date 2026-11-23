"""Post-purchase journey plugin manifest."""

from __future__ import annotations

from morpheus.app import DashboardCard, DashboardPage, Plugin, SettingsPanel, StorefrontBlock
from morpheus.core import events


class PostPurchasePlugin(Plugin):
    name = 'post_purchase'
    label = 'Post-purchase journey'
    version = '1.0.0'
    description = (
        'Emails a delivery check, a review request and an NPS survey after each '
        'order, as you switch them on, runs the survey and its report, and suggests '
        'one product on the order confirmation page.'
    )
    requires = ['orders', 'catalog']
    # The Celery worker reads these too: without a window it would keep the
    # settings it first read until the next deploy (sending what was switched off).
    config_fresh_s = 30.0

    def ready(self) -> None:
        from plugins.installed.post_purchase.handlers import (  # noqa: PLC0415
            on_order_delivered,
            on_order_fulfilled,
        )

        # Owned, so the bus stops calling them while the app is off.
        self.register_hook(events.ORDER_FULFILLED, on_order_fulfilled, priority=60)
        self.register_hook(events.ORDER_DELIVERED, on_order_delivered, priority=60)
        from plugins.installed.post_purchase.tasks import on_email_delivered  # noqa: PLC0415

        # A step is 'sent' only once its email went out.
        self.register_hook(events.EMAIL_DELIVERED, on_email_delivered, priority=50)
        self.register_urls(
            'plugins.installed.post_purchase.urls',
            prefix='post-purchase/',
            namespace='post_purchase',
        )
        # Sends the steps that are due (registered name, not the module path).
        self.register_celery_beat(
            'post_purchase:process_due_steps',
            {'task': 'post_purchase.process_due_steps', 'schedule': 15 * 60},
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
        # Every email starts off: until v0.189.0 none was ever sent.
        return {
            'type': 'object',
            'properties': {
                'delivered_followup_enabled': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Ask whether the order arrived',
                },
                'delivered_followup_delay_hours': {
                    'type': 'integer',
                    'default': 24,
                    'minimum': 1,
                    'maximum': 720,
                    'title': 'Hours after the order is marked delivered',
                },
                'review_request_enabled': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Ask for a review',
                    'description': "Marketing: sent only with the customer's consent.",
                },
                'review_request_delay_days': {
                    'type': 'integer',
                    'default': 14,
                    'minimum': 1,
                    'maximum': 365,
                    'title': 'Days after delivery',
                },
                'nps_survey_enabled': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Send the NPS survey',
                    'description': "Marketing: sent only with the customer's consent.",
                },
                'nps_survey_delay_days': {
                    'type': 'integer',
                    'default': 30,
                    'minimum': 1,
                    'maximum': 365,
                    'title': 'Days after delivery',
                },
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
            description=(
                'The emails after an order (each starts off) and the one product '
                'suggested on the order confirmation page.'
            ),
            schema=self.get_config_schema(),
        )

    def contribute_email_templates(self) -> list:
        from morpheus.app import EmailTemplateDef  # noqa: PLC0415

        return [
            EmailTemplateDef(
                key='post_purchase_delivered',
                label='Did your order arrive?',
                default_subject='Did order #{{ order.order_number }} arrive safely?',
                group='Orders',
                description='Asks after delivery whether the order arrived, and invites '
                'a reply if anything is wrong.',
            ),
            EmailTemplateDef(
                key='post_purchase_review',
                label='Review request',
                default_subject='How was order #{{ order.order_number }}?',
                group='Marketing',
                description='Asks for a review of each product on the order. Sent only '
                "with the customer's consent, with an unsubscribe link.",
            ),
            EmailTemplateDef(
                key='post_purchase_nps',
                label='NPS survey',
                default_subject='Quick 30-second survey?',
                group='Marketing',
                description='Asks how likely the customer is to recommend the shop, '
                "from 0 to 10. Sent only with the customer's consent, with an "
                'unsubscribe link.',
            ),
        ]
