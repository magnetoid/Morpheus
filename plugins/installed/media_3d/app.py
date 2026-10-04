"""3D / AR / Shoppable video.

The existing `bookstore_3d` plugin proves the data model for a 3D
asset attached to a product. This plugin:

  * Generalises that model so any product type can carry a `.glb`
    (Android Scene Viewer) + `.usdz` (iOS Quick Look) pair;
  * Emits a `StorefrontBlock` that swaps in the correct viewer
    based on the device's `User-Agent`;
  * Exposes a GraphQL extension to surface shoppable-video time
    markers → product cards;
  * Adds a guardrail: any PDP that ships more than the configured
    `max_glb_size_mb` falls back to a static poster (no
    experience-destroying mobile 30 MB glb downloads).

The plugin never imports a sibling plugin's models; assets live in
its own `Asset3D` model keyed to `catalog.Product`.
"""

from __future__ import annotations

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock


class Media3dPlugin(Plugin):
    name = 'media_3d'
    label = '3D / AR / Shoppable video'
    version = '1.0.0'
    description = (
        'Per-product 3D + AR previews (.glb for Android, .usdz for iOS). '
        'Auto-detects device, ships a fast-fail glb-size budget, and pairs '
        'with the shoppable-video block on the PDP.'
    )
    has_models = True
    requires = ['catalog']

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='pdp_below_gallery',
                template='media_3d/blocks/viewer.html',
                priority=10,
                context_keys=['product'],
            ),
            StorefrontBlock(
                slot='pdp_above_long_description',
                template='media_3d/blocks/shoppable_video.html',
                priority=40,
                context_keys=['product'],
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='3D / AR / Shoppable video',
            description='Size budgets, viewer defaults, shoppable-video card slots.',
            category='general',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'max_glb_size_mb': {
                    'type': 'integer',
                    'minimum': 1,
                    'maximum': 100,
                    'default': 12,
                    'title': 'Max .glb size (MB) before falling back to a static poster',
                },
                'shoppable_video_max_cards': {
                    'type': 'integer',
                    'minimum': 0,
                    'maximum': 20,
                    'default': 6,
                    'title': 'Maximum shoppable-product cards per video',
                },
            },
        }
