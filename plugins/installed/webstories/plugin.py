"""Web Stories plugin manifest.

Generates a Google Web Stories AMP document per Product
(``/story/<slug>/``) from the product's images + metafields, and
embeds an ``<amp-story-player>`` thumbnail on the PDP.

Discovery surfaces:
  * Google Discover carousel
  * Google search 'Visual Stories'
  * ``<link rel="amphtml">`` from the PDP
  * Story URLs in the main sitemap

V1 is auto-only — every Product save triggers a fresh build via
``services.ensure_story``. Manual per-panel editing is a v2 follow-up.
"""

from __future__ import annotations

from morpheus import Plugin, SettingsPanel, StorefrontBlock


class WebstoriesPlugin(Plugin):
    name = 'webstories'
    label = 'Web Stories'
    version = '0.1.0'
    description = (
        'Auto-generates Google-indexable AMP Web Stories from product '
        'images and embeds an <amp-story-player> on the product page.'
    )

    def ready(self) -> None:
        # Mount /story/<slug>/ at the storefront root (no /dashboard/
        # prefix) so the URL feels native and crawlers find it.
        self.register_urls(
            'plugins.installed.webstories.urls',
            prefix='',
            namespace='webstories',
        )

    def storefront_blocks(self) -> list[StorefrontBlock]:
        # Render the story-player thumbnail above the long description —
        # high prominence without crowding the price/add-to-cart band.
        return [
            StorefrontBlock(
                slot='pdp_above_long_description',
                template='storefront/blocks/_webstory_embed.html',
                priority=40,
            )
        ]

    def settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            slug='webstories',
            label='Web Stories',
            category='channels',
            description=(
                'Auto-generated Web Stories per product. Stories are '
                'rebuilt on every product save and image change.'
            ),
            schema={
                'enabled': {
                    'type': 'boolean',
                    'title': 'Enable Web Stories',
                    'default': True,
                    'description': (
                        'When off, /story/<slug>/ returns 404 and the PDP embed renders nothing.'
                    ),
                },
                'show_pdp_embed': {
                    'type': 'boolean',
                    'title': 'Show the amp-story-player on PDP',
                    'default': True,
                },
                'theme': {
                    'type': 'string',
                    'title': 'Story theme',
                    'enum': ['paper', 'cream', 'dark'],
                    'default': 'paper',
                    'description': 'Background color when an image is missing.',
                },
            },
        )
