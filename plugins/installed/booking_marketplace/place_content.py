"""Presentation helpers for Place detail pages.

`good_for` is a list of free-form audience tags ("couples", "hikers",
"wine lovers", …). To render the "Ideal for" block as a proper icon-card
grid (instead of bare text pills), we resolve each tag to a lucide-style
line icon by keyword, falling back to a star. Pure/stateless so it is
trivially unit-testable and safe to call per-request.
"""

from __future__ import annotations

# inner SVG markup for a 24×24 stroke icon (wrapped in <svg> by the template)
_ICON_SVG = {
    'heart': '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
    'camera': '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3Z"/><circle cx="12" cy="13" r="3"/>',
    'users': '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    'compass': '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
    'snow': '<path d="M2 12h20M12 2v20m7.4-16L4.6 18M19.4 18 4.6 6"/>',
    'waves': '<path d="M2 6c.6.5 1.2 1 2.5 1C7 7 7 5 9.5 5s2.4 2 5 2 2.5-2 5-2c1.3 0 1.9.5 2.5 1M2 12c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2s2.4 2 5 2 2.5-2 5-2c1.3 0 1.9.5 2.5 1M2 18c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2s2.4 2 5 2 2.5-2 5-2c1.3 0 1.9.5 2.5 1"/>',
    'anchor': '<circle cx="12" cy="5" r="3"/><path d="M12 22V8M5 12H2a10 10 0 0 0 20 0h-3"/>',
    'moon': '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    'utensils': '<path d="M3 2v7c0 1.1.9 2 2 2h1v11M7 2v20M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Z"/>',
    'wine': '<path d="M8 22h8M7 10h10M12 15v7M17 2H7l1 8a4 4 0 0 0 8 0l1-8Z"/>',
    'landmark': '<path d="M3 22h18M6 18v-7M10 18v-7M14 18v-7M18 18v-7M12 2 2 8h20Z"/>',
    'leaf': '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6"/>',
    'gem': '<path d="M6 3h12l4 6-10 13L2 9Z"/><path d="M11 3 8 9l4 13 4-13-3-6M2 9h20"/>',
    'wallet': '<path d="M19 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H5a2 2 0 0 1-2-2V5"/><path d="M16 12h.01"/>',
    'star': '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>',
}

# (keyword needles) → icon key; first match wins, so order narrow→broad.
_MATCH = [
    (('honeymoon', 'luxury', 'upscale'), 'gem'),
    (('couple', 'romantic'), 'heart'),
    (('photograph', 'photo'), 'camera'),
    (('family', 'families', 'kid'), 'users'),
    (('group', 'friends'), 'users'),
    (('ski', 'snow', 'winter'), 'snow'),
    (('hike', 'hiking', 'trek', 'adventure', 'walk', 'off-the-beaten'), 'compass'),
    (('beach', 'swim', 'sun', 'first-time'), 'waves'),
    (('sail', 'boat', 'ferry', 'kayak', 'day-trip'), 'anchor'),
    (('nightlife', 'party', 'night'), 'moon'),
    (('wine',), 'wine'),
    (('food', 'foodie', 'cuisine', 'gastro'), 'utensils'),
    (('history', 'culture', 'museum', 'heritage', 'archae'), 'landmark'),
    (('nature', 'bird', 'wildlife', 'garden', 'eco', 'slow'), 'leaf'),
    (('budget', 'cheap', 'value'), 'wallet'),
]


def _icon_key_for(label: str) -> str:
    low = label.lower()
    for needles, key in _MATCH:
        if any(n in low for n in needles):
            return key
    return 'star'


def good_for_cards(good_for) -> list:
    """[{'label': 'Couples', 'icon': '<path .../>'}] for the Ideal-for grid.

    Labels are title-cased for display; the raw tag drives icon selection.
    """
    cards = []
    for raw in good_for or []:
        label = str(raw).strip()
        if not label:
            continue
        cards.append(
            {
                'label': label[:1].upper() + label[1:],
                'icon': _ICON_SVG[_icon_key_for(label)],
            }
        )
    return cards
