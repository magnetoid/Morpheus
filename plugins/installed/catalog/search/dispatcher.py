"""Backend selection + unified search() entry point.

Search is called from views, GraphQL resolvers, and the storefront
template. All of them go through `search(q, ...)` here so the Typesense
→ Django fallback is centralised.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.conf import settings

logger = logging.getLogger('morpheus.catalog.search')


@dataclass(slots=True)
class SearchResult:
    """Backend-agnostic shape."""

    product_ids: list = field(default_factory=list)
    total: int = 0
    backend: str = 'django'
    facets: dict = field(default_factory=dict)
    typo_corrected_query: str = ''


def get_backend() -> str:
    """Return the active backend name."""
    cfg = getattr(settings, 'TYPESENSE', None) or {}
    if not cfg.get('host'):
        return 'django'
    try:
        import typesense  # noqa: F401, PLC0415
    except ImportError:
        return 'django'
    return 'typesense'


def search(
    q: str,
    *,
    page: int = 1,
    per_page: int = 24,
    filter_by: str = '',
    sort_by: str = '',
) -> SearchResult:
    """Run a search via the active backend. Falls back to Django on any
    Typesense error so the storefront never goes dark on a search outage.
    """
    q = (q or '').strip()
    if not q:
        return SearchResult(backend=get_backend())

    if get_backend() == 'typesense':
        try:
            from plugins.installed.catalog.search.typesense_backend import (  # noqa: PLC0415
                run as ts_run,
            )

            return ts_run(q, page=page, per_page=per_page, filter_by=filter_by, sort_by=sort_by)
        except Exception:  # noqa: BLE001 — never lose search on adapter failure
            logger.exception('catalog.search: typesense failed, falling back to django')

    from plugins.installed.catalog.search.django_backend import (  # noqa: PLC0415
        run as dj_run,
    )

    return dj_run(q, page=page, per_page=per_page)
