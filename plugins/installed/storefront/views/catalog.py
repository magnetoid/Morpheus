"""Catalog browse + search surfaces: PLP, PDP, search, category landings,
author landings, staff picks, categories, JSON quick-search.

Also exports the PDP helpers (_pdp_faqs, _published_reviews, _book_specs,
_related_products) and the hybrid-search helpers (_apply_search,
_metafield_search_ids). They're consumed by other modules in this package.
"""

# ruff: noqa: PLC0415, PLR0912, PLR0915, S110, I001, B904
# - PLC0415: inline imports across this file are intentional — every
#   view-level function imports only what it needs, keeping import time
#   low and avoiding circular deps with metafields / cms / ai_assistant.
# - PLR0912 / PLR0915: product_list / product_detail / author_detail are
#   the catalog's hot paths; splitting them prematurely would make the
#   request flow harder to read.
# - S110: defensive try/except/pass around optional integrations (videos,
#   metafields, similar-to) is deliberate — they must never break a PDP.
# - I001: per-function localised import groups intentionally.
# - B904: Http404 in author_detail is a deliberate re-raise of an
#   internal lookup failure; no chained context needed.
from __future__ import annotations

from api.client import internal_graphql
from core.hooks import MorpheusEvents, hook_registry
from morpheus.views import render

from ._queries import PRODUCT_DETAIL_QUERY


def _surface_reorder(request, surface, products):
    """Merchandising takeover (STOREFRONT_PRODUCTS, reorder-only, fail-soft).

    Lets a dynamics surface block re-rank the current page slice; with no
    block (or dynamics disabled) the list passes through unchanged.
    """
    try:
        from core.hooks import MorpheusEvents, hook_registry

        return (
            hook_registry.filter(
                MorpheusEvents.STOREFRONT_PRODUCTS,
                value=products,
                surface=surface,
                request=request,
                limit=len(products) or 1,
            )
            or products
        )
    except Exception:
        return products


