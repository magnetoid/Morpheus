"""
Dawnchild — the storefront of Dawnchild Books, an imprint of illustrated books
for children and the whole family.

Design notes
------------
- From the owner's six "soft" page designs (2026-11): Home, Books, About,
  Authors, Notes and Trade. An olive field with parchment cartouches set on
  it, the way the 1926 cover of *The Dawnchild* sets its title panel on the
  garden; reading pages sit on cream paper. Libre Caslon throughout, square
  corners, ink rules, one russet for the action a page needs.
- ``static/dawnchild/dawnchild.css`` is the design's own stylesheet, every
  layer once. ``compat.css`` gives the shared shop pages (product, basket,
  checkout, account) the same palette through the token names they already
  use, so they work unchanged.
- Navigation belongs to the CMS: the header reads the ``header`` menu and the
  footer the ``footer`` menu; the links the design shows are the fallback
  for a store that has not built its menus yet.
- Books, prices and covers come from the catalogue, never from the theme: a
  shelf with no products says so, and a signup form says only what the
  newsletter app answered.
- The home banner is the design's fixed opening of *The Dawnchild*. Its
  illustration is the store's own: the ``hero_image_url`` setting names an
  image in its media library, shown whole beside the words (without it the
  banner closes up to one column), and ``hero_link_url`` names the page on
  this store its button leads to (empty leads to the shelf).
- Activate only via instance env (``MORPHEUS_ACTIVE_THEME=dawnchild``) or the
  dashboard's theme picker. Nothing else changes when this theme is present.
"""

from __future__ import annotations

from themes.base import MorpheusTheme


class DawnchildTheme(MorpheusTheme):
    name = 'dawnchild'
    label = 'Dawnchild'
    version = '0.1.0'
    description = (
        'Illustrated-book imprint storefront: an olive field, parchment panels '
        'and ink rules, set in Libre Caslon. Shelves, authors, notes and a trade page.'
    )
    author = 'Morph Team'
    supports_plugins = ['storefront', 'catalog', 'orders', 'cms', 'book_product', 'newsletter']
    head_contract = 1
    vendor_noun = 'Publisher'
    vendor_noun_plural = 'Publishers'
    demo_topic = 'bookstore'

    def get_design_tokens(self) -> dict:
        return {
            'colors': {
                'background': '#b9ab60',
                'reading': '#efe6cf',
                'header': '#8a7f3d',
                'surface': '#e9ddc0',
                'surface2': '#d4c29c',
                'foreground': '#0b0e06',
                'muted': '#2e2a12',
                'dark': '#4b4025',
                'accent': '#7c4a2b',
                'accent_text': '#5e3620',
            },
            'fonts': {'display': 'Libre Caslon Display', 'body': 'Libre Caslon Text'},
            'radii': {'sm': '0px', 'md': '0px', 'lg': '0px'},
            'spacing': {'xs': '4px', 'sm': '8px', 'md': '16px', 'lg': '24px', 'xl': '48px'},
        }

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'notice_text': {
                    'type': 'string',
                    'default': '',
                    'title': 'Notice under the header (empty hides it)',
                },
                'imprint_line': {
                    'type': 'string',
                    'default': '',
                    'title': 'Line under the footer wordmark',
                },
                'trade_email': {
                    'type': 'string',
                    'default': '',
                    'title': 'Trade email (shown on the trade page)',
                },
                'hero_image_url': {
                    'type': 'string',
                    'default': '',
                    'title': (
                        'Home banner illustration: address of an image in the media library '
                        '(empty shows the words alone)'
                    ),
                },
                'hero_image_alt': {
                    'type': 'string',
                    'default': '',
                    'title': 'Home banner illustration: what it shows, for screen readers',
                },
                'hero_link_url': {
                    'type': 'string',
                    'default': '',
                    'title': (
                        'Home banner: the page on this store "Read the first chapter" and the '
                        "book's name lead to, starting with / (empty leads to the shelf)"
                    ),
                },
                'christmas_look': {
                    'type': 'string',
                    'enum': ['off', 'dates', 'on'],
                    'default': 'off',
                    'title': (
                        'Christmas look: off, dates (every year between the two days below) '
                        'or on (shown now, to preview it)'
                    ),
                },
                'christmas_from': {
                    'type': 'string',
                    'default': '01-12',
                    'pattern': r'\d{2}-\d{2}',
                    'examples': ['01-12'],
                    'title': 'Christmas look starts (day-month, DD-MM; 01-12 is 1 December)',
                },
                'christmas_until': {
                    'type': 'string',
                    'default': '06-01',
                    'pattern': r'\d{2}-\d{2}',
                    'examples': ['06-01'],
                    'title': 'Christmas look ends, that day included (DD-MM; 06-01 is 6 January)',
                },
            },
        }

    def christmas_on(self) -> bool:
        """Whether today, on the store's clock, the Christmas look shows
        (``christmas.py`` holds the rule)."""
        from core.utils.site import store_today  # noqa: PLC0415
        from themes.library.dawnchild.christmas import is_on  # noqa: PLC0415

        return is_on(self.get_config(), store_today())
