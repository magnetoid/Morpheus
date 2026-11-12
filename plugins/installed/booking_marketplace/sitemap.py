"""SITEMAP_URLS filter subscriber.

Folds this plugin's own routes — experiences, places, stays, events, regions,
the shop and their list pages — into the seo plugin's sitemap via `core.hooks`,
so seo never has to import `plugins.installed.booking_marketplace` to know these
URLs exist (CLAUDE.md: cross-plugin flows go through the hook bus only).
Registered in `app.py:ready()` with `plugin='booking_marketplace'` ownership, so
the bus skips it for free while this plugin is disabled.

A list page is listed only when it has something on it — an empty one answers
200 with "nothing here", a soft 404 the sitemap would be inviting crawlers to.
The rows obey the same rule as the detail views: an inactive host's listings
404, so they are never here either. `/shop/` and the region pages were missing
altogether, although the nav links both. A region × category page
(`/regions/<key>/<category>/`, v0.161.0) is listed when an experience is on it.

None of the models here carry an `updated_at` field (only `created_at`), so
every contributed entry's `lastmod` is `None` — nothing to report.
"""

from __future__ import annotations

from urllib.parse import urljoin

from core.utils.site import site_base_url


def contribute_sitemap_urls(value, **kwargs):
    """SITEMAP_URLS subscriber — appends active rows + non-empty list pages to
    `value` (the sitemap's running URL list so far) and returns it."""
    from django.db.models import Count

    from plugins.installed.booking_marketplace.country import regions
    from plugins.installed.booking_marketplace.models import (
        BookableService,
        Event,
        Place,
        Property,
    )

    base = site_base_url()
    entries = list(value or [])

    def add(path: str, *, changefreq: str = 'weekly', priority: str = '0.7') -> None:
        entries.append(
            {
                'loc': urljoin(base, path),
                'lastmod': None,
                'changefreq': changefreq,
                'priority': priority,
            }
        )

    live = BookableService.objects.filter(is_active=True, vendor__is_active=True)
    experiences = live.filter(listing_kind='experience')
    goods = live.filter(listing_kind='product')
    stays = Property.objects.filter(is_active=True, vendor__is_active=True)
    places = Place.objects.filter(is_active=True)
    events = Event.objects.filter(is_active=True)

    for path, rows in (
        ('/bookings/', experiences),
        ('/shop/', goods),
        ('/places/', places),
        ('/hotels/', stays),
        ('/events/', events),
    ):
        if rows.exists():
            add(path)

    known = {key for key, _label in regions()}
    stocked_regions = [
        row['region']
        for row in live.exclude(region='').values('region').annotate(n=Count('pk'))
        if row['n'] and row['region'] in known
    ]
    if stocked_regions:
        add('/regions/')
    for region in sorted(stocked_regions):
        add(f'/regions/{region}/', priority='0.6')
    # Each region × category landing page with a live experience on it, never an
    # empty one (landing.category_counts counts what the page lists).
    from plugins.installed.booking_marketplace.landing import category_counts

    for region, rows in sorted(category_counts().items()):
        for category, _count in rows:
            add(f'/regions/{region}/{category.slug}/', priority='0.5')

    for svc in live.only('slug'):
        add(f'/bookings/{svc.slug}/')
    for place in places.only('slug'):
        add(f'/places/{place.slug}/', changefreq='monthly', priority='0.6')
    for prop in stays.only('slug'):
        add(f'/hotels/{prop.slug}/')
    for event in events.only('slug'):
        add(f'/events/{event.slug}/', changefreq='monthly', priority='0.6')
    return entries
