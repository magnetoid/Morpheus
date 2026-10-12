"""Flipbook view — renders the PDF.js + StPageFlip page for one product.

Resolves the product by slug, finds a PDF source (Product.digital_file
or ProductVariant.digital_file fallback), and renders a fullscreen
flipbook page. No-op when the flipbook plugin is disabled, the product
is missing, or the source isn't a PDF.
"""

from __future__ import annotations

from django.utils.translation import gettext

from morpheus.app.views import Http404, render


def _plugin_config() -> dict:
    try:
        from plugins.registry import app_registry

        p = app_registry.get('flipbook')
        if p is None:
            return {}
        return p.get_config() or {}
    except Exception:  # noqa: BLE001
        return {}


def _source(product):
    """The product's PDF (its own, else the first active digital variant's), or None.

    The file itself is never linked: /media/digital/ answers staff only
    (core/media.py), and the page reads the first pages from ``preview_pdf``.
    """
    files = [getattr(product, 'digital_file', None)]
    v = (
        product.variants.filter(is_active=True, variant_type='digital')
        .exclude(digital_file='')
        .order_by('sort_order')
        .first()
    )
    if v is not None:
        files.append(v.digital_file)
    for f in files:
        if f and getattr(f, 'name', '') and f.name.lower().endswith('.pdf'):
            return f
    return None


def preview_pdf(request, slug: str):
    """The first ``max_preview_pages`` pages of the product's PDF, made here."""
    import io

    from django.core.cache import cache
    from django.http import HttpResponse
    from pypdf import PdfReader, PdfWriter

    cfg = _plugin_config()
    if cfg.get('enabled') is False:
        raise Http404
    from plugins.installed.catalog.models import Product

    product = Product.objects.filter(slug=slug, status='active').first()
    source = _source(product) if product else None
    if source is None:
        raise Http404
    max_pages = int(cfg.get('max_preview_pages') or 20)
    key = f'flipbook:preview:{source.name}:{max_pages}'
    data = cache.get(key)
    if data is None:
        try:
            with source.open('rb') as fh:
                reader = PdfReader(fh)
                writer = PdfWriter()
                for page in reader.pages[:max_pages]:
                    writer.add_page(page)
                buf = io.BytesIO()
                writer.write(buf)
            data = buf.getvalue()
        except Exception as e:  # noqa: BLE001 — a damaged or encrypted PDF has no preview
            raise Http404 from e
        cache.set(key, data, 60 * 60 * 24)
    resp = HttpResponse(data, content_type='application/pdf')
    resp['Content-Disposition'] = 'inline; filename="preview.pdf"'
    resp['Cache-Control'] = 'public, max-age=86400'
    resp['X-Robots-Tag'] = 'noindex'
    return resp


def flipbook(request, slug: str):
    cfg = _plugin_config()
    if cfg.get('enabled') is False:
        raise Http404

    from plugins.installed.catalog.models import Product

    product = Product.objects.filter(slug=slug, status='active').first()
    if product is None:
        raise Http404

    if _source(product) is None:
        raise Http404

    max_pages = int(cfg.get('max_preview_pages') or 20)
    cover = product.primary_image
    return render(
        request,
        'flipbook/reader.html',
        {
            # Not `product`: the SEO head takes a `product` in the context as
            # the page's subject and gives it the product page's own title and
            # description, so two indexable URLs would share one title.
            'book': product,
            'source_url': f'/p/{product.slug}/flipbook/preview.pdf',
            'max_pages': max_pages,
            'seo_title': gettext('Read a preview of %(name)s') % {'name': product.name},
            'seo_description': gettext(
                'Read the first %(pages)s pages of %(name)s in your browser.'
            )
            % {'pages': max_pages, 'name': product.name},
            'seo_image': cover.image.url if cover and cover.image else '',
            'theme': (cfg.get('theme') or 'paper').lower(),
            'breadcrumb_items': [
                {'name': 'Home', 'url': request.build_absolute_uri('/')},
                {'name': 'All books', 'url': request.build_absolute_uri('/products/')},
                {
                    'name': product.name,
                    'url': request.build_absolute_uri(f'/products/{product.slug}/'),
                },
                {'name': 'Preview', 'url': request.build_absolute_uri(request.path)},
            ],
        },
    )