def product_list(request):
    """Product list with merchant-friendly facets: category, tag, price range,
    attribute facets (size/color/brand/...), and sort."""
    from decimal import Decimal, InvalidOperation
    from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
    from django.db.models import Q
    from plugins.installed.catalog.models import (
        Attribute,
        AttributeValue,
        Category,
        Product,
    )

    qs = Product.objects.filter(status='active').select_related('category')

    # Search — Postgres full-text on Postgres backends, LIKE fallback elsewhere.
    q = (request.GET.get('q') or '').strip()
    if q:
        qs = _apply_search(qs, q)

    # Category filter — match either the primary `category` FK OR the
    # `additional_categories` M2M, with .distinct() to avoid duplicate
    # rows from the join. Symmetric with category_detail's listing.
    cat_slug = (request.GET.get('category') or '').strip()
    if cat_slug:
        qs = qs.filter(
            Q(category__slug=cat_slug) | Q(additional_categories__slug=cat_slug)
        ).distinct()

    # Genre / Topic filter — `?genre=<slug>` / `?topic=<slug>` (the book_product
    # taxonomies that replaced category-as-genre). Match via the book's M2M.
    genre_slug = (request.GET.get('genre') or '').strip()
    if genre_slug:
        qs = qs.filter(book__genres__slug=genre_slug).distinct()
    topic_slug = (request.GET.get('topic') or '').strip()
    if topic_slug:
        qs = qs.filter(book__topics__slug=topic_slug).distinct()

    # Collection filter — `?collection=<slug>` (curated merchandising sets;
    # the PDP "Featured in" chips link here so a shopper can browse the set).
    col_slug = (request.GET.get('collection') or '').strip()
    if col_slug:
        qs = qs.filter(collections__slug=col_slug)

    # Tag filter
    tag_slug = (request.GET.get('tag') or '').strip()
    selected_tag_obj = None
    if tag_slug:
        # Match by slug OR name — product cards link by tag.slug while the tag
        # itself is stored by name, so a name-only filter missed slugged links.
        from django.db.models import Q  # noqa: PLC0415

        qs = qs.filter(Q(tags__name__iexact=tag_slug) | Q(tags__slug__iexact=tag_slug))
        # Editorial copy for the tag landing (title + description below it).
        from plugins.installed.catalog.models import TagProfile  # noqa: PLC0415

        selected_tag_obj = TagProfile.for_tag(tag_slug)

    # Book filters — `?author=Hanna Rieder`, `?publisher=Pelican Press`.
    # Model-first (BookProduct) with a legacy book.* metafield fallback.
    book_filter = {}
    for qk in ('author', 'publisher'):
        v = (request.GET.get(qk) or '').strip()
        if v:
            book_filter[qk] = v
    for qk, v in book_filter.items():
        try:
            from plugins.installed.book_product.compat import product_ids_for

            qs = qs.filter(id__in=product_ids_for(qk, v))
        except Exception:  # noqa: BLE001
            pass

    # Price range
    pmin = request.GET.get('price_min')
    pmax = request.GET.get('price_max')
    try:
        if pmin:
            qs = qs.filter(price__gte=Decimal(pmin))
        if pmax:
            qs = qs.filter(price__lte=Decimal(pmax))
    except (InvalidOperation, TypeError):
        pass

    # Attribute facets — `?attr_<slug>=value1,value2`.
    selected_attrs: dict[str, list[str]] = {}
    for key, raw in request.GET.lists():
        if not key.startswith('attr_'):
            continue
        attr_slug = key[len('attr_') :]
        values = [
            v for chunk in raw for v in (chunk.split(',') if isinstance(chunk, str) else []) if v
        ]
        if not values:
            continue
        selected_attrs[attr_slug] = values
        q_obj = Q(
            productattribute__attribute__slug=attr_slug, productattribute__values__slug__in=values
        ) | Q(
            variants__attribute_values__attribute__slug=attr_slug,
            variants__attribute_values__slug__in=values,
        )
        qs = qs.filter(q_obj)

    qs = qs.distinct()

    # Sort
    sort = (request.GET.get('sort') or 'for_you').strip()
    sort_map = {
        'for_you': '-created_at',  # Base sort, dynamically reordered later
        'newest': '-created_at',
        'oldest': 'created_at',
        'price_asc': 'price',
        'price_desc': '-price',
        'name': 'name',
    }
    qs = qs.order_by(sort_map.get(sort, '-created_at'))

    # Build facet panel.
    facet_attributes = list(
        Attribute.objects.filter(is_filterable=True).order_by('sort_order', 'name')
    )
    facets = []
    for attr in facet_attributes:
        value_ids = set(
            AttributeValue.objects.filter(
                attribute=attr,
                productattribute__product__in=qs,
            ).values_list('id', flat=True)
        ) | set(
            AttributeValue.objects.filter(
                attribute=attr,
                productvariant__product__in=qs,
            ).values_list('id', flat=True)
        )
        if not value_ids:
            continue
        values = list(
            AttributeValue.objects.filter(id__in=value_ids).order_by('sort_order', 'name')
        )
        facets.append(
            {
                'attr': attr,
                'values': values,
                'selected': set(selected_attrs.get(attr.slug, [])),
            }
        )

    # Pagination — 60 per page. ?page=N navigates; out-of-range / non-int
    # quietly falls back to page 1 so a hand-typed URL never 404s the PLP.
    paginator = Paginator(qs, 60)
    try:
        page_obj = paginator.page(request.GET.get('page') or 1)
    except (EmptyPage, PageNotAnInteger):
        page_obj = paginator.page(1)
    products = list(page_obj.object_list)

    # Advanced Personalization: Reorder the page dynamically if 'for_you' intent sort is active
    if sort == 'for_you':
        products = hook_registry.filter(
            MorpheusEvents.PRODUCT_LIST_REORDER,
            value=products,
            request=request,
            surface='catalog_plp',
        )
        products = _surface_reorder(request, 'plp_default', products)

    # Query-string base for pagination links — drops `page` so the template
    # can append it cleanly while preserving every active filter (search,
    # category, collection, tag, author, sort, attribute facets, …).
    _qs_no_page = request.GET.copy()
    _qs_no_page.pop('page', None)
    paginator_base_qs = _qs_no_page.urlencode()

    categories_list = list(Category.objects.filter(parent__isnull=True).order_by('name'))

    # Author facet — distinct authors (BookProduct model ∪ legacy metafields).
    available_authors: list[str] = []
    try:
        from plugins.installed.book_product.compat import distinct_values

        available_authors = distinct_values('author')
    except Exception:  # noqa: BLE001
        pass

    selected_cat = next((c for c in categories_list if c.slug == cat_slug), None)
    # SEO title/name for the listing. This drives the <title> (via seo_title →
    # {% seo_meta %}), the CollectionPage JSON-LD name, and the OG title — the
    # theme's {% block title %} is NOT what renders <title> (base.html emits it
    # through seo_meta), so this must mirror that block's precedence or filtered
    # PLPs all title as "All books". Order: author > publisher > category > tag
    # > search > default.
    _author_label = book_filter.get('author', '')
    _publisher_label = book_filter.get('publisher', '')
    _tag_label = (selected_tag_obj.name if selected_tag_obj else '') or tag_slug
    if _author_label:
        plp_name = f'Books by {_author_label}'
    elif _publisher_label:
        plp_name = f'{_publisher_label} titles'
    elif selected_cat:
        plp_name = selected_cat.name
    elif _tag_label:
        plp_name = _tag_label
    elif q:
        plp_name = f'Search: {q}'
    else:
        plp_name = 'All books'
    plp_items = [
        {
            'name': p.name,
            'url': request.build_absolute_uri(f'/products/{p.slug}/'),
            'image': (
                p.primary_image.image.url
                if p.primary_image and getattr(p.primary_image, 'image', None)
                else ''
            ),
        }
        for p in products[:50]
    ]
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'All books', 'url': request.build_absolute_uri('/products/')},
    ]
    if selected_cat:
        breadcrumb_items.append(
            {
                'name': selected_cat.name,
                'url': request.build_absolute_uri(f'/products/?category={selected_cat.slug}'),
            }
        )
    return render(
        request,
        'storefront/product_list.html',
        {
            'products': products,
            'categories': categories_list,
            'facets': facets,
            'available_authors': available_authors,
            'search_query': q,
            'selected_category': cat_slug,
            'selected_category_obj': selected_cat,
            'selected_tag': tag_slug,
            'selected_tag_obj': selected_tag_obj,
            'selected_author': book_filter.get('author', ''),
            'selected_publisher': book_filter.get('publisher', ''),
            'selected_sort': sort,
            'price_min': pmin or '',
            'price_max': pmax or '',
            'plp_items': plp_items,
            'plp_name': plp_name,
            'page_obj': page_obj,
            'paginator': paginator,
            'paginator_base_qs': paginator_base_qs,
            'breadcrumb_items': breadcrumb_items,
            'seo_title': f'{plp_name} — dot books',
            'seo_description': (
                (selected_cat.description if selected_cat and selected_cat.description else '')
                or (
                    selected_tag_obj.meta_description or selected_tag_obj.description
                    if selected_tag_obj
                    else ''
                )
                or 'The full dot books shelf — independent press, curated by readers.'
            )[:160],
        },
    )


def _apply_search(qs, q: str):
    """Three-tier retrieval:

    1. Typesense (sprint #3) — typo-tolerant + synonym-aware. Active
       when settings.TYPESENSE['host'] is set; falls through otherwise.
    2. Hybrid (BM25 + dense embeddings, RRF-fused) — the previous default,
       still used when Typesense is off or empty.
    3. SKU exact / metafield substring — backstop.
    """
    from django.db.models import Case, IntegerField, Q, When  # noqa: PLC0415
    from core.hooks import MorpheusEvents, hook_registry  # noqa: PLC0415
    from plugins.installed.catalog.search import (  # noqa: PLC0415
        get_backend as _search_backend,
        search as _catalog_search,
    )

    typesense_ids: list = []
    if _search_backend() == 'typesense':
        try:
            result = _catalog_search(q, per_page=80)
            typesense_ids = list(result.product_ids)
        except Exception:  # noqa: BLE001 — fall through to hybrid on any error
            typesense_ids = []

    metafield_ids = list(_metafield_search_ids(q))
    # Hybrid ranking is contributed by ai_assistant via SEARCH_RANKED_IDS —
    # disabled/absent, the filter returns [] and tier 3 takes over.
    hybrid_ids = (
        list(hook_registry.filter(MorpheusEvents.SEARCH_RANKED_IDS, [], query=q, limit=80))
        if not typesense_ids
        else []
    )

    # Preserve Typesense ordering first, then hybrid, then metafield matches.
    union_ids = list(dict.fromkeys(typesense_ids + hybrid_ids + metafield_ids))
    if not union_ids:
        return qs.filter(Q(sku__iexact=q))

    filtered = qs.filter(Q(id__in=union_ids) | Q(sku__iexact=q))
    ranked_ids = typesense_ids or hybrid_ids
    if not ranked_ids:
        return filtered.order_by('-created_at')

    rank_cases = [When(pk=pid, then=idx) for idx, pid in enumerate(ranked_ids)]
    return filtered.annotate(
        _hybrid_rank=Case(
            *rank_cases,
            default=len(ranked_ids) + 1,
            output_field=IntegerField(),
        )
    ).order_by('_hybrid_rank', '-created_at')


