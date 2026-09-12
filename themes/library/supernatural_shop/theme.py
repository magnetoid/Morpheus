"""Supernatural Shop — dark storefront theme for supernatural-shop.com.

Morpheus requires snake_case theme names. Activate with
`MORPHEUS_ACTIVE_THEME=supernatural_shop`. The public brand is
Supernatural Shop.
"""

from __future__ import annotations

from themes.base import MorpheusTheme


class SupernaturalShopTheme(MorpheusTheme):
    name = 'supernatural_shop'
    label = 'Supernatural Shop'
    version = '0.1.0'
    description = (
        'Dark gold storefront for supernatural-shop.com. Night paper, '
        'warm type, a single brass accent.'
    )
    author = 'Morph Team'
    supports_plugins = ['storefront', 'catalog', 'orders']
    head_contract = 1
    demo_topic = 'general_store'
    preview_image = 'preview.png'

    def get_design_tokens(self) -> dict:
        return {
            'colors': {
                'background': '#0c0a09',
                'foreground': '#f4efe6',
                'accent': '#c9a227',
            },
            'fonts': {'display': 'Cormorant Garamond', 'body': 'Outfit'},
            'radii': {'sm': '4px', 'md': '8px', 'lg': '16px'},
            'spacing': {'xs': '4px', 'sm': '8px', 'md': '16px', 'lg': '24px', 'xl': '48px'},
        }

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'brand_name': {
                    'type': 'string',
                    'default': 'Supernatural Shop',
                    'title': 'Brand name',
                },
                'tagline': {
                    'type': 'string',
                    'default': 'Objects with a pulse.',
                    'title': 'Tagline (single line)',
                },
                'accent_color': {
                    'type': 'string',
                    'default': '#c9a227',
                    'title': 'Accent color',
                },
                'newsletter_pitch': {
                    'type': 'string',
                    'default': 'Rare drops, no noise.',
                    'title': 'Newsletter pitch',
                },
            },
        }
