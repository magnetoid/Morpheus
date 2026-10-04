"""Journal — a block-editor CMS for store stories.

The existing `cms` plugin is a page store. This plugin adds the
*block editor* the merchant needs to write a long-form journal
piece (the Glossier / Aesop reading format) and a real-time
storefront preview, plus scheduled publishing.

The block format is a JSON document with the shape:

    { "version": 1,
      "blocks": [
        {"type": "text", "data": {"md": "..."}},
        {"type": "image", "data": {"url": "...", "alt": "..."}},
        {"type": "video", "data": {"url": "...", "poster": "..."}},
        {"type": "product", "data": {"slug": "..."}},
        {"type": "collection", "data": {"slug": "..."}},
        {"type": "form", "data": {"form_id": "..."}}
      ] }

The render path: a `Block` record → a context dict → the
`journal/blocks/<type>.html` template.
"""

from __future__ import annotations

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock


class JournalPlugin(Plugin):
    name = 'journal'
    label = 'Journal'
    version = '1.0.0'
    description = (
        'Notion-style block editor + live storefront preview + scheduled '
        'publishing. The block model supports text, image, video, product, '
        'collection, and form blocks — enough to write the long-form '
        'stories that turn a shop into a brand.'
    )
    has_models = True
    requires = ['cms', 'catalog']

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='journal',
                template='journal/blocks/post.html',
                priority=10,
                context_keys=['post'],
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Journal',
            description='Enable/disable journal, default block types, schedule preview window.',
            category='channels',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'enabled': {'type': 'boolean', 'default': True, 'title': 'Enable the journal'},
            },
        }