def _metafield_search_ids(q: str) -> list:
    """Return product IDs whose book.author/publisher/isbn metafield contains q."""
    try:
        from django.contrib.contenttypes.models import ContentType
        from plugins.installed.catalog.models import Product
        from plugins.installed.metafields.models import Metafield

        ct = ContentType.objects.get_for_model(Product)
        return list(
            Metafield.objects.filter(
                content_type=ct,
                namespace='book',
                key__in=('author', 'publisher', 'isbn'),
                value__icontains=q,
            ).values_list('object_id', flat=True)
        )
    except Exception:  # noqa: BLE001
        return []


def product_detail(request, slug):
    data = internal_graphql(PRODUCT_DETAIL_QUERY, variables={'slug': slug}, request=request)
    product = (data or {}).get('product')
    if not product:
        from morpheus.views import Http404

        raise Http404

    # Variant blurbs render as plain text on the PDP (pdp-variant__desc +
    # the data-variant-desc JS attr), but shortDescription is a rich-text
    # HTML field — flatten it so literal <p> tags don't leak. The product
    # lede keeps its HTML (rendered |safe).
    import html as _html
    import re as _re

    from django.utils.html import strip_tags as _strip_tags

    def _plain(s):
        return _re.sub(r'\s+', ' ', _html.unescape(_strip_tags(str(s or '')))).strip()

    for _v in product.get('variants') or []:
        if _v.get('shortDescription'):
            _v['shortDescription'] = _plain(_v['shortDescription'])

    from plugins.installed.catalog.models import Product as _Product

    try:
        product_row = (
            _Product.objects.filter(slug=slug)
            .select_related('vendor')
            .only(
                'id',
                'slug',
                'updated_at',
                'vendor__id',
                'vendor__name',
                'vendor__slug',
                'vendor__is_active',
            )
            .first()
        )
    except Exception:  # noqa: BLE001
        product_row = None

    pdp_vendor = None
    if product_row is not None and product_row.vendor and product_row.vendor.is_active:
        pdp_vendor = product_row.vendor

    # Server-side analytics: the funnel's product.viewed truth. Client
    # beacons are ad-blockable; this is not. Fail-soft — never break a PDP.
    try:
        from core.hooks import MorpheusEvents, hook_registry  # noqa: PLC0415

        if product_row is not None:
            hook_registry.fire(
                MorpheusEvents.PRODUCT_VIEWED,
                product=product_row,
                customer=request.user if request.user.is_authenticated else None,
                request=request,
            )
    except Exception:  # noqa: BLE001, S110
        pass

    related = _related_products(slug, request=request)
    images = product.get('images') or []
    primary_images = sorted(
        (i for i in images if i.get('isPrimary')),
        key=lambda i: i.get('sortOrder') or 0,
    )[:2]
    primary_image = primary_images[0] if primary_images else None
    hero_image = primary_image or (images[0] if images else None)
    breadcrumb_items = [{'name': 'Home', 'url': request.build_absolute_uri('/')}]
    breadcrumb_items.append({'name': 'All books', 'url': request.build_absolute_uri('/products/')})
    cat = (product or {}).get('category') or {}
    if cat.get('slug'):
        breadcrumb_items.append(
            {
                'name': cat.get('name') or cat['slug'],
                'url': request.build_absolute_uri(f'/products/?category={cat["slug"]}'),
            }
        )
    breadcrumb_items.append(
        {
            'name': product.get('name') or slug,
            'url': request.build_absolute_uri(request.path),
        }
    )
    last_reviewed = None
    if product_row is not None:
        last_reviewed = product_row.updated_at
        if isinstance(product, dict):
            product['updatedAt'] = last_reviewed.isoformat()
    active_pdp_edit_url = ''
    pid = (product or {}).get('id') if isinstance(product, dict) else None
    if pid and request.user.is_authenticated and request.user.is_staff:
        active_pdp_edit_url = f'/dashboard/products/{pid}/'

    videos: list = []
    try:
        from plugins.installed.product_videos.models import ProductVideo

        videos = list(
            ProductVideo.objects.filter(product__slug=slug, is_active=True).order_by(
                'sort_order', 'created_at'
            )[:15]
        )
    except Exception:  # noqa: BLE001
        pass

    review_summary = None
    if product_row is not None:
        try:
            cnt = product_row.review_count
            if cnt:
                avg = product_row.average_rating or 0
                review_summary = {
                    'count': cnt,
                    'avg': round(avg, 1),
                    'avg_int': int(avg),
                    'has_half': (avg - int(avg)) >= 0.5,
                }
        except Exception:  # noqa: BLE001
            pass

    # SEO meta — pass the Product instance as seo_object so SeoMeta
    # overrides + native model SEO fields + Product JSON-LD all light up.
    # Falls back to the GraphQL dict on the off-chance the row lookup
    # failed (resolve_meta is dict-safe).
    pdp_seo_obj = product_row if product_row is not None else product
    pdp_seo_image = ''
    if primary_image and primary_image.get('url'):
        pdp_seo_image = primary_image['url']
    elif hero_image and hero_image.get('url'):
        pdp_seo_image = hero_image['url']
    pdp_seo_description = _plain(
        product.get('shortDescription') or product.get('description') or ''
    )[:160]

    # Published Web Story for this product, if the webstories plugin is
    # installed and has a row. Resolved here (not in the template) because
    # `product` is a GraphQL dict, so dotted access can't traverse the
    # OneToOne reverse relation. Template uses `web_story` as the gate for
    # the <amp-story-player> embed block (no rel=amphtml — stories self-canonical).
    web_story = None
    if product_row is not None:
        try:
            ws = product_row.web_story
            if ws.is_published and ws.panels:
                web_story = ws
        except Exception:  # noqa: BLE001 — RelatedObjectDoesNotExist or plugin missing
            web_story = None

    # Stock gate for the "Notify me when back in stock" form on the PDP.
    # True iff inventory tracking is on AND no variant has any available
    # stock anywhere. Falls quietly to False if the inventory plugin
    # isn't installed (no stock_levels relation).
    out_of_stock = False
    if product_row is not None and getattr(product_row, 'track_inventory', False):
        try:
            from plugins.installed.catalog.models import (  # noqa: PLC0415
                ProductVariant,
            )

            has_stock = (
                ProductVariant.objects.filter(product=product_row, stock_levels__quantity__gt=0)
                .only('id')
                .exists()
            )
            out_of_stock = not has_stock
        except Exception:  # noqa: BLE001
            out_of_stock = False

    product_codes = _product_codes(product_row)
    reviews_list = _published_reviews(slug, product_row=product_row)
    book_jsonld_data = _book_jsonld_data(product_row, product, product_codes, out_of_stock)
    product_seo_extra = _product_seo_extra(
        product_row, primary_image, hero_image, review_summary, reviews_list
    )
    video_seo = _video_seo_data(videos, product)

    return render(
        request,
        'storefront/product_detail.html',
        {
            'product': product,
            'book_jsonld_data': book_jsonld_data,
            'product_seo_extra': product_seo_extra,
            'video_seo': video_seo,
            'pdp_vendor': pdp_vendor,
            'review_summary': review_summary,
            'images': images,
            'hero_image': hero_image,
            'primary_image': primary_image,
            'primary_images': primary_images,
            'videos': videos,
            'related_products': related,
            'book_specs': _book_specs(slug),
            'product_codes': product_codes,
            'reviews': reviews_list,
            'pdp_faqs': _pdp_faqs(slug, product_row=product_row),
            'breadcrumb_items': breadcrumb_items,
            'last_reviewed': last_reviewed,
            'active_pdp_edit_url': active_pdp_edit_url,
            'web_story': web_story,
            'out_of_stock': out_of_stock,
            'seo_object': pdp_seo_obj,
            'seo_title': product.get('name') or '',
            'seo_description': pdp_seo_description,
            'seo_image': pdp_seo_image,
            'seo_og_type': 'product',
        },
    )


