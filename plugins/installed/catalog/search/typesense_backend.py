"""Typesense adapter — typo-tolerant search via the Typesense container.

Activation:
  settings.TYPESENSE = {
      'host': '...',           # e.g. 'typesense.internal'
      'port': 8108,
      'protocol': 'http',
      'api_key': '<xyz>',
      'collection': 'products', # optional, default 'products'
  }

Schema (fields registered on the collection at index time):
  id            string  primary
  name          string  (sort, search)
  sku           string  (search)
  slug          string  (filter)
  description   string  (search)
  author        string  (search, optional metafield)
  publisher     string  (search, optional metafield)
  isbn          string  (search, optional metafield)
  category      string  (facet)
  vendor        string  (facet)
  price         float   (sort, range)
  status        string  (filter)
  in_stock      bool    (filter)
  created_at    int64   (sort)

Search options (mirror the dispatcher signature):
  - filter_by: Typesense filter expression, e.g. 'in_stock:=true'.
  - sort_by:   Typesense sort expression, e.g. 'price:asc'.

Typo tolerance: `num_typos=2` (default; tolerates 2 character edits
on terms ≥ 4 chars). Synonyms can be added by merchant via the
catalog dashboard once the Phase 2 admin UI lands.
"""

from __future__ import annotations

import logging
from contextlib import suppress
from typing import Any

from django.conf import settings

from plugins.installed.catalog.search.dispatcher import SearchResult

logger = logging.getLogger('morpheus.catalog.search.typesense')

DEFAULT_COLLECTION = 'products'

# Fields searched (in order — first match wins on tie-break).
QUERY_BY = 'name,author,publisher,sku,isbn,description'
# Per-field weights (parallel to QUERY_BY) — higher = higher score.
QUERY_BY_WEIGHTS = '6,5,4,3,3,1'


def run(
    q: str,
    *,
    page: int = 1,
    per_page: int = 24,
    filter_by: str = '',
    sort_by: str = '',
) -> SearchResult:
    """Search the Typesense collection. Raises on failure (the
    dispatcher catches + falls back to Django).
    """
    client = _client()
    coll = _collection_name()
    params: dict[str, Any] = {
        'q': q,
        'query_by': QUERY_BY,
        'query_by_weights': QUERY_BY_WEIGHTS,
        'page': max(1, page),
        'per_page': max(1, min(50, per_page)),
        'num_typos': 2,
        'prefix': 'true',
        'highlight_full_fields': 'name',
        'snippet_threshold': 30,
        'facet_by': 'category,vendor',
    }
    if filter_by:
        params['filter_by'] = filter_by
    if sort_by:
        params['sort_by'] = sort_by

    response = client.collections[coll].documents.search(params)
    hits = response.get('hits', []) or []
    product_ids = [h['document'].get('id') for h in hits if h.get('document')]
    facets = {
        f.get('field_name'): {c.get('value'): c.get('count') for c in (f.get('counts') or [])}
        for f in response.get('facet_counts', []) or []
    }
    return SearchResult(
        product_ids=product_ids,
        total=int(response.get('found', 0)),
        backend='typesense',
        facets=facets,
        typo_corrected_query=str(response.get('request_params', {}).get('q', q)),
    )


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------


def ensure_collection() -> None:
    """Idempotent. Creates the collection on first run; no-ops thereafter."""
    client = _client()
    coll = _collection_name()
    with suppress(Exception):
        # Already exists → retrieve() succeeds → skip.
        client.collections[coll].retrieve()
        return
    schema = {
        'name': coll,
        'fields': [
            {'name': 'id', 'type': 'string'},
            {'name': 'name', 'type': 'string', 'sort': True},
            {'name': 'sku', 'type': 'string', 'optional': True},
            {'name': 'slug', 'type': 'string', 'facet': False},
            {'name': 'description', 'type': 'string', 'optional': True},
            {'name': 'author', 'type': 'string', 'optional': True},
            {'name': 'publisher', 'type': 'string', 'optional': True},
            {'name': 'isbn', 'type': 'string', 'optional': True},
            {'name': 'category', 'type': 'string', 'facet': True, 'optional': True},
            {'name': 'vendor', 'type': 'string', 'facet': True, 'optional': True},
            {'name': 'price', 'type': 'float', 'optional': True},
            {'name': 'status', 'type': 'string', 'facet': True, 'optional': True},
            {'name': 'in_stock', 'type': 'bool', 'optional': True},
            {'name': 'created_at', 'type': 'int64', 'optional': True},
        ],
        'default_sorting_field': 'created_at',
    }
    client.collections.create(schema)


