"""The storefront's own pages in the sitemap — listed by the owner, when they have content.

seo used to hardcode `/products/`, `/staff-picks/`, `/vendors/`, `/journal/`,
`/about/`, `/contact/`, `/shipping/` and `/returns/` on every store, whatever
they held. On the travel store `/products/` was an empty catalogue (its goods
are booking listings) sitting in the sitemap as a soft 404, and on a store
with no journal or no staff picks those were the same. Only the owner of a
route can answer "do I currently show anything here?", so the owner lists it.

`/categories/` is the vertical case of the same question: `book_product`
replaces categories with genres, so wherever that app is on the index is a
301 to `/genres/` and never belongs here.

Also here: `CMS_PAGE_PATH`, the storefront's claim on the CMS pages it renders
at routes of its own (/shipping/, /returns/), so each has one url.
"""

from __future__ import annotations

from urllib.parse import urljoin

from core.utils.site import site_base_url
from plugins.registry import app_registry

# CMS pages the storefront renders at its own route — slug → path.
CLAIMED_CMS_PAGES = {'shipping': '/shipping/', 'returns': '/returns/'}


def contribute_sitemap_urls(value, **kwargs):
    """SITEMAP_URLS subscriber — the storefront index and content pages that have content."""
    from plugins.installed.catalog.models import Category, Product
    from plugins.installed.catalog.vendors import listing_counts
    from plugins.installed.storefront.services import (
        journal_has_entries,
        staff_picks_collection,
        stocked_category_ids,
    )

    entries = list(value or [])
    base = site_base_url()

    def add(path: str, *, changefreq: str = 'weekly', priority: str = '0.7') -> None:
        entries.append({'loc': urljoin(base, path), 'changefreq': changefreq, 'priority': priority})

    if Product.objects.filter(status='active').exists():
        add('/products/')
    if not app_registry.is_active('book_product'):
        stocked = stocked_category_ids()
        top_level = Category.objects.filter(is_active=True, parent__isnull=True)
        if any(
            stocked & set(c.get_descendants(include_self=True).values_list('pk', flat=True))
            for c in top_level
        ):
            add('/categories/')
    picks = staff_picks_collection()
    if picks is not None and picks.products.filter(status='active').exists():
        add('/staff-picks/')
    if listing_counts():
        add('/vendors/')
    if journal_has_entries():
        add('/journal/')
    add('/about/')
    add('/contact/')
    # Policy pages — low priority, change rarely.
    add('/shipping/', changefreq='monthly', priority='0.4')
    add('/returns/', changefreq='monthly', priority='0.4')
    return entries


def claim_cms_page_path(value, page=None, **kwargs):
    """CMS_PAGE_PATH subscriber — the policy pages the storefront renders itself."""
    slug = getattr(page, 'slug', '') or ''
    return CLAIMED_CMS_PAGES.get(slug, value)