def _pdp_faqs(slug: str, *, product_row=None) -> list[dict]:
    """Return ``[{q, a}, ...]`` from the seo.pdp_faqs metafield, or []."""
    try:
        from plugins.installed.catalog.models import Product
        from plugins.installed.metafields.models import Metafield
    except Exception:  # noqa: BLE001
        return []
    try:
        product = product_row or Product.objects.filter(slug=slug).first()
        if product is None:
            return []
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(Product)
        mf = Metafield.objects.filter(
            content_type=ct,
            object_id=str(product.pk),
            namespace='seo',
            key='pdp_faqs',
        ).first()
    except Exception:  # noqa: BLE001
        return []
    if mf is None or not mf.value:
        return []
    import json as _json

    try:
        data = _json.loads(mf.value)
    except (ValueError, TypeError):
        return []
    out = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            q = (item.get('q') or '').strip()
            a = (item.get('a') or '').strip()
            if q and a:
                out.append({'q': q, 'a': a})
    return out


def _published_reviews(slug: str, limit: int = 4, *, product_row=None) -> list[dict]:
    """Return ``[{stars, body, author_name, created_at}, ...]`` for the PDP."""
    try:
        from plugins.installed.catalog.models import Product, Review
    except Exception:  # noqa: BLE001
        return []
    try:
        product = product_row or Product.objects.filter(slug=slug).first()
        if product is None:
            return []
        rows = (
            Review.objects.filter(product=product, is_approved=True)
            .select_related('customer')
            .order_by('-created_at')[:limit]
        )
    except Exception:  # noqa: BLE001
        return []
    out = []
    for r in rows:
        full_name = ''
        if r.customer is not None:
            full_name = (r.customer.get_full_name() or r.customer.email.split('@')[0]).strip()
        out.append(
            {
                'stars': '★' * r.rating + '☆' * (5 - r.rating),
                'body': r.body,
                'author_name': full_name or 'A reader',
                'created_at': r.created_at,
            }
        )
    return out


# Book-specific metafields rendered as a clean Specifications card on the PDP.
_BOOK_SPEC_FIELDS = (
    ('author', 'Author', 'author'),
    ('publisher', 'Publisher', 'publisher'),
    ('published_year', 'Year', ''),
    ('format', 'Format', ''),
    ('pages', 'Pages', ''),
    ('language', 'Language', ''),
)


def _product_codes(product_row) -> list[dict]:
    """Product identifier codes (ISBN/EAN/GTIN/UPC/MPN/ASIN) for the PDP."""
    try:
        from plugins.installed.metafields.identifiers import product_identifiers

        return product_identifiers(product_row)
    except Exception:  # noqa: BLE001
        return []


def _product_seo_extra(product_row, primary_image, hero_image, review_summary, reviews):
    """SAFE-assembled Product JSON-LD enrichments (image / aggregateRating /
    brand / review) for the dict path. Reads aggregates + relations + the
    GraphQL image dict only — never the product's deferred price field.
    """
    extra: dict = {}
    img = primary_image or hero_image or {}
    if isinstance(img, dict) and img.get('url'):
        extra['image'] = img['url']
    if review_summary and review_summary.get('count'):
        extra['aggregate_rating'] = {
            'value': review_summary.get('avg'),
            'count': review_summary['count'],
        }
        extra['reviews'] = [
            {
                'rating': r.get('stars'),
                'author': r.get('author_name'),
                'body': r.get('body'),
                'date': r.get('created_at'),
            }
            for r in (reviews or [])[:5]
            if r.get('stars')
        ]
    if product_row is not None:
        try:
            from plugins.installed.book_product.compat import book_attrs

            pub = (book_attrs(product_row) or {}).get('publisher')
            if pub:
                extra['brand'] = str(pub)
        except Exception:  # noqa: BLE001
            pass
    return extra or None


