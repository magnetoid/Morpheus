"""Post-purchase journey plugin manifest."""

from __future__ import annotations

from morpheus.app import DashboardCard, DashboardPage, Plugin, SettingsPanel


class PostPurchasePlugin(Plugin):
    name = 'post_purchase'
    label = 'Post-purchase journey'
    version = '1.0.0'
    description = (
        'Automates the 4-step post-purchase chain: shipment tracking → '
        'delivered-confirmation → review request → NPS survey. Compounds '
        'LTV via timing nobody else gets right.'
    )

    def ready(self) -> None:
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

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Post-purchase journey',
            category='marketing',
            description=(
                'Per-shop timing + on/off controls for each step of the '
                'post-purchase automation chain.'
            ),
            schema={
                'tracking_email_enabled': {
                    'type': 'boolean',
                    'title': 'Send tracking email when shipment is created',
                    'default': True,
                },
                'delivered_followup_enabled': {
                    'type': 'boolean',
                    'title': 'Send delivered-confirmation follow-up',
                    'default': True,
                },
                'delivered_followup_delay_hours': {
                    'type': 'integer',
                    'title': 'Hours after delivery → follow-up',
                    'minimum': 1,
                    'maximum': 168,
                    'default': 24,
                },
                'review_request_enabled': {
                    'type': 'boolean',
                    'title': 'Send review-request email',
                    'default': True,
                },
                'review_request_delay_days': {
                    'type': 'integer',
                    'title': 'Days after delivery → review request',
                    'minimum': 1,
                    'maximum': 60,
                    'default': 14,
                    'description': (
                        '14 days is the empirically-optimal delay — '
                        'long enough for the customer to actually use the '
                        'product, short enough to still be memorable.'
                    ),
                },
                'nps_survey_enabled': {
                    'type': 'boolean',
                    'title': 'Send NPS survey',
                    'default': True,
                },
                'nps_survey_delay_days': {
                    'type': 'integer',
                    'title': 'Days after delivery → NPS survey',
                    'minimum': 7,
                    'maximum': 90,
                    'default': 30,
                },
            },
        )
