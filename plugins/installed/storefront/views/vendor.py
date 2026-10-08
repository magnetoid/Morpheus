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
    """Public vendor directory — every active vendor with something to show.

    "Something" is catalog Products AND whatever another app lists for the
    vendor (`catalog.vendors.listing_counts`): the travel store's directory
    showed one vendor while its 170 hosts — whose experiences and stays live in
    booking_marketplace — were missing from it. The editorial intro comes from
    the merchant's own copy (`page_intro`), not from a voice the shell decides.

    Supports an optional ``?q=`` filter against ``Vendor.name`` /
    ``Vendor.description`` so customers can hunt for a known shop.
    """
    from plugins.installed.catalog.vendors import listing_counts
    from plugins.installed.storefront.services import store_name, vendor_nouns

    counts = listing_counts()
    q = (request.GET.get('q') or '').strip()
    qs = Vendor.objects.filter(pk__in=list(counts))
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    qs = qs.prefetch_related(
        Prefetch(
            'products',
            queryset=Product.objects.filter(status='active').order_by(
                '-is_featured', '-created_at'
            ),
            to_attr='_preview_products_all',
        )
    ).order_by('name')[:100]

    vendors = [
        {
            'obj': v,
            # Everything the vendor page lists, not only catalog Products —
            # the card's count and the page it links to must agree.
            'product_count': counts.get(str(v.pk), 0),
            'preview_products': getattr(v, '_preview_products_all', [])[:3],
        }
        for v in qs
    ]

    _single, plural = vendor_nouns()
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': plural, 'url': request.build_absolute_uri(request.path)},
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
            'seo_title': plural,
            'seo_description': (
                intro['meta_description']
                or intro['body']
                or f'The {plural.lower()} behind everything {store_name()} offers.'
            )[:160],
            'seo_og_type': 'website',
            # The SEO layer holds an empty directory out of the index.
            'seo_item_count': len(vendors),
        },
    )


def _vendor_sections(vendor, request) -> list[dict]:
    """What other apps list for this vendor (`STOREFRONT_VENDOR_SECTIONS`), in order."""
    from morpheus.core import MorpheusEvents, hook_registry

    try:
        raw = hook_registry.filter(
            MorpheusEvents.STOREFRONT_VENDOR_SECTIONS, [], vendor=vendor, request=request
        )
    except Exception:  # noqa: BLE001 — a broken contributor must not take the page down
        return []
    sections = []
    for section in raw or []:
        if not isinstance(section, dict) or not section.get('template'):
            continue
        try:
            count = int(section.get('count') or 0)
        except (TypeError, ValueError):
            continue
        if count > 0:
            sections.append({**section, 'count': count})
    return sorted(sections, key=lambda s: s.get('order', 100))


def vendor_detail(request, slug):
    """Per-vendor storefront — logo, bio, everything the vendor lists, stats.

    Catalog Products are paginated here; anything another app lists for the
    vendor (a travel host's experiences and stays) arrives as sections through
    `STOREFRONT_VENDOR_SECTIONS` and counts toward the page's total — the number
    the SEO layer reads to keep an empty vendor page out of the index.
    """
    from core.utils.pagination import paginate_or_404
    from plugins.installed.storefront.services import store_name, vendor_nouns

    vendor = Vendor.objects.filter(slug=slug, is_active=True).first()
    if vendor is None:
        raise Http404

    page_obj = paginate_or_404(
        Product.objects.filter(vendor=vendor, status='active')
        .select_related('category')
        .order_by('-is_featured', '-created_at'),
        48,
        request,
    )
    products = list(page_obj.object_list)
    vendor_sections = _vendor_sections(vendor, request)

    # Everything the vendor lists, across every page and every section.
    product_count = page_obj.paginator.count
    listing_count = product_count + sum(s['count'] for s in vendor_sections)
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

    single, plural = vendor_nouns()
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': plural, 'url': request.build_absolute_uri('/vendors/')},
        {'name': vendor.name, 'url': request.build_absolute_uri(request.path)},
    ]

    # The ItemList the SEO graph publishes for this page — the catalog grid and
    # every contributed section, so a host's page describes its experiences.
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
    for section in vendor_sections:
        collection_items.extend(section.get('jsonld_items') or [])

    # The vendor's own words, or none: the shell used to invent "one of the
    # independent presses we work with" for every vendor of every store.
    description = (vendor.description or '').strip()
    return render(
        request,
        'storefront/vendor_detail.html',
        {
            'vendor': vendor,
            'products': products,
            'page_obj': page_obj,
            'product_count': product_count,
            'listing_count': listing_count,
            'vendor_sections': vendor_sections,
            'vendor_noun': single,
            'category_count': category_count,
            'books_sold': books_sold,
            'collection_items': collection_items,
            'intro_text': description,
            'breadcrumb_items': breadcrumb_items,
            'seo_title': f'{vendor.name} — {plural}',
            'seo_description': (
                description or f'Everything {vendor.name} offers on {store_name()}.'
            )[:160],
            'seo_og_type': 'website',
            # Products on every page + every section: zero means an empty page,
            # which the SEO layer keeps out of the index.
            'seo_item_count': listing_count,
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

    from plugins.installed.storefront.services import store_name, vendor_nouns

    single, _plural = vendor_nouns()
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
            # "Independent presses and bookshops, in one shelf." was this
            # description on the apothecary and the travel store too.
            'seo_description': f'Every {single.lower()} on {store_name()}, in one place.',
            'seo_og_type': 'website',
        },
    )