def _video_seo_data(videos, product):
    """Plain dicts for VideoObject JSON-LD from ProductVideo rows. Needs a
    poster (Google requires a thumbnail); description falls back to the title
    or product name so the required field is never empty."""
    fallback_name = (product.get('name') if isinstance(product, dict) else '') or 'Video'
    out = []
    for v in videos or []:
        poster = getattr(v, 'poster_url', '') or ''
        if not poster:
            continue
        title = (getattr(v, 'title', '') or '').strip()
        out.append(
            {
                'name': title or fallback_name,
                'description': title or fallback_name,
                'thumbnail_url': poster,
                'upload_date': getattr(v, 'created_at', None),
                'content_url': getattr(v, 'url', '') or '',
            }
        )
    return out


def _book_jsonld_data(product_row, product, product_codes, out_of_stock):
    """Assemble the plain dict for ``{% seo_book_jsonld %}`` from SAFE sources.

    Book attributes + identifiers come from relation queries keyed on the
    product PK (never the product's *deferred* Money/price field, which would
    KeyError); price comes from the GraphQL ``product`` dict. Returns None when
    there's no author — a Book Work needs a title + author to be valid.
    """
    if product_row is None or not isinstance(product, dict):
        return None
    try:
        from plugins.installed.book_product.compat import book_attrs

        ba = book_attrs(product_row)
    except Exception:  # noqa: BLE001
        return None
    author = str(ba.get('author') or '').strip()
    if not author:
        return None
    codes = {c.get('key'): c.get('value') for c in (product_codes or [])}
    price = product.get('price') if isinstance(product.get('price'), dict) else {}
    # Reconciliation identifiers for public-domain works (no own ISBN): the
    # Open Library work id → sameAs, and the OCLC number → edition identifier.
    # Both live in the 'book' metafield namespace (surfaced by book_attrs).
    olid = str(ba.get('openlibrary') or '').strip()
    same_as = []
    if olid:
        same_as.append(f'https://openlibrary.org/works/{olid}' if olid.startswith('OL') else olid)
    return {
        'name': product.get('name') or '',
        'path': f'/products/{product.get("slug") or product_row.slug}/',
        'authors': [a.strip() for a in author.replace(';', ',').split(',') if a.strip()],
        'isbn13': codes.get('isbn13'),
        'isbn10': codes.get('isbn10'),
        'oclc': ba.get('oclc'),
        'same_as': same_as,
        'book_format': ba.get('format'),
        'language': ba.get('language'),
        'date_published': ba.get('published_year'),
        'edition': ba.get('edition'),
        'price': price.get('amount'),
        'currency': price.get('currency') or 'USD',
    }


def _book_specs(slug: str) -> list[dict]:
    """Book attributes for the PDP ``[{label, value, link?}, ...]``.

    Reads the BookProduct **model** first (the book_product plugin); falls back
    to the legacy ``book.*`` metafields only when no BookProduct row exists.
    Both paths are lazy + fail-soft.
    """
    from urllib.parse import urlencode

    from django.utils.text import slugify

    model_specs = _book_specs_from_model(slug, slugify, urlencode)
    if model_specs is not None:
        return model_specs
    return _book_specs_from_metafields(slug, slugify, urlencode)


def _book_specs_from_model(slug, slugify, urlencode):  # noqa: PLR0911 — flat field map
    try:
        from plugins.installed.book_product.models import BookProduct
    except Exception:  # noqa: BLE001 — plugin absent
        return None
    try:
        book = BookProduct.objects.select_related('product').filter(product__slug=slug).first()
    except Exception:  # noqa: BLE001
        return None
    if book is None:
        return None

    # Each value links to its facet landing page (book_product) — the PDP's
    # book attributes are browsable like categories.
    def _link(prefix, val):
        return f'/{prefix}/{slugify(val)}/' if val else ''

    series = f'{book.series} ({book.series_position})' if book.series_position else book.series
    rows = [
        ('Author', book.author, _link('author', book.author)),
        ('Publisher', book.publisher, _link('publisher', book.publisher)),
        ('Imprint', book.imprint, _link('imprint', book.imprint)),
        ('Published', book.publication_date.strftime('%B %Y') if book.publication_date else '', ''),
        (
            'Format',
            book.get_print_type_display() if book.print_type else '',
            f'/format/{book.print_type}/' if book.print_type else '',
        ),
        ('Paper', book.get_paper_type_display() if book.paper_type else '', ''),
        ('Pages', str(book.page_count) if book.page_count else '', ''),
        ('Language', book.language, f'/language/{book.language}/' if book.language else ''),
        ('Edition', book.edition, ''),
        ('Series', series, _link('series', book.series)),
    ]
    return [
        {'label': lbl, 'value': str(val), 'link': link}
        for lbl, val, link in rows
        if val not in (None, '')
    ]


def _book_specs_from_metafields(slug, slugify, urlencode):
    try:
        from plugins.installed.catalog.models import Product
        from plugins.installed.metafields.models import Metafield

        product = Product.objects.filter(slug=slug).first()
        if product is None:
            return []
        meta = Metafield.objects.for_obj(product, ns='book')
    except Exception:  # noqa: BLE001
        return []
    out = []
    for key, label, link_kind in _BOOK_SPEC_FIELDS:
        value = meta.get(f'book.{key}') or meta.get(key)
        if value in (None, ''):
            continue
        spec = {'label': label, 'value': str(value), 'link': ''}
        if link_kind == 'author':
            spec['link'] = f'/author/{slugify(str(value))}/'
        elif link_kind == 'publisher':
            spec['link'] = '/products/?' + urlencode({'publisher': str(value)})
        out.append(spec)
    return out


