"""
Supernatural Shop — editorial storefront, same bones as dot_books.

Design notes
------------
- Light linen paper (#faf7f2) and dark ink. Not Dot Books cream/red.
- One brass accent (#c9a227) on the wordmark period and primary CTA.
- Display in Cormorant Garamond. Body in Outfit.
- Same layout contract as dot_books (topbar, window hero, cards, PDP).
- Activate only via instance env. Do not commit MORPHEUS_ACTIVE_THEME.
"""

from __future__ import annotations

from themes.base import MorpheusTheme


class SupernaturalShopTheme(MorpheusTheme):
    name = 'supernatural_shop'
    label = 'Supernatural Shop'
    version = '0.1.3'
    description = (
        'Light editorial shop theme. Linen paper, dark ink, a single brass mark. '
        'Built on the dot_books storefront contract.'
    )
    author = 'Morph Team'
    supports_plugins = ['storefront', 'catalog', 'orders']
    head_contract = 1
    demo_topic = 'general_store'
    preview_image = 'preview.png'

    def get_design_tokens(self) -> dict:
        return {
            'colors': {
                'background': '#faf7f2',
                'foreground': '#1c1612',
                'accent': '#c9a227',
            },
            'fonts': {'display': 'Cormorant Garamond', 'body': 'Outfit'},
            'radii': {'sm': '4px', 'md': '8px', 'lg': '16px'},
            'spacing': {
                'xs': '4px',
                'sm': '8px',
                'md': '16px',
                'lg': '24px',
                'xl': '48px',
            },
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
                    'default': 'objects with a pulse',
                    'title': 'Tagline (single line)',
                },
                'accent_color': {
                    'type': 'string',
                    'default': '#c9a227',
                    'title': 'Accent color',
                },
                'newsletter_pitch': {
                    'type': 'string',
                    'default': 'Rare drops. No noise.',
                    'title': 'Newsletter pitch',
                },
            },
        }
