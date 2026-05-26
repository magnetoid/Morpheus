"""Per-product markdown + AI shopping feed for LLM crawlers.

``render_product_markdown`` is served at ``/md/products/<slug>`` so
LLMs (Anthropic, OpenAI, Perplexity) can fetch a stable plain-text
rendering of any product without parsing HTML.

``render_ai_products_feed`` wraps every product's :func:`product_jsonld`
into a single ``ItemList`` for AI shopping crawlers (Google AI Shopping,
Perplexity, etc.).
"""
from __future__ import annotations

from ._helpers import site_settings
from .jsonld import product_jsonld


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
            avail = 'in stock' if not getattr(product, 'track_inventory', False) else \
                    ('in stock' if (getattr(product, 'stock_quantity', None) or 1) > 0 else 'out of stock')
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
        from django.contrib.contenttypes.models import ContentType
        from plugins.installed.metafields.models import Metafield
        ct = ContentType.objects.get_for_model(type(product))
        rows = list(Metafield.objects.filter(
            content_type=ct, object_id=product.pk, namespace='book',
        ).values_list('key', 'value'))
        if rows:
            parts.append('')
            parts.append('## Specifications')
            for k, v in rows:
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
                parts.append(f"### {r.get('title') or '(untitled)'} — {r['rating']}/5")
                parts.append((r.get('body') or '').strip())
    except Exception:  # noqa: BLE001
        pass
    return '\n'.join(parts) + '\n'


def render_ai_products_feed(*, limit: int = 500) -> dict:
    """Schema.org Product feed for AI shopping crawlers.

    Returns a dict that the view JSON-encodes. Each entry is a full
    Product JSON-LD object plus an `agent_metadata` block for any
    structured fields the merchant set on the Product.
    """
    out = {
        '@context': 'https://schema.org',
        '@type': 'ItemList',
        'name': site_settings().organization_name or 'Morpheus product feed',
        'itemListElement': [],
    }
    try:
        from plugins.installed.catalog.models import Product
        for i, p in enumerate(Product.objects.filter(status='active').order_by('-created_at')[:max(1, min(int(limit), 2000))]):
            out['itemListElement'].append({
                '@type': 'ListItem',
                'position': i + 1,
                'item': product_jsonld(p),
            })
    except Exception:  # noqa: BLE001
        pass
    return out
