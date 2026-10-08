"""Public listings per vendor — the one number the directory and the sitemap share.

A vendor page that lists nothing is a soft 404: a 200 that says "0 listings".
The travel store had 171 of them in its sitemap, because every host's
experiences and stays live in booking_marketplace while the vendor page, the
directory and the sitemap all counted catalog Products only. Counting in three
places is how they drifted; this is the one place, and an app whose listings are
not Products adds its own through `VENDOR_LISTING_COUNTS`.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.catalog')


def listing_counts() -> dict[str, int]:
    """`{str(vendor_pk): count}` for every active vendor with something to show."""
    from django.db.models import Count, Q

    from core.hooks import MorpheusEvents, hook_registry
    from plugins.installed.catalog.models import Vendor

    active = Vendor.objects.filter(is_active=True)
    counts = {
        str(pk): n
        for pk, n in active.annotate(n=Count('products', filter=Q(products__status='active')))
        .filter(n__gt=0)
        .values_list('pk', 'n')
    }
    try:
        contributed = hook_registry.filter(MorpheusEvents.VENDOR_LISTING_COUNTS, dict(counts))
    except Exception as e:  # noqa: BLE001 — a broken contributor must not empty the directory
        logger.warning('catalog: VENDOR_LISTING_COUNTS failed: %s', e, exc_info=True)
        return counts
    if not isinstance(contributed, dict):
        return counts
    # A contributor may only count vendors the storefront actually serves.
    live = {str(pk) for pk in active.values_list('pk', flat=True)}
    out: dict[str, int] = {}
    for key, value in contributed.items():
        if (
            str(key) in live
            and isinstance(value, int)
            and not isinstance(value, bool)
            and value > 0
        ):
            out[str(key)] = value
    return out
