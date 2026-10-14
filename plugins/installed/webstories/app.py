"""Web Stories plugin manifest.

Generates a Google Web Stories AMP document per Product
(``/story/<slug>/``) from the product's images + metafields, and
embeds an ``<amp-story-player>`` thumbnail on the PDP.

Stories are **standalone + self-canonical** (Google's current Web Stories
guidance) — the PDP must NOT declare them via ``rel="amphtml"`` (that pairs an
article with its AMP twin and contradicts a self-canonical story, which is what
triggered the GSC "amp-story canonical error"). Discovery instead comes from:
  * Google Discover carousel
  * Google search 'Visual Stories'
  * the ``<amp-story-player>`` embed on the PDP (a normal link, not a pairing)
  * Story URLs in the main sitemap

Auto-only — every Product save triggers a fresh build via
``services.ensure_story`` (plain text, one idea per page, a 3:4 poster).
Manual per-page editing is a follow-up.
"""

from __future__ import annotations

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock


class WebstoriesPlugin(Plugin):
    name = 'webstories'
    label = 'Web Stories'
    version = '0.2.0'
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

    def contribute_storefront_blocks(self) -> list[StorefrontBlock]:
        # Render the story-player thumbnail BELOW the long description, centered.
        # NOTE: must be `contribute_storefront_blocks` (the base-class
        # contract). A method named `storefront_blocks` is silently
        # ignored by the plugin registry.
        return [
            StorefrontBlock(
                slot='pdp_below_long_description',
                template='storefront/blocks/_webstory_embed.html',
                priority=40,
            ),
            # A booking page (an experience is a catalog Product extended by the booking
            # app); the page puts its `product` and `web_story` in the context like a PDP.
            StorefrontBlock(
                slot='listing_below_description',
                template='storefront/blocks/_webstory_embed.html',
                priority=40,
            ),
        ]

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'show_pdp_embed': {
                    'type': 'boolean',
                    'title': 'Show the story card on product pages',
                    'description': (
                        'The tappable story preview under the long description. '
                        'Stories stay at /story/<product>/ and in the sitemap either way.'
                    ),
                    'default': True,
                },
            },
        }

    def contribute_settings_panel(self) -> SettingsPanel:
        # Until v0.93.0 this was a method named `settings_panel` — not the
        # contract name — so the panel never showed, and none of its three
        # keys was read by anything.
        return SettingsPanel(
            label='Web Stories',
            description=(
                'A story per product, rebuilt whenever the product or its photos '
                'change: the photos, the opening lines, the key points and a link '
                'back to the product.'
            ),
            schema=self.get_config_schema(),
            category='storefront',
        )