def _related_products(current_slug: str, limit: int = 4, *, request=None) -> list[dict]:
    """'You might also like' for the PDP — candidates contributed by
    ai_assistant via SIMILAR_PRODUCTS, reordered per visitor. No subscriber
    (plugin disabled) → [] and the section self-hides."""
    try:
        from core.hooks import MorpheusEvents, hook_registry
        from plugins.installed.catalog.models import Product

        product = Product.objects.filter(slug=current_slug).first()
        if product is None:
            return []
        rows = hook_registry.filter(
            MorpheusEvents.SIMILAR_PRODUCTS, [], product=product, limit=limit
        )
        if request is not None and rows:
            rows = hook_registry.filter(
                MorpheusEvents.PRODUCT_LIST_REORDER,
                value=list(rows),
                request=request,
                surface='related',
            )
    except Exception:  # noqa: BLE001
        return []
    out = []
    for p in rows:
        primary = p.primary_image
        out.append(
            {
                'id': str(p.id),
                'name': p.name,
                'slug': p.slug,
                'price': {'amount': str(p.price.amount), 'currency': str(p.price.currency)}
                if p.price
                else None,
                'primaryImage': {
                    'url': primary.image.url if primary and primary.image else '',
                    'altText': (primary.alt_text or p.name) if primary else p.name,
                }
                if primary
                else None,
            }
        )
    return out


def search(request):
    q = request.GET.get('q', '').strip()
    use_semantic = request.GET.get('mode') == 'semantic'

    if q:
        # Server-side analytics: search.performed truth (ad-blocker-proof).
        try:
            from core.hooks import MorpheusEvents, hook_registry  # noqa: PLC0415

            hook_registry.fire(
                MorpheusEvents.SEARCH_PERFORMED,
                query=q,
                results_count=None,
                request=request,
            )
        except Exception:  # noqa: BLE001, S110
            pass

    # Plain keyword search bounces to /products/?q=… so it lands on the rich PLP.
    if not use_semantic:
        from django.shortcuts import redirect as _redirect

        target = f'/products/?q={q}' if q else '/products/'
        return _redirect(target)

    data = (
        internal_graphql(
            """
        query SemanticSearch($query: String!) {
          semanticSearch(query: $query) {
            products { id name slug price { amount currency } primaryImage { url } }
            explanation
          }
        }
    """,
            variables={'query': q},
            request=request,
        )
        if q
        else None
    )
    result = (
        (data or {}).get('semanticSearch', {}) if data else {'products': [], 'explanation': None}
    )

    search_items = [
        {
            'name': p.get('name', ''),
            'url': request.build_absolute_uri(f'/products/{p.get("slug", "")}/'),
            'image': (p.get('primaryImage') or {}).get('url', ''),
        }
        for p in (result.get('products') or [])
    ]
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'Search', 'url': request.build_absolute_uri(request.path)},
    ]
    return render(
        request,
        'storefront/search.html',
        {
            'query': q,
            'result': result,
            'semantic': use_semantic,
            'search_items': search_items,
            'breadcrumb_items': breadcrumb_items,
            'seo_title': f'Search results for {q}' if q else 'Search — dot books',
            'seo_description': f'Results for "{q}" on the dot books shelf.'
            if q
            else 'Search the dot books shelf.',
        },
    )


# Editorial intros for genre landing pages. Category.description wins.
_CATEGORY_INTROS = {
    'fiction': {
        'eyebrow': 'On the shelf — fiction',
        'lede': "Contemporary literary novels we couldn't put down. Slow-burn debuts, "
        'patient experiments in form, and the occasional re-read of something we still mean.',
    },
    'nonfiction': {
        'eyebrow': 'On the shelf — non-fiction',
        'lede': 'Subject-matter we wanted to live with for a week. Cultural history, science writing '
        "that earns its metaphors, and ideas books that don't mistake length for depth.",
    },
    'poetry': {
        'eyebrow': 'On the shelf — poetry',
        'lede': 'Pamphlets, debut collections, and chapbook-thin volumes you can finish in a sitting '
        'and reopen for years. Read aloud at least once.',
    },
    'essays': {
        'eyebrow': 'On the shelf — essays',
        'lede': 'Long-form personal and cultural essays. The kind that show up in an annual best-of '
        'and earn the placement.',
    },
    'art-design': {
        'eyebrow': 'On the shelf — art & design',
        'lede': 'Monographs and field guides. Books that teach you how to look, then make you want to.',
    },
    'children': {
        'eyebrow': 'On the shelf — children',
        'lede': 'Picture books, board books, and early-reader stories that hold up to the 200-times test.',
    },
}


def _attach_book_authors(products) -> None:
    """Attach ``.author_name`` to each product for the card grid (no N+1).
    BookProduct model first; legacy book.author metafield fills any gaps."""
    for p in products:
        p.author_name = ''
    if not products:
        return
    by_id = {str(p.id): p for p in products}
    try:
        from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

        for pid, author in (
            BookProduct.objects.filter(product_id__in=list(by_id))
            .exclude(author='')
            .values_list('product_id', 'author')
        ):
            target = by_id.get(str(pid))
            if target is not None:
                target.author_name = author
    except Exception:  # noqa: BLE001
        pass
    missing = [pid for pid, p in by_id.items() if not p.author_name]
    if missing:
        try:
            from django.contrib.contenttypes.models import ContentType  # noqa: PLC0415
            from plugins.installed.catalog.models import Product  # noqa: PLC0415
            from plugins.installed.metafields.models import Metafield  # noqa: PLC0415

            ct = ContentType.objects.get_for_model(Product)
            for m in Metafield.objects.filter(
                content_type=ct, namespace='book', key='author', object_id__in=missing
            ):
                target = by_id.get(m.object_id)
                if target is not None and not target.author_name:
                    target.author_name = m.typed_value or ''
        except Exception:  # noqa: BLE001 — card metadata is best-effort
            pass


