"""Discovery quiz funnel — zero-party data, vibe-coded.

A merchant-configurable quiz funnel: zero-party-data questions
("What's your skin type?", "What's the gift's occasion?") that end
in a personalised category view. The answers persist in the
customer's `metafields`, drive the personalised rails, and (with
consent) power segmentation.

The "brand voice" in the quiz *is* the merchant's tone of voice —
copy + motion + illustration become the funnel.
"""

from __future__ import annotations

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock


class DiscoveryQuizPlugin(Plugin):
    name = 'discovery_quiz'
    label = 'Discovery quiz'
    version = '1.0.0'
    description = (
        'Zero-party-data quiz funnel that ends in a personalised category '
        'view. Answers persist in the customer metafield, drive the '
        'personalised rails, and (with consent) power segmentation.'
    )
    has_models = True
    requires = ['catalog', 'metafields', 'consent']

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='checkout_extra',
                template='discovery_quiz/blocks/personalised_results.html',
                priority=30,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Discovery quiz',
            description='Active quiz, question order, result-template mapping.',
            category='marketing',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'require_consent': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Require consent to save answers to metafields',
                },
            },
        }
