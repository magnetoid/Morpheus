"""Template tags for surfacing experiences on theme pages (e.g. the homepage).

Lets a theme feature real BookableService experiences without the storefront
home view needing to know about this plugin.
"""

from __future__ import annotations

from urllib.parse import quote

from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def featured_experiences(limit=8):
    """Top active experiences — bestsellers first, then by rating / reviews."""
    from plugins.installed.booking_marketplace.models import BookableService

    return list(
        BookableService.objects.filter(
            is_active=True, vendor__is_active=True, listing_kind='experience'
        )
        .select_related('vendor')
        .order_by('-is_bestseller', '-rating', '-review_count')[: int(limit)]
    )


@register.simple_tag
def featured_places(limit=6):
    """Destinations for the homepage strip — featured first, then sort order."""
    from plugins.installed.booking_marketplace.models import Place

    return list(
        Place.objects.filter(is_active=True).order_by('-is_featured', 'sort_order', 'name')[
            : int(limit)
        ]
    )


@register.simple_tag
def booking_listing_mode():
    """Enquiry mode flag (opt-in), for templates that branch on price visibility."""
    return getattr(settings, 'BOOKING_LISTING_MODE', False)


@register.simple_tag
def booking_enquiry_only():
    """Whether a submit captures an enquiry rather than confirming a booking.

    Distinct from `booking_listing_mode`, which is only about price visibility.
    A CTA must read from THIS tag: while nothing charges, "Book now" promises a
    confirmed reservation the submit does not create.
    """
    from plugins.installed.booking_marketplace.views import takes_enquiry_only

    return takes_enquiry_only()


@register.filter
def dictkey(d, key):
    """Look up d[key] with a variable key (templates can't do d[var])."""
    try:
        return d.get(key, '')
    except AttributeError:
        return ''


# --- Homepage content tags — derived live from the catalog (no hardcoded lists) ---

# Category icons are presentation, keyed by slugified name; unmapped
# categories get the compass. Adding a category in the dashboard therefore
# needs no code change to appear on the storefront.
_CAT_ICON_ATTRS = (
    'class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
)
_CAT_ICONS = {
    'adventure': f'<svg {_CAT_ICON_ATTRS}><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>',
    'wellness': f'<svg {_CAT_ICON_ATTRS}><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></svg>',
    'dining': f'<svg {_CAT_ICON_ATTRS}><path d="M3 2v7c0 1.1.9 2 2 2h0a2 2 0 0 0 2-2V2M5 2v20M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/></svg>',
    'water-sports': f'<svg {_CAT_ICON_ATTRS}><path d="M22 18H2a4 4 0 0 0 4 4h12a4 4 0 0 0 4-4Z"/><path d="M21 14 10 2 3 14h18Z"/><path d="M10 2v16"/></svg>',
    'culture': f'<svg {_CAT_ICON_ATTRS}><line x1="3" x2="21" y1="22" y2="22"/><line x1="6" x2="6" y1="18" y2="11"/><line x1="10" x2="10" y1="18" y2="11"/><line x1="14" x2="14" y1="18" y2="11"/><line x1="18" x2="18" y1="18" y2="11"/><polygon points="12 2 20 7 4 7"/></svg>',
    'wine': f'<svg {_CAT_ICON_ATTRS}><path d="M8 22h8M7 10h10M12 15v7M12 15a5 5 0 0 0 5-5c0-2-.5-4-1-8H8c-.5 4-1 6-1 8a5 5 0 0 0 5 5Z"/></svg>',
    'books': f'<svg {_CAT_ICON_ATTRS}><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/></svg>',
}
_CAT_ICON_DEFAULT = f'<svg {_CAT_ICON_ATTRS}><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>'


def _cat_href(name):
    return f'/bookings/?category={quote(name)}'


@register.simple_tag
def booking_categories():
    """Live categories (name + count) — the single category source."""
    from plugins.installed.booking_marketplace.services import active_categories

    return active_categories()


@register.simple_tag
def hero_pills():
    """Quick-pills under the hero search — top categories by inventory."""
    from plugins.installed.booking_marketplace.services import active_categories

    return [c['name'] for c in active_categories()[:4]]


@register.simple_tag
def featured_filters():
    """Filter chips above the featured grid — every live category."""
    from plugins.installed.booking_marketplace.services import active_categories

    return [c['name'] for c in active_categories()]


@register.simple_tag
def home_categories():
    """Category band tiles: label + glyph + live count + filtered link."""
    from django.utils.text import slugify

    from plugins.installed.booking_marketplace.services import active_categories

    return [
        {
            'label': c['name'],
            'icon': _CAT_ICONS.get(slugify(c['name']), _CAT_ICON_DEFAULT),
            'count': c['count'],
            'href': _cat_href(c['name']),
        }
        for c in active_categories()
    ]


@register.simple_tag
def booking_regions():
    """Region options for the hero 'Where' dropdown (key + label)."""
    from plugins.installed.booking_marketplace.models import REGIONS

    return [{'key': k, 'label': l} for k, l in REGIONS]


@register.simple_tag
def home_testimonials():
    """Real guest reviews (rating ≥4 with body text), newest first."""
    from plugins.installed.booking_marketplace.models import ServiceReview

    try:
        rows = (
            ServiceReview.objects.filter(rating__gte=4)
            .exclude(body='')
            .select_related('service')
            .order_by('-created_at')[:4]
        )
        return [
            {
                'name': r.author_name or 'Guest',
                'avatar': (r.author_name or 'G')[0].upper(),
                'text': r.body,
                'experience': r.service.name,
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001
        return []
