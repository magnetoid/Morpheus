"""UGC reviews + creator program.

The existing `reviews` plugin stores a `rating` + `body`. This plugin
layers:

  * photo + video uploads per review (1-N);
  * a creator tier with a small stipend prompt that fires 90 days
    post-delivery (the *delay* is the magic, per Bazaarvoice);
  * approved UGC auto-rendering on the PDP gallery (via
    `StorefrontBlock(pdp_below_gallery)`) and the home-page story
    rail (via the `cms` plugin's journal hook).

No cross-plugin imports — approved UGC is read via the existing
`reviews` model through a guarded `reviews.ugc_for_product` filter
that the `reviews` plugin ships and this plugin consumes via the
hook bus.
"""

from __future__ import annotations

from morpheus.plugin import Plugin, SettingsPanel, StorefrontBlock


class UgcReviewsPlugin(Plugin):
    name = 'ugc_reviews'
    label = 'UGC reviews + creator program'
    version = '1.0.0'
    description = (
        'Photo + video reviews. Auto-moderation. Creator tier with 90-day '
        'post-delivery prompt. Approved UGC surfaces in PDP gallery and '
        'home-page story rail.'
    )
    has_models = True
    requires = ['reviews', 'post_purchase', 'consent']

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='pdp_below_gallery',
                template='ugc_reviews/blocks/ugc_gallery.html',
                priority=30,
                context_keys=['product'],
            ),
            StorefrontBlock(
                slot='pdp_above_long_description',
                template='ugc_reviews/blocks/ugc_highlights.html',
                priority=30,
                context_keys=['product'],
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='UGC reviews + creator program',
            description='Auto-moderation, creator tier eligibility, photo + video upload budget.',
            category='marketing',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'allow_photo': {'type': 'boolean', 'default': True, 'title': 'Allow photo uploads'},
                'allow_video': {'type': 'boolean', 'default': True, 'title': 'Allow video uploads'},
                'max_video_seconds': {
                    'type': 'integer',
                    'default': 60,
                    'title': 'Max video length (seconds)',
                },
                'creator_prompt_delay_days': {
                    'type': 'integer',
                    'default': 90,
                    'title': 'Days after delivery → creator prompt',
                    'description': '90 days is empirically optimal — long enough to use the product, short enough to still be memorable.',
                },
                'creator_stipend_currency': {
                    'type': 'string',
                    'default': 'USD',
                    'title': 'Creator stipend currency',
                },
                'creator_stipend_amount': {
                    'type': 'number',
                    'default': 25,
                    'title': 'Creator stipend amount (paid via store credit, not cash)',
                },
            },
        }
