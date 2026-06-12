"""Rich post-purchase — multichannel (email + SMS + WhatsApp + push).

Extends the existing `post_purchase` chain (which is email-only)
with merchant-tunable per-step channel choice. Each step in the
chain (tracking, delivered, review request, NPS) gets a
`channels: list[Channel]` field on the timing panel.

The chain's *content* is what makes it vibe-coded: the 14-day-delayed
review request embeds a journal article the merchant authors (a
"How to use it" guide); the 30-day-delayed NPS embeds a brand
asset gallery; the 90-day UGC prompt is now the `ugc_reviews`
plugin's domain.

Channels supported by this plugin:
  * `email`     — the platform's transactional email
  * `sms`       — opt-in, gateway-agnostic (Twilio adapter)
  * `whatsapp`  — opt-in, WhatsApp Business adapter
  * `push`      — PWA push (via the `pwa` plugin)
"""
from __future__ import annotations

from morpheus import Plugin, SettingsPanel


class RichPostPurchasePlugin(Plugin):
    name = 'rich_post_purchase'
    label = 'Rich post-purchase'
    version = '1.0.0'
    description = (
        'Multichannel post-purchase chain: email + SMS + WhatsApp + PWA '
        'push, with merchant-tunable per-step channel choice and rich '
        'content blocks (journal articles, brand assets, UGC prompts).'
    )
    has_models = True
    requires = ['post_purchase', 'consent']

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Rich post-purchase',
            description='Per-step channel choice, content blocks, opt-in gating.',
            category='notifications',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'tracking_channels': {
                    'type': 'array',
                    'items': {'type': 'string', 'enum': ['email', 'sms', 'whatsapp', 'push']},
                    'default': ['email'],
                    'title': 'Channels for the tracking email step',
                },
                'delivered_channels': {
                    'type': 'array',
                    'items': {'type': 'string', 'enum': ['email', 'sms', 'whatsapp', 'push']},
                    'default': ['email'],
                    'title': 'Channels for the delivered-confirmation step',
                },
                'review_channels': {
                    'type': 'array',
                    'items': {'type': 'string', 'enum': ['email', 'sms', 'whatsapp', 'push']},
                    'default': ['email'],
                    'title': 'Channels for the review request step',
                },
                'nps_channels': {
                    'type': 'array',
                    'items': {'type': 'string', 'enum': ['email', 'sms', 'whatsapp', 'push']},
                    'default': ['email'],
                    'title': 'Channels for the NPS survey step',
                },
                'embed_journal_articles': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Embed a journal article in the 14-day review step',
                },
                'embed_brand_assets': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Embed brand asset gallery in the 30-day NPS step',
                },
            },
        }
