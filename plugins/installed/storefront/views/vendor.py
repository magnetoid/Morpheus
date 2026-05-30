"""Public-facing vendor pages — marketplace landing + directory + per-vendor storefront."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, Sum

from morpheus.views import Http404, render
from plugins.installed.catalog.models import Product, Vendor

# Optional sibling plugins — marketplace ships VendorOrder for the
# "books sold" stat, metafields drives editorial FAQ overrides. Both
# imports are wrapped so the storefront still boots if either plugin is
# disabled in MORPHEUS_DEFAULT_PLUGINS.
try:
    from plugins.installed.marketplace.models import VendorOrder as _VendorOrder
except Exception:  # noqa: BLE001
    _VendorOrder = None  # type: ignore[assignment]

try:
    from plugins.installed.metafields.models import Metafield as _Metafield
except Exception:  # noqa: BLE001
    _Metafield = None  # type: ignore[assignment]


def vendors_directory(request):
    """Public vendor directory — every active vendor with at least one
    active product. Editorial intro mirrors the dot books voice.

    Supports an optional ``?q=`` filter against ``Vendor.name`` /
    ``Vendor.description`` so customers can hunt for a known shop.
    """
    q = (request.GET.get('q') or '').strip()
    qs = Vendor.objects.filter(is_active=True)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    qs = qs.order_by('name')[:100]

    vendors = []
    for v in qs:
        product_count = Product.objects.filter(vendor=v, status='active').count()
        if product_count == 0:
            continue
        vendors.append(
            {
                'obj': v,
                'product_count': product_count,
                'preview_products': list(
                    Product.objects.filter(vendor=v, status='active').order_by(
                        '-is_featured', '-created_at'
                    )[:3]
                ),
            }
        )

    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'Marketplace', 'url': request.build_absolute_uri('/marketplace/')},
        {'name': 'Publishers', 'url': request.build_absolute_uri(request.path)},
    ]
    return render(
        request,
        'storefront/vendors.html',
        {
            'vendors': vendors,
            'query': q,
            'breadcrumb_items': breadcrumb_items,
            'seo_title': 'Publishers & makers — dot books',
            'seo_description': 'The independent presses, university imprints, and small publishers we work with. Every title on the shelf comes from one of these makers.',
            'seo_og_type': 'website',
        },
    )


def vendor_detail(request, slug):
    """Per-vendor storefront — logo, bio, product grid, stats."""
    vendor = Vendor.objects.filter(slug=slug, is_active=True).first()
    if vendor is None:
        raise Http404

    products = list(
        Product.objects.filter(vendor=vendor, status='active')
        .select_related('category')
        .order_by('-is_featured', '-created_at')[:60]
    )

    product_count = Product.objects.filter(vendor=vendor, status='active').count()
    category_count = (
        Product.objects.filter(vendor=vendor, status='active', category__isnull=False)
        .values('category')
        .distinct()
        .count()
    )

    # Books sold lifetime — sum of confirmed/shipped/delivered VendorOrder.gross.
    # Cheap aggregate; safe to skip if the marketplace plugin isn't installed.
    books_sold = 0
    if _VendorOrder is not None:
        try:
            agg = _VendorOrder.objects.filter(
                vendor=vendor, status__in=('confirmed', 'shipped', 'delivered')
            ).aggregate(total=Sum('gross'))
            total = agg.get('total')
            if total is not None:
                # MoneyField returns Money; .amount is the decimal.
                books_sold = int(getattr(total, 'amount', total) or 0)
        except Exception:  # noqa: BLE001 — never break the page on a stats query
            books_sold = 0

    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'Marketplace', 'url': request.build_absolute_uri('/marketplace/')},
        {'name': 'Publishers', 'url': request.build_absolute_uri('/vendors/')},
        {'name': vendor.name, 'url': request.build_absolute_uri(request.path)},
    ]
    intro_fallback = (
        f'{vendor.name} is one of the independent presses we work with. '
        f'Every {vendor.name} title on the shelf was read and selected by us first.'
    )

    # Build CollectionPage items for the product grid — used by
    # seo_collection_jsonld so search/AI engines see this as a vendor catalog.
    collection_items = []
    for p in products[:30]:
        img = ''
        try:
            pi = p.primary_image
            if pi and getattr(pi, 'image', None):
                img = request.build_absolute_uri(pi.image.url)
        except Exception:  # noqa: BLE001
            img = ''
        collection_items.append(
            {
                'name': p.name,
                'url': request.build_absolute_uri(f'/products/{p.slug}/'),
                'image': img,
            }
        )

    return render(
        request,
        'storefront/vendor_detail.html',
        {
            'vendor': vendor,
            'products': products,
            'product_count': product_count,
            'category_count': category_count,
            'books_sold': books_sold,
            'collection_items': collection_items,
            'intro_text': vendor.description or intro_fallback,
            'breadcrumb_items': breadcrumb_items,
            'seo_title': f'{vendor.name} — Publishers · dot books',
            'seo_description': (vendor.description or intro_fallback)[:160],
            'seo_og_type': 'website',
        },
    )


def marketplace_landing(request):
    """Public marketplace landing — the editorial doorway customers hit
    when they want to learn about the indie-press side of the shop.

    Pulls real-time counts (vendors / active products / in-stock) and a
    rotating 6-card grid of featured vendors. FAQ entries come from
    ``Metafield(namespace='marketplace', key='faq_*')`` if any are set;
    otherwise the template renders the editorial defaults.
    """
    # Real ORM counts — kept cheap (one query each).
    vendor_count = (
        Vendor.objects.filter(is_active=True, products__status='active').distinct().count()
    )
    active_product_count = Product.objects.filter(status='active').count()
    titles_in_stock_now = (
        Product.objects.filter(status='active')
        .filter(Q(track_inventory=False) | Q(inventory_quantity__gt=0))
        .count()
    )

    # 6 featured vendors — active, with at least one active product, with
    # a description (so the cards aren't blank). Ordered by most-recent so
    # the grid feels alive between visits.
    featured_qs = (
        Vendor.objects.filter(is_active=True, products__status='active')
        .exclude(description='')
        .distinct()
        .order_by('-created_at')[:6]
    )
    featured_vendors = []
    for v in featured_qs:
        featured_vendors.append(
            {
                'obj': v,
                'product_count': Product.objects.filter(vendor=v, status='active').count(),
            }
        )

    # FAQ — editorial overrides stored as metafields on the Vendor content
    # type (namespace='marketplace', keys 'faq_<n>_q' / 'faq_<n>_a'). Falls
    # through to template defaults if nothing is configured.
    faqs = []
    if _Metafield is not None:
        try:
            vendor_ct = ContentType.objects.get_for_model(Vendor)
            rows = _Metafield.objects.filter(
                content_type=vendor_ct, namespace='marketplace', key__startswith='faq_'
            ).order_by('key')
            bucket: dict[str, dict[str, str]] = {}
            for m in rows:
                # key shape: faq_<n>_q | faq_<n>_a
                parts = m.key.split('_')
                if len(parts) < 3:
                    continue
                n, kind = parts[1], parts[2]
                bucket.setdefault(n, {})[kind] = m.value
            for n in sorted(bucket.keys()):
                row = bucket[n]
                if row.get('q') and row.get('a'):
                    faqs.append({'q': row['q'], 'a': row['a']})
        except Exception:  # noqa: BLE001 — FAQ is best-effort, never breaks landing
            faqs = []

    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'Marketplace', 'url': request.build_absolute_uri(request.path)},
    ]
    return render(
        request,
        'storefront/marketplace_landing.html',
        {
            'vendor_count': vendor_count,
            'active_product_count': active_product_count,
            'titles_in_stock_now': titles_in_stock_now,
            'featured_vendors': featured_vendors,
            'faqs': faqs,
            'breadcrumb_items': breadcrumb_items,
            'seo_title': 'The Marketplace',
            'seo_description': 'Independent presses and bookshops, in one shelf.',
            'seo_og_type': 'website',
        },
    )
