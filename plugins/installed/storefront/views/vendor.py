"""Public-facing vendor pages — directory + per-vendor storefront."""
from __future__ import annotations

from morpheus.views import render


def vendors_directory(request):
    """Public vendor directory — every active vendor with at least one
    active product. Editorial intro mirrors the dot books voice.
    """
    from plugins.installed.catalog.models import Product, Vendor

    qs = (Vendor.objects.filter(is_active=True)
          .order_by('name')[:100])
    vendors = []
    for v in qs:
        product_count = Product.objects.filter(vendor=v, status='active').count()
        if product_count == 0:
            continue
        vendors.append({
            'obj': v,
            'product_count': product_count,
            'preview_products': list(
                Product.objects.filter(vendor=v, status='active')
                .order_by('-is_featured', '-created_at')[:3]
            ),
        })

    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'Publishers', 'url': request.build_absolute_uri(request.path)},
    ]
    return render(request, 'storefront/vendors.html', {
        'vendors': vendors,
        'breadcrumb_items': breadcrumb_items,
        'seo_title':       'Publishers & makers — dot books',
        'seo_description': "The independent presses, university imprints, and small publishers we work with. Every title on the shelf comes from one of these makers.",
        'seo_og_type':     'website',
    })


def vendor_detail(request, slug):
    """Per-vendor storefront — logo, bio, product grid, stats."""
    from morpheus.views import Http404
    from plugins.installed.catalog.models import Product, Vendor

    vendor = Vendor.objects.filter(slug=slug, is_active=True).first()
    if vendor is None:
        raise Http404

    products = list(
        Product.objects.filter(vendor=vendor, status='active')
        .select_related('category')
        .order_by('-is_featured', '-created_at')[:60]
    )

    product_count = Product.objects.filter(vendor=vendor, status='active').count()
    category_count = (Product.objects
                      .filter(vendor=vendor, status='active', category__isnull=False)
                      .values('category').distinct().count())

    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'Publishers', 'url': request.build_absolute_uri('/vendors/')},
        {'name': vendor.name, 'url': request.build_absolute_uri(request.path)},
    ]
    intro_fallback = (
        f"{vendor.name} is one of the independent presses we work with. "
        f"Every {vendor.name} title on the shelf was read and selected by us first."
    )
    return render(request, 'storefront/vendor_detail.html', {
        'vendor': vendor,
        'products': products,
        'product_count': product_count,
        'category_count': category_count,
        'intro_text': vendor.description or intro_fallback,
        'breadcrumb_items': breadcrumb_items,
        'seo_title':       f'{vendor.name} — Publishers · dot books',
        'seo_description': (vendor.description or intro_fallback)[:160],
        'seo_og_type':     'website',
    })
