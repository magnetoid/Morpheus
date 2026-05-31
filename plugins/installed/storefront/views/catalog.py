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
from morpheus.views import render

from ._queries import PRODUCT_DETAIL_QUERY


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

    # Collection filter — `?collection=<slug>` (curated merchandising sets;
    # the PDP "Featured in" chips link here so a shopper can browse the set).
    col_slug = (request.GET.get('collection') or '').strip()
    if col_slug:
        qs = qs.filter(collections__slug=col_slug)

    # Tag filter
    tag_slug = (request.GET.get('tag') or '').strip()
    if tag_slug:
        qs = qs.filter(tags__name__iexact=tag_slug)

    # Book metafield filters — `?author=Hanna Rieder`, `?publisher=Pelican Press`.
    book_filter = {}
    for qk in ('author', 'publisher'):
        v = (request.GET.get(qk) or '').strip()
        if v:
            book_filter[qk] = v
    if book_filter:
        try:
            from django.contrib.contenttypes.models import ContentType
            from plugins.installed.metafields.models import Metafield

            ct = ContentType.objects.get_for_model(Product)
            for qk, v in book_filter.items():
                ids = Metafield.objects.filter(
                    content_type=ct,
                    namespace='book',
                    key=qk,
                    value__iexact=v,
                ).values_list('object_id', flat=True)
                qs = qs.filter(id__in=list(ids))
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
    sort = (request.GET.get('sort') or 'newest').strip()
    sort_map = {
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

    # Query-string base for pagination links — drops `page` so the template
    # can append it cleanly while preserving every active filter (search,
    # category, collection, tag, author, sort, attribute facets, …).
    _qs_no_page = request.GET.copy()
    _qs_no_page.pop('page', None)
    paginator_base_qs = _qs_no_page.urlencode()

    categories_list = list(Category.objects.filter(parent__isnull=True).order_by('name'))

    # Author facet — distinct values from book.author metafields.
    available_authors: list[str] = []
    try:
        from django.contrib.contenttypes.models import ContentType
        from plugins.installed.metafields.models import Metafield

        ct = ContentType.objects.get_for_model(Product)
        available_authors = sorted(
            set(
                Metafield.objects.filter(content_type=ct, namespace='book', key='author')
                .exclude(value='')
                .values_list('value', flat=True)
            )
        )
    except Exception:  # noqa: BLE001
        pass

    selected_cat = next((c for c in categories_list if c.slug == cat_slug), None)
    plp_name = selected_cat.name if selected_cat else 'All books'
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
                selected_cat.description
                if selected_cat and selected_cat.description
                else 'The full dot books shelf — independent press, curated by readers.'
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
    from plugins.installed.ai_assistant.services.search import hybrid_search  # noqa: PLC0415
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
    hybrid_products = hybrid_search(q, top_k=80) if not typesense_ids else []
    hybrid_ids = [p.pk for p in hybrid_products]

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

    related = _related_products(slug)
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
    pdp_seo_description = (product.get('shortDescription') or product.get('description') or '')[
        :160
    ].strip()

    # Published Web Story for this product, if the webstories plugin is
    # installed and has a row. Resolved here (not in the template) because
    # `product` is a GraphQL dict, so dotted access can't traverse the
    # OneToOne reverse relation. Template uses `web_story` as the gate for
    # the <link rel="amphtml"> tag and the <amp-story-player> block.
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

    return render(
        request,
        'storefront/product_detail.html',
        {
            'product': product,
            'pdp_vendor': pdp_vendor,
            'review_summary': review_summary,
            'images': images,
            'hero_image': hero_image,
            'primary_image': primary_image,
            'primary_images': primary_images,
            'videos': videos,
            'related_products': related,
            'book_specs': _book_specs(slug),
            'reviews': _published_reviews(slug, product_row=product_row),
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
    ('isbn', 'ISBN', ''),
)


def _book_specs(slug: str) -> list[dict]:
    """Return ``[{label, value, link?}, ...]`` of book metafields for the PDP."""
    try:
        from plugins.installed.catalog.models import Product
        from plugins.installed.metafields.models import Metafield
    except Exception:  # noqa: BLE001
        return []
    try:
        product = Product.objects.filter(slug=slug).first()
        if product is None:
            return []
        meta = Metafield.objects.for_obj(product, ns='book')
    except Exception:  # noqa: BLE001
        return []
    from urllib.parse import urlencode
    from django.utils.text import slugify

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


def _related_products(current_slug: str, limit: int = 4) -> list[dict]:
    """AI-driven 'you might also like' for the PDP."""
    try:
        from plugins.installed.ai_assistant.services.recommendations import similar_to
        from plugins.installed.catalog.models import Product
    except Exception:  # noqa: BLE001
        return []
    try:
        product = Product.objects.filter(slug=current_slug).first()
        if product is None:
            return []
        rows = similar_to(product, limit=limit)
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


def category_detail(request, slug):
    """Category landing — products + editorial framing."""
    from morpheus.views import Http404
    from plugins.installed.catalog.models import Category, Product

    category = Category.objects.filter(slug=slug).first()
    if category is None:
        raise Http404
    # Include products whose PRIMARY category is this one OR whose
    # `additional_categories` M2M includes it (multi-category surface
    # support — keeps the primary category canonical for breadcrumbs
    # but lets a product cross-list under "Bestsellers" + "Children's"
    # etc.).
    from django.db.models import Q  # noqa: PLC0415

    products = list(
        Product.objects.filter(status='active')
        .filter(Q(category=category) | Q(additional_categories=category))
        .select_related('category')
        .distinct()
        .order_by('-is_featured', '-created_at')[:60]
    )
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
    return render(
        request,
        'storefront/category_detail.html',
        {
            'category': category,
            'products': products,
            'intro_eyebrow': category.description
            and 'On the shelf'
            or intro.get('eyebrow', 'On the shelf'),
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
    products = list(
        Product.objects.filter(status='active', collections=collection)
        .select_related('category')
        .order_by('-is_featured', '-created_at')[:60]
    )
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
    return render(
        request,
        'storefront/category_detail.html',
        {
            'category': collection,
            'products': products,
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
    from django.utils.text import slugify

    author_name = ''
    bibliography = []
    try:
        from django.contrib.contenttypes.models import ContentType
        from plugins.installed.catalog.models import Product
        from plugins.installed.metafields.models import Metafield

        ct = ContentType.objects.get_for_model(Product)
        names = (
            Metafield.objects.filter(content_type=ct, namespace='book', key='author')
            .exclude(value='')
            .values_list('value', flat=True)
            .distinct()
        )
        match = next((n for n in names if slugify(n) == slug), None)
        if match is None:
            raise Http404
        author_name = match
        product_ids = list(
            Metafield.objects.filter(
                content_type=ct,
                namespace='book',
                key='author',
                value__iexact=match,
            ).values_list('object_id', flat=True)
        )
        bibliography = list(
            Product.objects.filter(id__in=product_ids, status='active').order_by(
                '-is_featured', '-created_at'
            )
        )
    except Http404:
        raise
    except Exception:  # noqa: BLE001
        raise Http404

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
            'seo_title': f'{author_name} — dot books',
            'seo_description': (
                bio_page.excerpt
                if bio_page and bio_page.excerpt
                else f'Books by {author_name}, on the dot books shelf.'
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
    data = (
        internal_graphql(
            """
        query Categories {
          categories(topLevel: true, first: 50) {
            id name slug image { url }
          }
        }
    """,
            request=request,
        )
        or {}
    )
    cats = data.get('categories', [])
    cat_items = [
        {
            'name': c.get('name', ''),
            'url': request.build_absolute_uri(f'/products/?category={c.get("slug", "")}'),
            'image': (c.get('image') or {}).get('url', ''),
        }
        for c in cats
    ]
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'Categories', 'url': request.build_absolute_uri(request.path)},
    ]
    return render(
        request,
        'storefront/categories.html',
        {
            'categories': cats,
            'cat_items': cat_items,
            'breadcrumb_items': breadcrumb_items,
            'seo_title': 'Categories — dot books',
            'seo_description': "All categories on the dot books shelf — fiction, non-fiction, poetry, essays, art & design, children's.",
            'seo_og_type': 'website',
        },
    )


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
