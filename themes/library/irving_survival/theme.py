"""
Irving Survival — calm household preparedness, built on direction 1a.

Design notes
------------
- From the owner's design canvases (2026-10, "REMNANT" working name):
  direction 1a "product hero" for the home page, and the inner pages built on
  it (category, product, calculator, bundles, checkout).
- Warm grey ground (#F3F2EE), white surfaces, near-black ink (#121311), one
  orange signal (#E8590C) used sparingly. Geist for everything, Geist Mono
  for labels and figures. Pill buttons, 24-28px tiles, no shadows.
- The copy is Irving's own voice: calm, UK-specific, honest about limits.
  Numbers the theme prints (water per person, the 105 power-cut line) come
  from the UK Government's Prepare guidance and say so.
- The supply calculator and the readiness check run in the browser and
  store nothing on the server; neither invents a figure about the visitor.
- Same storefront contract as supernatural_shop (slots, head contract,
  account and auth pages), restyled. Activate only via instance env.
"""

from __future__ import annotations

from themes.base import MorpheusTheme


class IrvingSurvivalTheme(MorpheusTheme):
    name = 'irving_survival'
    label = 'Irving Survival'
    version = '0.1.0'
    description = (
        'Calm household-preparedness storefront: warm grey, ink and one orange '
        'signal, set in Geist. Supply calculator and readiness check built in.'
    )
    author = 'Morph Team'
    supports_plugins = ['storefront', 'catalog', 'orders']
    head_contract = 1
    vendor_noun = 'Supplier'
    vendor_noun_plural = 'Suppliers'
    demo_topic = 'general_store'
    preview_image = 'preview.png'

    def get_design_tokens(self) -> dict:
        return {
            'colors': {
                'background': '#F3F2EE',
                'surface': '#FFFFFF',
                'surface2': '#E7E6E1',
                'foreground': '#121311',
                'muted': '#5B5D58',
                'accent': '#E8590C',
                'accent_text': '#B93D06',
                'ok': '#2B8A3E',
            },
            'fonts': {'display': 'Geist', 'body': 'Geist', 'mono': 'Geist Mono'},
            'radii': {'sm': '14px', 'md': '20px', 'lg': '28px', 'pill': '999px'},
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
                'tagline': {
                    'type': 'string',
                    'default': 'Calm, practical preparedness for UK households.',
                    'title': 'Tagline (single line)',
                },
                'show_status_bar': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Show the status line above the header',
                },
                'status_text': {
                    'type': 'string',
                    'default': 'Power cut in England, Scotland or Wales? Call 105, free.',
                    'title': 'Status line',
                },
            },
        }
