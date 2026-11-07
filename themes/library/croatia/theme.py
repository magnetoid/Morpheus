"""
croatia — the Croatia Experience marketplace theme (croatia-experience.me).

Design notes
------------
- Sea-tinted near-white background with deep blue-ink text.
- Deep Adriatic blue (#1a4f89) is the primary brand / CTA colour; a terracotta
  roof-tile red (#c7471f) handles urgency / secondary CTAs.
- Headlines in an editorial serif (Playfair Display). Body in Inter.
- Soft, rounded cards (0.75rem) with sea-tinted shadows — an Airbnb-style
  travel marketplace feel rather than a retail grid.
- Ported from the montenegro-experience-hub "Adriatic Design System".
- Built on the Morpheus storefront views, so all data flows through
  GraphQL (`api.client.internal_graphql`) — see LAW 3.

A copy of the montenegro theme (owner, 2026-11-07), itself derived from dot_books:
the same templates and slots, with Croatia's copy, colours, images and Croatian
(/hr/) in place of Serbian. A fix to one of the two usually belongs in both. Keeping the same
template paths means upstream Morpheus storefront updates keep working.
"""

from __future__ import annotations

from themes.base import MorpheusTheme


class CroatiaTheme(MorpheusTheme):
    name = 'croatia'
    label = 'Croatia Experience — Adriatic marketplace'
    version = '0.1.0'
    description = (
        'Croatian travel marketplace theme. Sea-tinted paper, deep Adriatic '
        'blue, terracotta accent, editorial serif headlines.'
    )
    author = 'Croatia Experience'
    supports_plugins = ['storefront', 'catalog', 'orders', 'marketplace', 'booking_marketplace']
    # The homepage loads `{% load booking_tags %}` and calls six tags that only
    # exist in the booking_marketplace vertical app. A store without that app
    # would 500 on the homepage, so the theme must refuse to activate there
    # rather than appear as a broken option in the theme picker.
    requires_plugins = ['booking_marketplace']
    # base.html calls `{% storefront_head %}` and emits no SEO markup of its own.
    head_contract = 1
    # The marketplace's vendors, in this store's words (see MorpheusTheme).
    vendor_noun = 'Host'
    vendor_noun_plural = 'Hosts'
    demo_topic = 'travel'
    # The booking app's regions, address country and page titles follow it.
    country = 'HR'

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'brand_name': {
                    'type': 'string',
                    'default': 'Croatia Experience',
                    'title': 'Brand name',
                },
                'tagline': {
                    'type': 'string',
                    'default': 'Unforgettable experiences along the Adriatic',
                    'title': 'Tagline (single line)',
                },
                'accent_color': {
                    'type': 'string',
                    'default': '#1a4f89',
                    'title': 'Primary accent (Adriatic blue)',
                },
                'accent_warm_color': {
                    'type': 'string',
                    'default': '#c7471f',
                    'title': 'Warm accent (terracotta CTA)',
                },
                'newsletter_pitch': {
                    'type': 'string',
                    'default': 'One letter a month. New experiences, hidden gems, no spam.',
                    'title': 'Newsletter pitch',
                },
            },
        }
