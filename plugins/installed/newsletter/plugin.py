"""Newsletter plugin — subscriber list (double opt-in) + signup popups, under
Marketing. Sending reuses marketing.EmailCampaign (Phase 3). See
docs/plans/newsletter.md.
"""

from __future__ import annotations

from morpheus import EmailTemplateDef, Plugin


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
