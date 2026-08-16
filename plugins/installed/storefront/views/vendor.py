"""Public-facing vendor pages — marketplace landing + directory + per-vendor storefront."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db.models import Count, Prefetch, Q, Sum

from morpheus.app.views import Http404, render
from plugins.installed.catalog.models import Product, Vendor
from plugins.installed.storefront.services import page_intro
from plugins.registry import app_registry

# Optional sibling plugins — marketplace ships VendorOrder for the
# "books sold" stat, metafields drives editorial FAQ overrides. Both
# imports are wrapped so the storefront still boots if either plugin is
# absent from MORPHEUS_DEFAULT_APPS; every USE is additionally gated on
# `app_registry.is_active()` so a runtime disable drops the surface too.
try:
    from plugins.installed.marketplace.models import VendorOrder as _VendorOrder
except Exception:  # noqa: BLE001
    _VendorOrder = None  # type: ignore[assignment]

try:
    from plugins.installed.metafields.models import Metafield as _Metafield
except Exception:  # noqa: BLE001
    _Metafield = None  # type: ignore[assignment]


def _marketplace_counts() -> dict:
    """Cache the three top-of-page counts for 5 minutes.

    These are full-table aggregates that all show the same value across
    every landing render within the cache window — pulling them on each
    request was 3-4 redundant COUNT queries per visitor.
    """

    def _compute() -> dict:
        vendor_count = (
            Vendor.objects.filter(is_active=True, products__status='active').distinct().count()
        )
        active_product_count = Product.objects.filter(status='active').count()
        try:
            titles_in_stock_now = (
                Product.objects.filter(status='active')
                .filter(Q(track_inventory=False) | Q(variants__stock_levels__quantity__gt=0))
                .distinct()
                .count()
            )
        except Exception:  # noqa: BLE001 — schema mismatch / inventory plugin missing
            titles_in_stock_now = Product.objects.filter(
                status='active', track_inventory=False
            ).count()
        return {
            'vendor_count': vendor_count,
            'active_product_count': active_product_count,
            'titles_in_stock_now': titles_in_stock_now,
        }

    return cache.get_or_set('marketplace:counts', _compute, 300)


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
    qs = (
        qs.annotate(active_product_count=Count('products', filter=Q(products__status='active')))
        .filter(active_product_count__gt=0)
        .prefetch_related(
            Prefetch(
                'products',
                queryset=Product.objects.filter(status='active').order_by(
                    '-is_featured', '-created_at'
                ),
                to_attr='_preview_products_all',
            )
        )
        .order_by('name')[:100]
    )

    vendors = []
    for v in qs:
        vendors.append(
            {
                'obj': v,
                'product_count': v.active_product_count,
                'preview_products': getattr(v, '_preview_products_all', [])[:3],
            }
        )

    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'Marketplace', 'url': request.build_absolute_uri('/marketplace/')},
        {'name': 'Publishers', 'url': request.build_absolute_uri(request.path)},
    ]
    intro = page_intro(request, 'vendors')
    return render(
        request,
        'storefront/vendors.html',
        {
            'vendors': vendors,
            'query': q,
            'breadcrumb_items': breadcrumb_items,
            'page_intro': intro['body'],
            'seo_title': 'Publishers & makers — dot books',
            'seo_description': (
                intro['meta_description']
                or intro['body']
                or 'The independent presses, university imprints, and small publishers we work with. Every title on the shelf comes from one of these makers.'
            )[:160],
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

    # Derive count + represented-category count from the materialised list
    # so we avoid two extra COUNT queries against the same filter.
    product_count = len(products)
    category_count = len({p.category_id for p in products if p.category_id})

    # Books sold lifetime — sum of confirmed/shipped/delivered VendorOrder.gross.
    # Cheap aggregate; safe to skip if the marketplace plugin isn't installed.
    books_sold = 0
    if _VendorOrder is not None and app_registry.is_active('marketplace'):
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
    # Real ORM counts — the three top-of-page numbers are full-table
    # aggregates so we cache them for 5 minutes to spare the DB on bursty
    # landing traffic.
    counts = _marketplace_counts()
    vendor_count = counts['vendor_count']
    active_product_count = counts['active_product_count']
    titles_in_stock_now = counts['titles_in_stock_now']

    # 6 featured vendors — active, with at least one active product, with
    # a description (so the cards aren't blank). Ordered by most-recent so
    # the grid feels alive between visits. Annotate the count so we don't
    # issue a per-card COUNT query inside the loop.
    featured_qs = (
        Vendor.objects.filter(is_active=True, products__status='active')
        .exclude(description='')
        .annotate(product_count=Count('products', filter=Q(products__status='active')))
        .distinct()
        .order_by('-created_at')[:6]
    )
    featured_vendors = [{'obj': v, 'product_count': v.product_count} for v in featured_qs]

    # FAQ — editorial overrides stored as metafields on the Vendor content
    # type (namespace='marketplace', keys 'faq_<n>_q' / 'faq_<n>_a'). Falls
    # through to template defaults if nothing is configured.
    faqs = []
    if _Metafield is not None and app_registry.is_active('metafields'):
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
