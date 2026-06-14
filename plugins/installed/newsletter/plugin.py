"""Newsletter plugin — subscriber list (double opt-in) + signup popups, under
Marketing. Sending reuses marketing.EmailCampaign (Phase 3). See
docs/plans/newsletter.md.
"""

from __future__ import annotations

from morpheus import DashboardPage, EmailTemplateDef, Plugin, StorefrontBlock


class NewsletterPlugin(Plugin):
    name = 'newsletter'
    label = 'Newsletter'
    version = '0.1.0'
    description = (
        'Email capture (signup popups) + a double-opt-in subscriber list. '
        'Sends reuse the marketing email-campaign engine.'
    )
    has_models = True
    requires = ['marketing']

    def ready(self) -> None:
        # Public capture + one-click confirm/unsubscribe endpoints.
        self.register_urls('plugins.installed.newsletter.urls', prefix='', namespace='newsletter')
        # Merchant dashboard (subscribers + popups), under Marketing.
        self.register_urls(
            'plugins.installed.newsletter.urls_dashboard',
            prefix='dashboard/newsletter/',
            namespace='newsletter_dashboard',
        )

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Newsletter',
                slug='subscribers',
                view='plugins.installed.newsletter.dashboard.subscribers_view',
                icon='mail',
                section='marketing',
                order=60,
                url='/dashboard/newsletter/',
            ),
            DashboardPage(
                label='Signup popups',
                slug='popups',
                view='plugins.installed.newsletter.dashboard.popups_view',
                icon='message-square',
                section='marketing',
                order=61,
                nav='hidden',
                url='/dashboard/newsletter/popups/',
            ),
        ]

    def contribute_storefront_blocks(self) -> list:
        # Renders the active signup popup (with JS triggers) on every page.
        # The template no-ops when no popup is enabled.
        return [
            StorefrontBlock(
                slot='global_below_body',
                template='newsletter/blocks/signup_popup.html',
                priority=70,
            ),
        ]

    def contribute_email_templates(self) -> list:
        return [
            EmailTemplateDef(
                key='newsletter_confirm',
                label='Newsletter — confirm subscription',
                default_subject='Please confirm your subscription',
                group='Newsletter',
                description='Double opt-in confirmation sent when someone subscribes.',
            ),
            EmailTemplateDef(
                key='newsletter_welcome',
                label='Newsletter — welcome',
                default_subject='You’re subscribed 🎉',
                group='Newsletter',
                description='Sent once a subscriber confirms their email.',
            ),
        ]