def category_detail(request, slug):
    """Category landing — products + editorial framing."""
    from morpheus.views import Http404
    from plugins.installed.catalog.models import Category, Product

    category = Category.objects.filter(slug=slug).first()
    if category is None:
        # Old genre-categories were migrated to /genre/<slug>/ — 301 so indexed
        # /category/<slug>/ URLs + bookmarks keep their link equity.
        from django.shortcuts import redirect  # noqa: PLC0415

        try:
            from plugins.installed.book_product.models import Genre  # noqa: PLC0415

            if Genre.objects.filter(slug=slug, is_active=True).exists():
                return redirect(f'/genre/{slug}/', permanent=True)
        except Exception:  # noqa: BLE001 — book_product may be disabled
            pass
        raise Http404
    # Include products whose PRIMARY category is this one OR whose
    # `additional_categories` M2M includes it (multi-category surface
    # support — keeps the primary category canonical for breadcrumbs
    # but lets a product cross-list under "Bestsellers" + "Children's"
    # etc.).
    from django.db.models import Q  # noqa: PLC0415

    sort = (request.GET.get('sort') or 'for_you').strip()
    sort_map = {
        'for_you': ('-is_featured', '-created_at'),
        'featured': ('-is_featured', '-created_at'),
        'newest': ('-created_at',),
        'price_asc': ('price',),
        'price_desc': ('-price',),
        'name': ('name',),
    }
    order = sort_map.get(sort, sort_map['for_you'])
    from django.core.paginator import Paginator  # noqa: PLC0415

    qs = (
        Product.objects.filter(status='active')
        .filter(Q(category=category) | Q(additional_categories=category))
        .select_related('category')
        .prefetch_related('images')  # primary_image hits this — avoid an N+1 per card
        .distinct()
        .order_by(*order)
    )
    page_obj = Paginator(qs, 24).get_page(request.GET.get('page') or 1)
    products = list(page_obj.object_list)

    if sort == 'for_you':
        products = hook_registry.filter(
            MorpheusEvents.PRODUCT_LIST_REORDER,
            value=products,
            request=request,
            surface='category_plp',
        )
        products = _surface_reorder(request, 'category_list', products)

    _attach_book_authors(products)
    intro = _CATEGORY_INTROS.get(slug, {})
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'All books', 'url': request.build_absolute_uri('/products/')},
        {'name': category.name, 'url': request.build_absolute_uri(request.path)},
    ]
    collection_items = [
        {
            'name': p.name,
            'url': request.build_absolute_uri(f'/products/{p.slug}/'),
            'image': (
                p.primary_image.image.url
                if p.primary_image and getattr(p.primary_image, 'image', None)
                else ''
            ),
        }
        for p in products[:30]
    ]
    # Staff admin-bar deep-link: edit this category in the dashboard.
    active_edit_url = ''
    if request.user.is_authenticated and request.user.is_staff:
        from django.urls import reverse  # noqa: PLC0415

        active_edit_url = reverse(
            'admin_dashboard:category_edit', kwargs={'category_id': category.pk}
        )
    return render(
        request,
        'storefront/category_detail.html',
        {
            'category': category,
            'active_edit_url': active_edit_url,
            'active_edit_label': 'Edit category',
            'products': products,
            'page_obj': page_obj,
            'sort': sort,
            'sort_options': [
                ('for_you', 'For You'),
                ('featured', 'Featured'),
                ('newest', 'Newest'),
                ('price_asc', 'Price: low to high'),
                ('price_desc', 'Price: high to low'),
                ('name', 'Title A–Z'),
            ],
            # Kind eyebrow — same vocabulary as the other shelf pages
            # (Collection / Genre / Author / Tag), was a convoluted
            # description-dependent expression that always said "On the shelf".
            'intro_eyebrow': intro.get('eyebrow', 'Category'),
            'intro_lede': category.description or intro.get('lede', ''),
            'breadcrumb_items': breadcrumb_items,
            'collection_items': collection_items,
            'seo_object': category,
            'seo_title': f'{category.name} — dot books',
            'seo_description': category.description or intro.get('lede', '')[:160],
            'seo_og_type': 'website',
        },
    )


def collection_detail(request, slug):
    """Collection landing page — clean SEO URL /collection/<slug>/ for a
    curated merchandising set (vs the hierarchical /category/<slug>/).
    Reuses category_detail.html (it only reads .name + .description,
    which Collection has)."""
    from morpheus.views import Http404
    from plugins.installed.catalog.models import Collection, Product

    collection = Collection.objects.filter(slug=slug, is_active=True).first()
    if collection is None:
        raise Http404
    sort = (request.GET.get('sort') or 'for_you').strip()
    sort_map = {
        'for_you': ('-is_featured', '-created_at'),
        'featured': ('-is_featured', '-created_at'),
        'newest': ('-created_at',),
        'price_asc': ('price',),
        'price_desc': ('-price',),
        'name': ('name',),
    }
    from django.core.paginator import Paginator  # noqa: PLC0415

    qs = (
        Product.objects.filter(status='active', collections=collection)
        .select_related('category')
        .prefetch_related('images')
        .order_by(*sort_map.get(sort, sort_map['for_you']))
    )
    page_obj = Paginator(qs, 24).get_page(request.GET.get('page') or 1)
    products = list(page_obj.object_list)

    if sort == 'for_you':
        products = hook_registry.filter(
            MorpheusEvents.PRODUCT_LIST_REORDER,
            value=products,
            request=request,
            surface='collection_plp',
        )
        products = _surface_reorder(request, 'collection_list', products)

    _attach_book_authors(products)
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'All books', 'url': request.build_absolute_uri('/products/')},
        {'name': collection.name, 'url': request.build_absolute_uri(request.path)},
    ]
    collection_items = [
        {
            'name': p.name,
            'url': request.build_absolute_uri(f'/products/{p.slug}/'),
            'image': (
                p.primary_image.image.url
                if p.primary_image and getattr(p.primary_image, 'image', None)
                else ''
            ),
        }
        for p in products[:30]
    ]
    # Staff admin-bar deep-link: edit this collection in the dashboard.
    active_edit_url = ''
    if request.user.is_authenticated and request.user.is_staff:
        from django.urls import reverse  # noqa: PLC0415

        active_edit_url = reverse(
            'admin_dashboard:collection_edit', kwargs={'collection_id': collection.pk}
        )
    return render(
        request,
        'storefront/category_detail.html',
        {
            'category': collection,
            'active_edit_url': active_edit_url,
            'active_edit_label': 'Edit collection',
            'products': products,
            'page_obj': page_obj,
            'sort': sort,
            'sort_options': [
                ('for_you', 'For You'),
                ('featured', 'Featured'),
                ('newest', 'Newest'),
                ('price_asc', 'Price: low to high'),
                ('price_desc', 'Price: high to low'),
                ('name', 'Title A–Z'),
            ],
            'intro_eyebrow': 'Collection',
            'intro_lede': collection.description or '',
            'breadcrumb_items': breadcrumb_items,
            'collection_items': collection_items,
            'seo_object': collection,
            'seo_title': f'{collection.name} — dot books',
            'seo_description': (collection.description or '')[:160],
            'seo_og_type': 'website',
        },
    )


