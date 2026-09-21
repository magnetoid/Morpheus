"""SITEMAP_URLS filter subscriber.

Only one entry, and it is here rather than in seo's static list because it is
the one storefront route whose existence depends on another app: `book_product`
replaces categories with genres, so `/categories/` 301s to `/genres/` wherever
that vertical is installed. seo listed it unconditionally, so every book store
published a sitemap url that permanently redirects — and the Sep 2026 audit
found the same shape on a travel marketplace, where the redirect target was a
page titled "Genres" that was not in the sitemap at all.

The owner of the route is the only layer that can answer "do I serve this?".
"""

from __future__ import annotations

from urllib.parse import urljoin

from core.utils.site import site_base_url
from plugins.registry import app_registry


def contribute_sitemap_urls(value, **kwargs):
    """SITEMAP_URLS subscriber — adds `/categories/` when it renders a page."""
    entries = list(value or [])
    if app_registry.is_active('book_product'):
        return entries
    entries.append(
        {
            'loc': urljoin(site_base_url(), '/categories/'),
            'changefreq': 'weekly',
            'priority': '0.7',
        }
    )
    return entries
