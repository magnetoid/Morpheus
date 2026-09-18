"""Per-product markdown + AI shopping feed for LLM crawlers.

``render_product_markdown`` is served at ``/md/products/<slug>`` so
LLMs (Anthropic, OpenAI, Perplexity) can fetch a stable plain-text
rendering of any product without parsing HTML.

``render_ai_products_feed`` wraps every product's :func:`product_jsonld`
into a single ``ItemList`` for AI shopping crawlers (Google AI Shopping,
Perplexity, etc.).
"""
# Lazy (in-function) imports + fail-soft feed builders are the pattern here.
# ruff: noqa: PLC0415, S110

from __future__ import annotations

import logging

from core.hooks import MorpheusEvents, hook_registry
from core.utils.site import store_name

from ._helpers import _site_base_url, site_settings
from .jsonld import product_jsonld

logger = logging.getLogger('morpheus.seo')


def render_product_markdown(product) -> str:
    """Canonical markdown rendering of a product for LLM crawlers.

    Output is plain text — no HTML, no menu, no boilerplate. Stable
    structure so crawlers can rely on the heading shape across pages.
    Sections (each separated by a blank line):
        # Title
        > Short description
        Price · availability
        ## About
        long description
        ## Specifications
        - key: value
        ## Reviews (top 5)
    """
    parts: list[str] = []
    name = getattr(product, 'name', '') or ''
    parts.append(f'# {name}')
    short = (getattr(product, 'short_description', '') or '').strip()
    if short:
        parts.extend(['', f'> {short}'])
    # Price + availability.
    price = getattr(product, 'price', None)
    if price is not None:
        try:
            amount = price.amount
            currency = str(price.currency)
            avail = (
                'in stock'
                if not getattr(product, 'track_inventory', False)
                else (
                    'in stock'
                    if (getattr(product, 'stock_quantity', None) or 1) > 0
                    else 'out of stock'
                )
            )
            parts.extend(['', f'Price: {amount} {currency} · {avail}'])
        except Exception:  # noqa: BLE001
            pass
    desc = (getattr(product, 'description', '') or '').strip()
    if desc:
        # Strip HTML if any — naive but adequate for the editorial copy
        # this storefront stores in `description`.
        import re as _re

        plain = _re.sub(r'<[^>]+>', '', desc)
        parts.extend(['', '## About', plain])
    # Book-shop specifics — pull metafields if the catalog uses them.
    try:
        from plugins.installed.book_product.compat import book_attrs

        attrs = book_attrs(product)  # model-first, legacy book.* fallback
        if attrs:
            parts.append('')
            parts.append('## Specifications')
            for k, v in attrs.items():
                parts.append(f'- {k}: {v}')
    except Exception:  # noqa: BLE001
        pass
    # Reviews (top 5 published).
    try:
        from plugins.installed.catalog.models import Review

        revs = list(
            Review.objects.filter(product=product, status='published')
            .order_by('-created_at')[:5]
            .values('rating', 'title', 'body', 'created_at')
        )
        if revs:
            parts.append('')
            parts.append('## Reviews')
            for r in revs:
                parts.append(f'### {r.get("title") or "(untitled)"} — {r["rating"]}/5')
                parts.append((r.get('body') or '').strip())
    except Exception:  # noqa: BLE001
        pass
    return '\n'.join(parts) + '\n'


def render_ai_products_feed(*, limit: int = 1000, offset: int = 0) -> dict:
    """Schema.org Product feed for AI shopping crawlers.

    Returns a dict that the view JSON-encodes. Each entry is a full
    Product JSON-LD object plus an `agent_metadata` block for any
    structured fields the merchant set on the Product.

    ``limit`` caps the number of items in one response (per-request);
    ``offset`` lets crawlers walk past the cap via ``nextPage``. The
    top-level ``numberOfItems`` reports the total queryset size so
    crawlers know when they've reached the tail.
    """
    limit = max(1, min(int(limit), 1000))
    offset = max(0, int(offset))
    out = {
        '@context': 'https://schema.org',
        '@type': 'ItemList',
        # The merchant's brand, never the engine's name — an AI crawler
        # reads this as who the shop IS.
        'name': site_settings().organization_name or store_name() or 'Product feed',
        'numberOfItems': 0,
        'itemListElement': [],
    }
    items: list[dict] = []
    catalog_total = 0
    try:
        from plugins.installed.catalog.models import Product

        qs = Product.objects.filter(status='active').order_by('-created_at')
        catalog_total = qs.count()
        items = [product_jsonld(p) for p in qs[offset : offset + limit]]
    except Exception:  # noqa: BLE001
        pass

    # A store whose inventory is not a catalog Product (bookings, stays,
    # tickets) folds its own schema.org objects in here — otherwise the feed
    # truthfully reports an empty shop to every AI crawler. Contributed items
    # sit AFTER the catalog rows and share the same window, so paging stays
    # consistent across the combined sequence.
    contributed: list[dict] = []
    try:
        contributed = hook_registry.filter(MorpheusEvents.AI_FEED_ITEMS, []) or []
    except Exception:  # noqa: BLE001 — a bad subscriber must not empty the feed
        logger.warning('ai_feed: AI_FEED_ITEMS subscriber failed', exc_info=True)

    if contributed:
        # Window the contributed tail by whatever the catalog page left free.
        start = max(0, offset - catalog_total)
        items.extend(contributed[start : start + (limit - len(items))])

    total = catalog_total + len(contributed)
    out['numberOfItems'] = total
    out['itemListElement'] = [
        {'@type': 'ListItem', 'position': offset + i + 1, 'item': item}
        for i, item in enumerate(items)
    ]
    if (offset + limit) < total:
        base = _site_base_url().rstrip('/')
        next_offset = offset + limit
        out['nextPage'] = f'{base}/ai/products.json?offset={next_offset}&limit={limit}'
    return out