def upsert_product(product) -> None:
    """Mirror one Product into Typesense. Called from PRODUCT_CREATED/
    PRODUCT_UPDATED hook subscribers."""
    if not _is_active():
        return
    try:
        client = _client()
        coll = _collection_name()
        doc = _serialize(product)
        client.collections[coll].documents.upsert(doc)
    except Exception:  # noqa: BLE001
        logger.exception('typesense upsert failed for product=%s', getattr(product, 'pk', '?'))


def delete_product(product_id: str) -> None:
    if not _is_active():
        return
    try:
        client = _client()
        coll = _collection_name()
        client.collections[coll].documents[str(product_id)].delete()
    except Exception:  # noqa: BLE001
        logger.exception('typesense delete failed for product=%s', product_id)


def reindex_all(batch_size: int = 500) -> dict:
    """Full reindex — drop + recreate the collection, batch-insert all
    active products. Returns counts for the Celery task log."""
    if not _is_active():
        return {'skipped': True}

    from plugins.installed.catalog.models import Product  # noqa: PLC0415

    client = _client()
    coll = _collection_name()
    # Drop + recreate to guarantee a clean schema.
    with suppress(Exception):
        client.collections[coll].delete()
    ensure_collection()

    indexed = 0
    qs = Product.objects.filter(status='active').iterator(chunk_size=batch_size)
    batch: list[dict[str, Any]] = []
    for p in qs:
        batch.append(_serialize(p))
        if len(batch) >= batch_size:
            client.collections[coll].documents.import_(batch, {'action': 'upsert'})
            indexed += len(batch)
            batch = []
    if batch:
        client.collections[coll].documents.import_(batch, {'action': 'upsert'})
        indexed += len(batch)
    logger.info('typesense reindex complete: %s products', indexed)
    return {'indexed': indexed}


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _serialize(product) -> dict:
    """Project one Product → Typesense document shape."""
    doc: dict[str, Any] = {
        'id': str(product.pk),
        'name': str(getattr(product, 'name', '') or '')[:300],
        'sku': str(getattr(product, 'sku', '') or '')[:80],
        'slug': str(getattr(product, 'slug', '') or '')[:200],
        'description': str(getattr(product, 'description', '') or '')[:2000],
        'category': str(getattr(getattr(product, 'category', None), 'name', '') or '')[:100],
        'vendor': str(getattr(getattr(product, 'vendor', None), 'name', '') or '')[:100],
        'status': str(getattr(product, 'status', '') or ''),
        'created_at': int(product.created_at.timestamp())
        if getattr(product, 'created_at', None)
        else 0,
    }
    price = getattr(product, 'price', None)
    if price is not None:
        with suppress(Exception):
            doc['price'] = float(getattr(price, 'amount', price))
    with suppress(Exception):
        from plugins.installed.book_product.compat import book_attrs  # noqa: PLC0415

        attrs = book_attrs(product)  # model-first, legacy book.* fallback
        for key in ('author', 'publisher', 'isbn'):
            if attrs.get(key):
                doc[key] = str(attrs[key])[:300]
    return doc


def _client():
    import typesense  # noqa: PLC0415

    cfg = settings.TYPESENSE or {}
    return typesense.Client(
        {
            'api_key': cfg['api_key'],
            'nodes': [
                {
                    'host': cfg['host'],
                    'port': str(cfg.get('port', 8108)),
                    'protocol': cfg.get('protocol', 'http'),
                }
            ],
            'connection_timeout_seconds': cfg.get('timeout_seconds', 2),
        }
    )


def _collection_name() -> str:
    cfg = getattr(settings, 'TYPESENSE', None) or {}
    return cfg.get('collection') or DEFAULT_COLLECTION


def _is_active() -> bool:
    cfg = getattr(settings, 'TYPESENSE', None) or {}
    if not cfg.get('host'):
        return False
    try:
        import typesense  # noqa: F401, PLC0415
    except ImportError:
        return False
    return True
