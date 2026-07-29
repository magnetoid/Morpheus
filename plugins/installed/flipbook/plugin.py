"""Flipbook plugin manifest — renders any digital product's PDF as a
3D-flipping book preview using PDF.js (Mozilla) + StPageFlip (MIT).

Both libraries load from a CDN, so no npm/pip install is required.
The full PDF is fetched at view time and rendered page-by-page in
the browser; no thumbnail generation step at upload.
"""

from __future__ import annotations

from morpheus.plugin import Plugin, SettingsPanel, StorefrontBlock


class FlipbookPlugin(Plugin):
    name = 'flipbook'
    label = 'Flipbook PDF preview'
    version = '1.0.0'
    description = 'Adds a 3D page-flipping PDF preview to any product with a digital_file attached.'

    def ready(self) -> None:
        # Mounts /p/<slug>/flipbook/ at the storefront root (no /dashboard/
        # prefix) so the URL feels native to the storefront.
        self.register_urls(
            'plugins.installed.flipbook.urls',
            prefix='',
            namespace='flipbook',
        )

    def contribute_settings_panel(self) -> SettingsPanel:
        # SettingsPanel takes (label, schema, description, plugin, category) —
        # no `slug` kwarg. The plugin name is set on the dataclass by the
        # registry after collection.
        return SettingsPanel(
            label='Flipbook preview',
            category='channels',
            description='Per-store flipbook preview controls.',
            schema={
                'type': 'object',
                'properties': {
                    'enabled': {
                        'type': 'boolean',
                        'title': 'Enable flipbook preview',
                        'default': True,
                        'description': 'When off, the storefront block + URL both 404.',
                    },
                    'max_preview_pages': {
                        'type': 'integer',
                        'title': 'Max pages to expose in preview',
                        'minimum': 0,
                        'maximum': 500,
                        'default': 20,
                        'description': 'Limits how many PDF pages render in the public preview. 0 = full book.',
                    },
                    'theme': {
                        'type': 'string',
                        'title': 'Page background',
                        'enum': ['paper', 'cream', 'dark'],
                        'default': 'paper',
                    },
                },
            },
        )

    def contribute_storefront_blocks(self) -> list[StorefrontBlock]:
        # Storefront block that appears under the PDP "Add to cart" form,
        # offering a "Flip through a preview" CTA for products with a
        # digital_file. The block template gates itself on the product
        # type / file presence.
        # NOTE: must be `contribute_storefront_blocks` (the base-class
        # contract); `storefront_blocks` is silently ignored by the
        # registry.
        return [
            StorefrontBlock(
                slot='pdp_below_form',
                template='storefront/blocks/_flipbook_cta.html',
                priority=50,
            )
        ]
