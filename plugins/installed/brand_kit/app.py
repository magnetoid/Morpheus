"""Brand asset library + design tokens.

The merchant uploads brand assets here. The plugin:

  * stores them with auto-crop + variant generation (we don't
    auto-crop in this MVP — we just store the source + a `tags`
    list — the variants are derived in the CDN with a single
    function in the storefront template);
  * emits design tokens (colors, fonts, spacing, radii) as CSS
    variables that the storefront consumes via
    `{% include 'brand_kit/blocks/tokens.html' %}`;
  * ships an "AI brand kit" endpoint that reads the merchant's
    hero imagery and returns a palette + typography suggestion
    (the suggestion is then saved to `DesignTokenSet`).
"""

from __future__ import annotations

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock


class BrandKitPlugin(Plugin):
    name = 'brand_kit'
    label = 'Brand kit'
    version = '1.0.0'
    description = (
        'Central brand asset library. Emits design tokens (colors, fonts, '
        'spacing, radii) as CSS variables the storefront consumes. Ships '
        'an AI brand-kit generator that reads hero imagery and produces a '
        'palette + typography the rest of the surface runs on.'
    )
    has_models = True
    requires = ['media']

    def ready(self) -> None:
        # The render layer the token block always assumed existed. Contributed
        # (not listed in settings.TEMPLATES) so the tokens vanish on disable.
        from plugins.installed.brand_kit.context_processors import brand_kit_tokens

        self.register_context_processor(brand_kit_tokens)

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='global_head',
                template='brand_kit/blocks/tokens.html',
                priority=2,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Brand kit',
            description='Active token set, asset tag taxonomy, AI brand kit generator.',
            category='storefront',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'active_token_set': {
                    'type': 'string',
                    'default': 'default',
                    'title': 'Active design-token set (slug)',
                },
            },
        }
