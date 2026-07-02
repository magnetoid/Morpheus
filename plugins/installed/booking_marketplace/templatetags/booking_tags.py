"""Template tags for surfacing bookable listings on theme pages (e.g. a homepage).

Lets a theme feature real BookableService listings without the home view needing
to know about this plugin. Brand-neutral — no deployment-specific content.
"""

from __future__ import annotations

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
    """Destinations for a homepage strip — featured first, then sort order."""
    from plugins.installed.booking_marketplace.models import Place

    return list(
        Place.objects.filter(is_active=True).order_by('-is_featured', 'sort_order', 'name')[
            : int(limit)
        ]
    )


@register.simple_tag
def booking_listing_mode():
    """Listing-mode flag, for templates that branch on price visibility."""
    return getattr(settings, 'BOOKING_LISTING_MODE', True)


@register.simple_tag
def booking_regions():
    """Configured region options (key + label) for a 'Where' dropdown.

    Empty unless the deployment sets BOOKING_REGIONS (see models.REGIONS)."""
    from plugins.installed.booking_marketplace.models import REGIONS

    return [{"key": k, "label": l} for k, l in REGIONS]


@register.filter
def dictkey(d, key):
    """Look up d[key] with a variable key (templates can't do d[var])."""
    try:
        return d.get(key, '')
    except AttributeError:
        return ''
