"""Motion + skeleton states.

A small `motion` plugin that ships a CSS + JS layer of:

  * page-transition choreography (the *one* thing that makes a
    storefront feel expensive);
  * scroll-snap story progress (the "tap-to-see-why" feel);
  * button-press micro-feel;
  * skeleton shimmer for slow GraphQL queries (replaces blank
    loading states).

Default-on, brand-color-tinted, no config required. Every
animation respects `prefers-reduced-motion` — and the plugin's
`reduced_motion_default` setting lets the merchant default to
reduced motion server-side too.

No models — pure CSS + JS, contributed once to
`global_head` and once to `global_below_body`.
"""

from __future__ import annotations

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock


class MotionPlugin(Plugin):
    name = 'motion'
    label = 'Motion'
    version = '1.0.0'
    description = (
        'Page-transition choreography, scroll-snap story progress, '
        'button-press micro-feel, skeleton shimmer for slow GraphQL '
        'queries. Brand-color-tinted, no config required.'
    )
    has_models = False
    requires = []

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='global_head',
                template='motion/blocks/styles.html',
                priority=1,
            ),
            StorefrontBlock(
                slot='global_below_body',
                template='motion/blocks/runtime.html',
                priority=0,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Motion + skeleton states',
            description='Intensity, reduced-motion default, brand-color tint.',
            category='general',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'intensity': {
                    'type': 'string',
                    'enum': ['off', 'minimal', 'standard', 'rich'],
                    'default': 'standard',
                    'title': 'Motion intensity',
                },
                'reduced_motion_default': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Default to reduced motion (server-side hint; client prefers-reduced-motion always wins)',
                },
            },
        }
