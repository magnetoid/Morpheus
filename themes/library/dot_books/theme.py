"""
dot books — a modern, editorial bookstore theme.

Design notes
------------
- Off-white "newsprint" background with deep ink text.
- A single ink-red accent (#E63946) used for the period in the wordmark
  and the primary CTA — nothing else.
- Headlines in a high-contrast serif (Fraunces). Body in Inter.
- Generous whitespace; long-form content treated as editorial, not retail.
- Built on the Morpheus storefront views, so all data flows through
  GraphQL (`api.client.internal_graphql`) — see LAW 3.
"""

from __future__ import annotations

from themes.base import MorpheusTheme


class DotBooksTheme(MorpheusTheme):
    name = 'dot_books'
    label = 'dot books — modern bookstore'
    version = '1.1.0'
    description = (
        'Editorial, type-forward bookstore theme for "dot books". Cream paper, '
        'ink black, a single red dot.'
    )
    author = 'Morph Team'
    supports_plugins = ['storefront', 'catalog', 'orders']
    # base.html calls `{% storefront_head %}` and emits no SEO markup of its own.
    head_contract = 1
    # The marketplace's vendors, in this store's words (see MorpheusTheme).
    vendor_noun = 'Publisher'
    vendor_noun_plural = 'Publishers'
    demo_topic = 'bookstore'

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'brand_name': {
                    'type': 'string',
                    'default': 'dot books',
                    'title': 'Brand name (without trailing dot)',
                },
                'tagline': {
                    'type': 'string',
                    'default': 'a quieter shelf for louder books',
                    'title': 'Tagline (single line)',
                },
                'accent_color': {
                    'type': 'string',
                    'default': '#E63946',
                    'title': 'Accent color (the dot)',
                },
                'newsletter_pitch': {
                    'type': 'string',
                    'default': 'One letter a month. New titles, staff picks, no spam. Just books.',
                    'title': 'Newsletter pitch',
                },
            },
        }
