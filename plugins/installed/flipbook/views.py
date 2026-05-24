"""Flipbook view — renders the PDF.js + StPageFlip page for one product.

Resolves the product by slug, finds a PDF source (Product.digital_file
or ProductVariant.digital_file fallback), and renders a fullscreen
flipbook page. No-op when the flipbook plugin is disabled, the product
is missing, or the source isn't a PDF.
"""
from __future__ import annotations

from morpheus.views import Http404, render


def _plugin_config() -> dict:
    try:
        from plugins.registry import plugin_registry
        p = plugin_registry.get('flipbook')
        if p is None:
            return {}
        return p.get_config() or {}
    except Exception:  # noqa: BLE001
        return {}


def flipbook(request, slug: str):
    cfg = _plugin_config()
    if cfg.get('enabled') is False:
        raise Http404

    from plugins.installed.catalog.models import Product
    product = Product.objects.filter(slug=slug, status='active').first()
    if product is None:
        raise Http404

    # Source: prefer the product's digital_file; fall back to the first
    # active digital variant. The browser will fetch the PDF directly
    # over the storage backend (S3 / local /media/).
    source_url = ''
    source_name = ''
    if getattr(product, 'digital_file', None) and product.digital_file:
        try:
            source_url = product.digital_file.url
            source_name = product.digital_file.name
        except Exception:  # noqa: BLE001
            pass
    if not source_url:
        v = (product.variants
             .filter(is_active=True, variant_type='digital')
             .exclude(digital_file='')
             .order_by('sort_order')
             .first())
        if v and v.digital_file:
            try:
                source_url = v.digital_file.url
                source_name = v.digital_file.name
            except Exception:  # noqa: BLE001
                pass

    if not source_url or not source_name.lower().endswith('.pdf'):
        raise Http404

    return render(request, 'flipbook/reader.html', {
        'product':       product,
        'source_url':    source_url,
        'max_pages':     int(cfg.get('max_preview_pages') or 20),
        'theme':         (cfg.get('theme') or 'paper').lower(),
        'breadcrumb_items': [
            {'name': 'Home', 'url': request.build_absolute_uri('/')},
            {'name': 'All books', 'url': request.build_absolute_uri('/products/')},
            {'name': product.name, 'url': request.build_absolute_uri(f'/products/{product.slug}/')},
            {'name': 'Preview', 'url': request.build_absolute_uri(request.path)},
        ],
    })
