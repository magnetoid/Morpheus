"""Newsletter plugin — subscriber list (double opt-in) + signup popups, under
Marketing. Sending reuses marketing.EmailCampaign (Phase 3). See
docs/plans/newsletter.md.
"""

from __future__ import annotations

from morpheus.core import events
from morpheus.plugin import DashboardPage, EmailTemplateDef, Plugin, SettingsPanel, StorefrontBlock


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
        # Merchant dashboard (subscribers + popups + campaign sending), under Marketing.
        self.register_urls(
            'plugins.installed.newsletter.urls_dashboard',
            prefix='dashboard/newsletter/',
            namespace='newsletter_dashboard',
        )
        # Win-back: the nightly RFM rescore fires this on segment flips; we act
        # on the drop to at-risk (consent-gated + deduped inside send_winback).
        self.register_hook(events.CUSTOMER_SEGMENT_CHANGED, self.on_segment_changed, priority=50)

    def on_segment_changed(self, customer=None, new=None, **kwargs):
        """Queue a win-back email when a customer slips to at-risk.

        Fail-soft — a marketing side-effect must never break the rescore task.
        All the guards (consent, dedupe window, config toggle) live in
        ``tasks.send_winback``.
        """
        if customer is None or new != 'at_risk':
            return
        try:
            if not self.get_config_value('winback_enabled', True):
                return
            from plugins.installed.newsletter.tasks import send_winback

            send_winback(customer)
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger('morpheus.newsletter').warning(
                'winback for %s failed: %s', getattr(customer, 'pk', '?'), exc, exc_info=True
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
            DashboardPage(
                label='Send campaigns',
                slug='newsletter-campaigns',
                view='plugins.installed.newsletter.dashboard.campaigns_view',
                icon='send',
                section='marketing',
                order=62,
                url='/dashboard/newsletter/campaigns/',
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

    def contribute_agent_tools(self) -> list:
        from plugins.installed.newsletter.agent_tools import (
            newsletter_create_popup_tool,
            newsletter_list_subscribers_tool,
            newsletter_stats_tool,
            newsletter_toggle_popup_tool,
        )

        return [
            newsletter_stats_tool,
            newsletter_list_subscribers_tool,
            newsletter_create_popup_tool,
            newsletter_toggle_popup_tool,
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
            EmailTemplateDef(
                key='newsletter_winback',
                label='Newsletter — win-back',
                default_subject='We saved some books for you',
                group='Newsletter',
                description=(
                    'Sent (at most once a month) when a subscribed customer '
                    'slips into the at-risk RFM segment.'
                ),
            ),
        ]

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='Newsletter',
            description='Win-back automation for lapsed, subscribed customers.',
            schema=self.get_config_schema(),
            category='marketing',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'winback_enabled': {
                    'type': 'boolean',
                    'title': 'Send win-back emails',
                    'description': (
                        'Email confirmed subscribers when they slip into the '
                        'at-risk segment (max one per address per 30 days).'
                    ),
                    'default': True,
                },
                'winback_coupon_code': {
                    'type': 'string',
                    'title': 'Win-back coupon code',
                    'description': (
                        'Optional existing coupon code to include in the '
                        'win-back email. Leave blank for none.'
                    ),
                    'default': '',
                },
            },
        }
