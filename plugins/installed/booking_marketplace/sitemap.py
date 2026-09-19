"""SITEMAP_URLS filter subscriber.

Folds this plugin's own routes — experiences, places, stays, and the three
list pages — into the seo plugin's sitemap via `core.hooks`, so seo never
has to import `plugins.installed.booking_marketplace` to know these URLs
exist (CLAUDE.md: cross-plugin flows go through the hook bus only).
Registered in `plugin.py:ready()` with `plugin='booking_marketplace'`
ownership, so the bus skips it for free while this plugin is disabled.

None of the models here carry an `updated_at` field (only `created_at`), so
every contributed entry's `lastmod` is `None` — nothing to report.
"""

from __future__ import annotations

from urllib.parse import urljoin

from core.utils.site import site_base_url


def contribute_sitemap_urls(value, **kwargs):
    """SITEMAP_URLS subscriber — appends active rows + list pages to
    `value` (the sitemap's running URL list so far) and returns it."""
    from plugins.installed.booking_marketplace.models import BookableService, Event, Place, Property

    base = site_base_url()
    entries = list(value or [])

    for path in ('/bookings/', '/places/', '/hotels/', '/events/'):
        entries.append({'loc': urljoin(base, path), 'changefreq': 'weekly', 'priority': '0.7'})

    for svc in BookableService.objects.filter(is_active=True, vendor__is_active=True).only('slug'):
        entries.append(
            {
                'loc': urljoin(base, f'/bookings/{svc.slug}/'),
                'lastmod': None,
                'changefreq': 'weekly',
                'priority': '0.7',
            }
        )

    for place in Place.objects.filter(is_active=True).only('slug'):
        entries.append(
            {
                'loc': urljoin(base, f'/places/{place.slug}/'),
                'lastmod': None,
                'changefreq': 'monthly',
                'priority': '0.6',
            }
        )

    for prop in Property.objects.filter(is_active=True, vendor__is_active=True).only('slug'):
        entries.append(
            {
                'loc': urljoin(base, f'/hotels/{prop.slug}/'),
                'lastmod': None,
                'changefreq': 'weekly',
                'priority': '0.7',
            }
        )

    for event in Event.objects.filter(is_active=True).only('slug'):
        entries.append(
            {
                'loc': urljoin(base, f'/events/{event.slug}/'),
                'lastmod': None,
                'changefreq': 'monthly',
                'priority': '0.6',
            }
        )

    return entries
