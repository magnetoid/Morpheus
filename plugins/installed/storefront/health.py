"""Storefront's contribution to the nightly health check (``HEALTH_CHECKS``)."""

from __future__ import annotations


def public_pages_check() -> dict:
    """The pages a purchase goes through load for a visitor."""
    from core.errors.health import fetch_failures
    from plugins.installed.catalog.models import Product

    paths = ['/', '/cart/', '/checkout/quick/']
    slug = (
        Product.objects.filter(status='active', price__gt=0)
        .order_by('pk')
        .values_list('slug', flat=True)
        .first()
    )
    if slug:
        paths.insert(1, f'/products/{slug}/')
    failures = fetch_failures(paths)
    return {'name': 'Shop pages load', 'ok': not failures, 'detail': '; '.join(failures)}
