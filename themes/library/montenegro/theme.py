"""
montenegro — the Adriatic experience marketplace theme.

Design notes
------------
- Sea-tinted near-white background with deep teal-ink text.
- Deep Adriatic teal (#19726a) is the primary brand / CTA colour; a warm
  sandstone (#ee7d23) handles urgency / secondary CTAs.
- Headlines in an editorial serif (Playfair Display). Body in Inter.
- Soft, rounded cards (0.75rem) with sea-tinted shadows — an Airbnb-style
  travel marketplace feel rather than a retail grid.
- Ported from the montenegro-experience-hub "Adriatic Design System".
- Built on the Morpheus storefront views, so all data flows through
  GraphQL (`api.client.internal_graphql`) — see LAW 3.

Derived from the dot_books theme (shares its template structure + slots);
only the design tokens, typography and branding differ. Keeping the same
template paths means upstream Morpheus storefront updates keep working.
"""

from __future__ import annotations

from themes.base import MorpheusTheme


class MontenegroTheme(MorpheusTheme):
    name = 'montenegro'
    label = 'Montenegro Experience — Adriatic marketplace'
    version = '0.1.0'
    description = (
        'Premium Mediterranean travel marketplace theme. Sea-tinted paper, '
        'deep Adriatic teal, warm sandstone accent, editorial serif headlines.'
    )
    author = 'Montenegro Experience'
    supports_plugins = ['storefront', 'catalog', 'orders', 'marketplace', 'booking_marketplace']
    # The homepage loads `{% load booking_tags %}` and calls six tags that only
    # exist in the booking_marketplace vertical app. A store without that app
    # would 500 on the homepage, so the theme must refuse to activate there
    # rather than appear as a broken option in the theme picker.
    requires_plugins = ['booking_marketplace']
    demo_topic = 'travel'

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'brand_name': {
                    'type': 'string',
                    'default': 'Montenegro Experience',
                    'title': 'Brand name',
                },
                'tagline': {
                    'type': 'string',
                    'default': 'Unforgettable experiences along the Adriatic',
                    'title': 'Tagline (single line)',
                },
                'accent_color': {
                    'type': 'string',
                    'default': '#19726a',
                    'title': 'Primary accent (Adriatic teal)',
                },
                'accent_warm_color': {
                    'type': 'string',
                    'default': '#ee7d23',
                    'title': 'Warm accent (sandstone CTA)',
                },
                'newsletter_pitch': {
                    'type': 'string',
                    'default': 'One letter a month. New experiences, hidden gems, no spam.',
                    'title': 'Newsletter pitch',
                },
            },
        }
