"""The resolved identity of a storefront page.

The dataclass and its kind constants moved to `core.seo_page` in v0.47: an app
that owns a URL family answers `SEO_RESOLVE_PAGE` by building one, and it must
be able to do that without importing this app. Re-exported here so the seo
app's own modules keep their short, local import.
"""

from __future__ import annotations

from core.seo_page import (
    KIND_ARTICLE,
    KIND_HOME,
    KIND_LISTING,
    KIND_PAGE,
    KIND_PRIVATE,
    KIND_PRODUCT,
    KIND_SEARCH,
    KIND_STATIC,
    SeoPage,
)

__all__ = [
    'KIND_ARTICLE',
    'KIND_HOME',
    'KIND_LISTING',
    'KIND_PAGE',
    'KIND_PRIVATE',
    'KIND_PRODUCT',
    'KIND_SEARCH',
    'KIND_STATIC',
    'SeoPage',
]
