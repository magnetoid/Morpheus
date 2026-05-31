"""Catalog search adapters.

Two backends:
  - ``typesense`` (preferred) — typo-tolerant, synonym-aware, ms-latency
    full-text search via the Typesense container. Activates when
    settings.TYPESENSE['host'] is set.
  - ``django`` (fallback) — Django `__icontains` over Product.name +
    book.author / book.publisher / book.isbn metafields. Always available.

The active backend is chosen by `get_backend()`; callers should always
use `search(q, **opts)` from this package so the fallback is automatic
if Typesense is unreachable.
"""

from plugins.installed.catalog.search.dispatcher import get_backend, search

__all__ = ['get_backend', 'search']