def author_detail(request, slug):
    """Author landing page — bibliography + optional bio."""
    from morpheus.views import Http404

    author_name = ''
    bibliography = []
    try:
        from plugins.installed.book_product.compat import product_ids_for, resolve_slug
        from plugins.installed.catalog.models import Product

        match = resolve_slug('author', slug)
        if match is None:
            raise Http404
        author_name = match
        bibliography = list(
            Product.objects.filter(
                id__in=product_ids_for('author', match), status='active'
            ).order_by('-is_featured', '-created_at')
        )
    except Http404:
        raise
    except Exception:  # noqa: BLE001
        raise Http404

    # Per-visitor merchandising: surface the books this visitor is most likely
    # to buy first (no-op without consent/history/personalisation plugin).
    from core.hooks import MorpheusEvents, hook_registry

    bibliography = hook_registry.filter(
        MorpheusEvents.PRODUCT_LIST_REORDER, value=bibliography, request=request, surface='author'
    )

    bio_page = None
    try:
        from plugins.installed.cms.models import Page

        bio_page = Page.objects.filter(
            slug=f'author-{slug}', state='published', metadata__category='author'
        ).first()
    except Exception:  # noqa: BLE001
        pass

    bib_items = [
        {
            'name': p.name,
            'url': request.build_absolute_uri(f'/products/{p.slug}/'),
            'image': (
                p.primary_image.image.url
                if p.primary_image and getattr(p.primary_image, 'image', None)
                else ''
            ),
        }
        for p in bibliography[:30]
    ]
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'All books', 'url': request.build_absolute_uri('/products/')},
        {'name': author_name, 'url': request.build_absolute_uri(request.path)},
    ]
    # Merchant-editable per-author SEO + intro (Book taxonomies dashboard).
    book_term = None
    try:
        from plugins.installed.book_product.models import BookTaxonomyTerm

        book_term = BookTaxonomyTerm.objects.filter(taxonomy='author', slug=slug).first()
    except Exception:  # noqa: BLE001
        book_term = None
    default_desc = (
        bio_page.excerpt
        if bio_page and bio_page.excerpt
        else f'Books by {author_name}, on the dot books shelf.'
    )
    return render(
        request,
        'storefront/author_detail.html',
        {
            'author_name': author_name,
            'author_slug': slug,
            'bibliography': bibliography,
            'bib_items': bib_items,
            'breadcrumb_items': breadcrumb_items,
            'bio_page': bio_page,
            'book_term': book_term,
            'seo_title': (
                book_term.meta_title
                if book_term and book_term.meta_title
                else f'{author_name} — dot books'
            ),
            'seo_description': (
                book_term.meta_description
                if book_term and book_term.meta_description
                else default_desc
            )[:160],
            'seo_og_type': 'profile',
        },
    )


def staff_picks(request):
    """Curated staff picks — Collection-backed."""
    from plugins.installed.catalog.models import Collection, Product

    collection = (
        Collection.objects.filter(slug='staff-picks', is_active=True).first()
        or Collection.objects.filter(slug='editors-pick-april', is_active=True).first()
    )
    products = []
    if collection is not None:
        products = list(
            Product.objects.filter(status='active', collections=collection).order_by(
                '-is_featured', '-created_at'
            )[:30]
        )
    description = (
        collection.description
        if collection and collection.description
        else 'A small rotating shelf of titles we’d hand a friend without hesitation.'
    )
    pick_items = [
        {
            'name': p.name,
            'url': request.build_absolute_uri(f'/products/{p.slug}/'),
            'image': (
                p.primary_image.image.url
                if p.primary_image and getattr(p.primary_image, 'image', None)
                else ''
            ),
        }
        for p in products[:30]
    ]
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'Staff picks', 'url': request.build_absolute_uri(request.path)},
    ]
    return render(
        request,
        'storefront/staff_picks.html',
        {
            'collection': collection,
            'products': products,
            'pick_items': pick_items,
            'breadcrumb_items': breadcrumb_items,
            'seo_object': collection,
            'seo_title': 'Staff picks — dot books',
            'seo_description': description[:160],
            'seo_og_type': 'website',
        },
    )


def categories(request):
    # Categories were collapsed to a single "Books" root; genres are the browse
    # axis now. 301 the old index to /genres/ to preserve SEO + bookmarks.
    from django.shortcuts import redirect  # noqa: PLC0415

    return redirect('/genres/', permanent=True)


def quick_search(request):
    """Lightweight JSON endpoint for the topbar quick-results dropdown.
    Returns up to 6 matches; empty array for queries < 2 chars.
    """
    from django.http import JsonResponse
    from plugins.installed.catalog.models import Product

    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    try:
        qs = Product.objects.filter(status='active')
        qs = _apply_search(qs, q)
        rows = list(qs[:6])
    except Exception:  # noqa: BLE001
        rows = []

    results = []
    for p in rows:
        img = ''
        primary = p.primary_image
        if primary and getattr(primary, 'image', None):
            try:
                img = primary.image.url
            except Exception:  # noqa: BLE001
                img = ''
        price_str = ''
        if p.price:
            try:
                price_str = (
                    f'${p.price.amount:.2f}'
                    if str(p.price.currency) == 'USD'
                    else f'{p.price.currency} {p.price.amount}'
                )
            except Exception:  # noqa: BLE001
                price_str = ''
        results.append(
            {
                'id': str(p.id),
                'name': p.name,
                'slug': p.slug,
                'price': price_str,
                'image_url': img,
            }
        )
    return JsonResponse({'results': results})
