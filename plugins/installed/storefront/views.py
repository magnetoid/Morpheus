"""
Storefront Plugin — Views
Consumes the GraphQL API via internal_graphql(). Never touches ORM directly.
"""
from morpheus.views import render, redirect
from api.client import internal_graphql


PRODUCT_LIST_QUERY = """
query ProductList($first: Int!, $search: String, $category: String) {
  products(first: $first, search: $search, category: $category) {
    id name slug price { amount currency }
    compareAtPrice { amount }
    primaryImage { url altText }
    isOnSale discountPercentage
    averageRating
  }
}
"""

PRODUCT_DETAIL_QUERY = """
query ProductDetail($slug: String!) {
  product(slug: $slug) {
    id name slug description shortDescription
    price { amount currency }
    compareAtPrice { amount }
    images { url altText isPrimary }
    variants { id name sku price { amount currency } isActive }
    tags category { name slug }
    averageRating
    reviews { rating title body customer { fullName } createdAt }
  }
}
"""

CART_QUERY = """
query Cart {
  cart {
    id itemCount subtotal { amount currency }
    items {
      id quantity unitPrice { amount currency } totalPrice { amount currency }
      product { name slug primaryImage { url } }
      variant { name sku }
    }
    coupon { code discountType discountValue }
    giftCard { code balance currency }
  }
}
"""


def home(request):
    data = internal_graphql("""
        query Home {
          featuredProducts: products(first: 8, featured: true) {
            id name slug price { amount currency }
            primaryImage { url altText }
            isOnSale discountPercentage
          }
          collections(featured: true, first: 6) {
            id name slug image { url }
          }
          categories(topLevel: true, first: 8) {
            id name slug image { url }
          }
        }
    """, request=request) or {}
    # Templates use snake_case; GraphQL returns camelCase. Normalise.
    data.setdefault('featured_products', data.get('featuredProducts', []) or [])
    data.setdefault('seasonal_products', data.get('featured_products', []))

    # Staff picks rail — same fallback chain as the dedicated /staff-picks/ page.
    try:
        from plugins.installed.catalog.models import Collection, Product
        sp_collection = (
            Collection.objects.filter(slug='staff-picks', is_active=True).first()
            or Collection.objects.filter(slug='editors-pick-april', is_active=True).first()
        )
        sp_products = list(
            Product.objects.filter(status='active', collections=sp_collection)
            .order_by('-is_featured', '-created_at')[:8]
        ) if sp_collection else []
    except Exception:  # noqa: BLE001
        sp_collection, sp_products = None, []
    data['staff_picks_collection'] = sp_collection
    data['staff_picks'] = sp_products

    return render(request, 'storefront/home.html', data)


def product_list(request):
    """Product list with merchant-friendly facets: category, tag, price range,
    attribute facets (size/color/brand/...), and sort."""
    from decimal import Decimal, InvalidOperation
    from django.db.models import Q
    from plugins.installed.catalog.models import (
        Attribute, AttributeValue, Category, Product,
    )

    qs = Product.objects.filter(status='active').select_related('category')

    # Search — Postgres full-text on Postgres backends, LIKE fallback elsewhere.
    q = (request.GET.get('q') or '').strip()
    if q:
        qs = _apply_search(qs, q)

    # Category filter
    cat_slug = (request.GET.get('category') or '').strip()
    if cat_slug:
        qs = qs.filter(category__slug=cat_slug)

    # Tag filter
    tag_slug = (request.GET.get('tag') or '').strip()
    if tag_slug:
        qs = qs.filter(tags__name__iexact=tag_slug)

    # Book metafield filters — `?author=Hanna Rieder`, `?publisher=Pelican Press`.
    # We narrow the queryset to products whose Metafield in namespace 'book'
    # matches the requested value (case-insensitive). Any failure (plugin
    # missing, table absent) is swallowed — the filter just becomes a no-op.
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
                    content_type=ct, namespace='book', key=qk, value__iexact=v,
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

    # Attribute facets — `?attr_<slug>=value1,value2` (comma-separated).
    # We OR within an attribute (red OR blue), AND across attributes
    # (red shoes AND size 10) — standard ecommerce facet behaviour.
    selected_attrs: dict[str, list[str]] = {}
    for key, raw in request.GET.lists():
        if not key.startswith('attr_'):
            continue
        attr_slug = key[len('attr_'):]
        values = [v for chunk in raw for v in (chunk.split(',') if isinstance(chunk, str) else []) if v]
        if not values:
            continue
        selected_attrs[attr_slug] = values
        # Each attribute filter narrows the queryset. We match against either
        # product-level ProductAttribute or variant-level ProductVariant.
        q_obj = (
            Q(productattribute__attribute__slug=attr_slug,
              productattribute__values__slug__in=values)
            | Q(variants__attribute_values__attribute__slug=attr_slug,
                variants__attribute_values__slug__in=values)
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

    # Build facet panel. For each filterable Attribute, list the values that
    # actually appear among products matching every OTHER filter (so each
    # facet stays meaningful when narrowed by other facets).
    facet_attributes = list(
        Attribute.objects.filter(is_filterable=True)
        .order_by('sort_order', 'name')
    )
    facets = []
    for attr in facet_attributes:
        # Values that appear in the current filtered set, via either
        # product or variant link. distinct() avoids dupes.
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
            AttributeValue.objects
            .filter(id__in=value_ids)
            .order_by('sort_order', 'name')
        )
        facets.append({
            'attr': attr,
            'values': values,
            'selected': set(selected_attrs.get(attr.slug, [])),
        })

    products = list(qs[:60])
    categories = list(Category.objects.filter(parent__isnull=True).order_by('name'))

    # Author facet — distinct values from book.author metafields, alphabetised.
    # Cheap on this catalog size; defer to a cached top-N query if it grows.
    available_authors: list[str] = []
    try:
        from django.contrib.contenttypes.models import ContentType
        from plugins.installed.metafields.models import Metafield
        ct = ContentType.objects.get_for_model(Product)
        available_authors = sorted(set(
            Metafield.objects.filter(content_type=ct, namespace='book', key='author')
            .exclude(value='')
            .values_list('value', flat=True)
        ))
    except Exception:  # noqa: BLE001
        pass

    return render(request, 'storefront/product_list.html', {
        'products': products,
        'categories': categories,
        'facets': facets,
        'available_authors': available_authors,
        'search_query': q,
        'selected_category': cat_slug,
        'selected_category_obj': next((c for c in categories if c.slug == cat_slug), None),
        'selected_tag': tag_slug,
        'selected_author': book_filter.get('author', ''),
        'selected_publisher': book_filter.get('publisher', ''),
        'selected_sort': sort,
        'price_min': pmin or '',
        'price_max': pmax or '',
    })


def _apply_search(qs, q: str):
    """Hybrid retrieval (BM25 + dense embeddings, RRF-fused) with a
    metafield + SKU union for book-specific identifiers.

    The ``hybrid_search`` service handles BM25 / dense fusion and
    gracefully falls back to keyword search on non-Postgres setups or
    when no embeddings exist. We then union in metafield matches
    (``book.author`` / ``publisher`` / ``isbn``) and exact-SKU matches
    so identifier-style queries still resolve.

    Ranking: products in the hybrid result preserve their fused rank;
    metafield/SKU-only matches sit after them ordered by ``-created_at``.
    """
    from django.db.models import Case, IntegerField, Q, When
    from plugins.installed.ai_assistant.services.search import hybrid_search

    metafield_ids = list(_metafield_search_ids(q))
    hybrid_products = hybrid_search(q, top_k=80)
    hybrid_ids = [p.pk for p in hybrid_products]

    union_ids = list(dict.fromkeys(hybrid_ids + metafield_ids))
    if not union_ids:
        return qs.filter(Q(sku__iexact=q))

    filtered = qs.filter(Q(id__in=union_ids) | Q(sku__iexact=q))
    if not hybrid_ids:
        return filtered.order_by('-created_at')

    rank_cases = [When(pk=pid, then=idx) for idx, pid in enumerate(hybrid_ids)]
    return (
        filtered
        .annotate(_hybrid_rank=Case(
            *rank_cases,
            default=len(hybrid_ids) + 1,
            output_field=IntegerField(),
        ))
        .order_by('_hybrid_rank', '-created_at')
    )


def _metafield_search_ids(q: str) -> list:
    """Return product IDs whose book.author/publisher/isbn metafield contains q.
    Returns [] silently if metafields plugin is absent or queries fail."""
    try:
        from django.contrib.contenttypes.models import ContentType
        from plugins.installed.catalog.models import Product
        from plugins.installed.metafields.models import Metafield
        ct = ContentType.objects.get_for_model(Product)
        return list(Metafield.objects.filter(
            content_type=ct, namespace='book',
            key__in=('author', 'publisher', 'isbn'),
            value__icontains=q,
        ).values_list('object_id', flat=True))
    except Exception:  # noqa: BLE001
        return []


def product_detail(request, slug):
    data = internal_graphql(PRODUCT_DETAIL_QUERY, variables={'slug': slug}, request=request)
    product = (data or {}).get('product')
    if not product:
        from morpheus.views import Http404
        raise Http404
    related = _related_products(slug)
    breadcrumb_items = [{'name': 'Home', 'url': request.build_absolute_uri('/')}]
    breadcrumb_items.append({'name': 'All books', 'url': request.build_absolute_uri('/products/')})
    cat = (product or {}).get('category') or {}
    if cat.get('slug'):
        breadcrumb_items.append({
            'name': cat.get('name') or cat['slug'],
            'url': request.build_absolute_uri(f"/products/?category={cat['slug']}"),
        })
    breadcrumb_items.append({
        'name': product.get('name') or slug,
        'url': request.build_absolute_uri(request.path),
    })
    return render(request, 'storefront/product_detail.html', {
        'product': product,
        'related_products': related,
        'book_specs': _book_specs(slug),
        'reviews': _published_reviews(slug),
        'breadcrumb_items': breadcrumb_items,
    })


def _published_reviews(slug: str, limit: int = 4) -> list[dict]:
    """Return ``[{stars, body, author_name, created_at}, ...]`` for the PDP.
    Pre-computes the star string + author display so the template stays simple."""
    try:
        from plugins.installed.catalog.models import Product, Review
    except Exception:  # noqa: BLE001 — catalog plugin not installed
        return []
    try:
        product = Product.objects.filter(slug=slug).first()
        if product is None:
            return []
        rows = (Review.objects
                .filter(product=product, is_approved=True)
                .select_related('customer')
                .order_by('-created_at')[:limit])
    except Exception:  # noqa: BLE001
        return []
    out = []
    for r in rows:
        full_name = ''
        if r.customer is not None:
            full_name = (r.customer.get_full_name() or r.customer.email.split('@')[0]).strip()
        out.append({
            'stars': '★' * r.rating + '☆' * (5 - r.rating),
            'body': r.body,
            'author_name': full_name or 'A reader',
            'created_at': r.created_at,
        })
    return out


# Book-specific metafields rendered as a clean Specifications card on the PDP.
# Order is the display order; missing keys are skipped silently.
# The third tuple element controls how the value is linked:
#   'author'    → /author/<slugify(value)>/  (dedicated landing)
#   'publisher' → /products/?publisher=...
#   ''          → plain text, no link
_BOOK_SPEC_FIELDS = (
    ('author',         'Author',     'author'),
    ('publisher',      'Publisher',  'publisher'),
    ('published_year', 'Year',       ''),
    ('format',         'Format',     ''),
    ('pages',          'Pages',      ''),
    ('language',       'Language',   ''),
    ('isbn',           'ISBN',       ''),
)


def _book_specs(slug: str) -> list[dict]:
    """Return ``[{label, value, link?}, ...]`` of book metafields for the PDP.
    Fails closed — bad data never breaks the page."""
    try:
        from plugins.installed.catalog.models import Product
        from plugins.installed.metafields.models import Metafield
    except Exception:  # noqa: BLE001 — plugin not installed
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
    """AI-driven 'you might also like' for the PDP. Returns dicts shaped
    like the PRODUCT_LIST_QUERY rows so the template can reuse the card.
    Fails closed — recs never block the page."""
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
    except Exception:  # noqa: BLE001 — recs are non-essential
        return []
    out = []
    for p in rows:
        primary = p.primary_image
        out.append({
            'id': str(p.id),
            'name': p.name,
            'slug': p.slug,
            'price': {'amount': str(p.price.amount), 'currency': str(p.price.currency)} if p.price else None,
            'primaryImage': {
                'url': primary.image.url if primary and primary.image else '',
                'altText': (primary.alt_text or p.name) if primary else p.name,
            } if primary else None,
        })
    return out


def cart(request):
    data = internal_graphql(CART_QUERY, request=request)
    return render(request, 'storefront/cart.html', {'cart': (data or {}).get('cart', {})})


def cart_add(request, product_id):
    """Add a product to the cart.

    Returns JSON when called as ``X-Requested-With: fetch`` (the cart
    drawer drains the response into the slide-out). Falls back to a
    plain POST + redirect for users without JS or for the rare server
    fetch that fails.
    """
    from django.http import HttpResponseNotAllowed, JsonResponse

    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    quantity = max(1, int((request.POST.get('quantity') or '1').strip() or 1))
    variant_id = (request.POST.get('variant_id') or '').strip() or None

    is_xhr = (
        request.headers.get('X-Requested-With', '').lower() == 'fetch'
        or 'application/json' in request.headers.get('Accept', '')
    )

    mutation = """
    mutation Add($input: AddToCartInput!) {
      addToCart(input: $input) {
        cart {
          id itemCount subtotal { amount currency }
          items {
            id quantity
            unitPrice { amount currency }
            totalPrice { amount currency }
            product { name slug primaryImage { url } }
            variant { name }
          }
        }
        errors { code message }
      }
    }
    """
    variables = {
        'input': {
            'productId': str(product_id),
            'quantity': quantity,
            'variantId': variant_id,
            'sessionKey': request.session.session_key or '',
        },
    }
    data = internal_graphql(mutation, variables=variables, request=request) or {}
    payload = (data or {}).get('addToCart') or {}
    errors = payload.get('errors') or []

    if is_xhr:
        if errors:
            return JsonResponse(
                {'ok': False, 'error': errors[0].get('message', 'Add failed.')},
                status=400,
            )
        return JsonResponse({'ok': True, 'cart': payload.get('cart') or {}})

    if errors:
        # No JS: fall back to the cart page so the customer at least
        # sees what's there. Could surface the message via messages
        # framework once that's wired storefront-side.
        return redirect('/cart/')
    return redirect('/cart/')


def checkout(request):
    """Step 1 of the server-rendered checkout: contact + shipping address.

    Subsequent steps (`/checkout/shipping/`, `/checkout/review/`) live below.
    The legacy single-page JS checkout still renders if a theme overrides
    this template — we just pre-populate values from the visitor's session
    and an authenticated user when present.
    """
    if request.method == 'GET':
        ctx = _checkout_base_context(request)
        return render(request, 'storefront/checkout.html', ctx)
    # Save contact + shipping address into the session, then advance to
    # the shipping-method picker.
    fields = (
        'email', 'first_name', 'last_name', 'address_line1', 'address_line2',
        'city', 'state', 'postal_code', 'country', 'phone',
    )
    addr = {f: (request.POST.get(f) or '').strip() for f in fields}
    if not (addr['email'] and addr['address_line1'] and addr['city'] and addr['country']):
        ctx = _checkout_base_context(request)
        ctx['error'] = 'Please fill in email, address, city, and country.'
        ctx['form'] = addr
        return render(request, 'storefront/checkout.html', ctx)
    request.session['checkout_address'] = addr
    return redirect('/checkout/shipping/')


def checkout_apply_gift_card(request):
    """POST /checkout/gift-card/apply/ — runs the applyGiftCard mutation
    and bounces back to whichever step the user came from."""
    if request.method != 'POST':
        return redirect('/checkout/')
    code = (request.POST.get('code') or '').strip().upper()
    cart_id = request.session.get('cart_id') or ''
    if cart_id and code:
        mutation = """
        mutation Apply($input: ApplyGiftCardInput!) {
          applyGiftCard(input: $input) { errors { code message } }
        }
        """
        internal_graphql(
            mutation,
            variables={'input': {'cartId': cart_id, 'code': code}},
            request=request,
        )
    back = request.META.get('HTTP_REFERER', '/checkout/') or '/checkout/'
    return redirect(back)


def checkout_remove_gift_card(request):
    """POST /checkout/gift-card/remove/ — clears the applied card."""
    if request.method != 'POST':
        return redirect('/checkout/')
    cart_id = request.session.get('cart_id') or ''
    if cart_id:
        mutation = """
        mutation Remove($input: ApplyGiftCardInput!) {
          removeGiftCard(input: $input) { errors { code message } }
        }
        """
        internal_graphql(
            mutation,
            variables={'input': {'cartId': cart_id, 'code': ''}},
            request=request,
        )
    back = request.META.get('HTTP_REFERER', '/checkout/') or '/checkout/'
    return redirect(back)


def _checkout_base_context(request):
    """Common context every checkout step uses — cart summary + saved form values."""
    cart_data = internal_graphql(CART_QUERY, request=request) or {}
    saved = request.session.get('checkout_address') or {}
    user = getattr(request, 'user', None)
    if not saved and user is not None and getattr(user, 'is_authenticated', False):
        saved = {
            'email': getattr(user, 'email', '') or '',
            'first_name': getattr(user, 'first_name', '') or '',
            'last_name': getattr(user, 'last_name', '') or '',
        }
    return {
        'cart': cart_data.get('cart') or {},
        'form': saved,
    }


def checkout_shipping(request):
    """Step 2: pick a shipping rate."""
    addr = request.session.get('checkout_address')
    if not addr:
        return redirect('/checkout/')
    cart_data = internal_graphql(CART_QUERY, request=request) or {}
    cart = cart_data.get('cart') or {}

    rates = _available_shipping_rates(request, addr)

    if request.method == 'POST':
        rate_id = (request.POST.get('shipping_rate_id') or '').strip()
        if not rate_id and rates:
            rate_id = str(rates[0]['id'])
        request.session['checkout_shipping_rate_id'] = rate_id
        request.session['checkout_shipping_rate_label'] = next(
            (r['label'] for r in rates if str(r['id']) == rate_id), '',
        )
        return redirect('/checkout/review/')

    return render(request, 'storefront/checkout_shipping.html', {
        'cart': cart,
        'address': addr,
        'rates': rates,
        'selected_rate_id': request.session.get('checkout_shipping_rate_id', ''),
    })


def _available_shipping_rates(request, addr):
    """Compute shipping rates for the resolved address. Falls back to a
    single 'Standard — Free' option when the shipping plugin isn't wired."""
    try:
        from plugins.installed.shipping.services import compute_rates
        from plugins.installed.orders.models import Cart
        cart_id = request.session.get('cart_id')
        cart = Cart.objects.filter(id=cart_id).first() if cart_id else None
        if cart is None:
            return []
        rates = compute_rates(cart=cart, address=addr) or []
        return [
            {
                'id': r.get('id') or r.get('rate_id') or r.get('name') or 'standard',
                'label': r.get('name') or r.get('label') or 'Standard',
                'amount': r.get('amount') or r.get('price') or 0,
                'currency': r.get('currency') or 'USD',
            }
            for r in rates
        ]
    except Exception:  # noqa: BLE001 — shipping plugin optional
        return [{'id': 'standard', 'label': 'Standard delivery', 'amount': 0, 'currency': 'USD'}]


def checkout_review(request):
    """Step 3: final review + place order.

    POST creates the Order via the existing GraphQL mutation, captures
    the Stripe ``payment_client_secret`` it returns, and redirects to
    ``/checkout/payment/`` where the customer enters their card.
    """
    addr = request.session.get('checkout_address')
    if not addr:
        return redirect('/checkout/')
    cart_data = internal_graphql(CART_QUERY, request=request) or {}
    cart = cart_data.get('cart') or {}
    rate_label = request.session.get('checkout_shipping_rate_label', 'Standard')
    rate_id = request.session.get('checkout_shipping_rate_id', '')

    error = ''
    if request.method == 'POST':
        cart_id = (cart.get('id') or request.session.get('cart_id') or '').strip()
        if not cart_id:
            error = 'Your cart has expired — add items again to continue.'
        else:
            mutation = """
            mutation Complete($input: CompleteOrderInput!) {
              completeOrder(input: $input) { orderNumber paymentClientSecret errors { code message } }
            }
            """
            shipping_input = {
                'firstName': addr.get('first_name', ''),
                'lastName': addr.get('last_name', ''),
                'addressLine1': addr.get('address_line1', ''),
                'addressLine2': addr.get('address_line2', ''),
                'city': addr.get('city', ''),
                'state': addr.get('state', ''),
                'postalCode': addr.get('postal_code', ''),
                'country': addr.get('country', ''),
                'phone': addr.get('phone', ''),
            }
            data = internal_graphql(mutation, variables={
                'input': {
                    'cartId': cart_id,
                    'email': addr.get('email', ''),
                    'shippingAddress': shipping_input,
                    'shippingRateId': rate_id or None,
                },
            }, request=request) or {}
            payload = data.get('completeOrder') or {}
            errs = payload.get('errors') or []
            if errs:
                error = '; '.join(e.get('message', 'Order failed.') for e in errs)
            else:
                order_no = payload.get('orderNumber') or ''
                client_secret = payload.get('paymentClientSecret') or ''
                # Stash for the payment step; clear address/shipping
                # so a back-button refresh doesn't re-place the order.
                request.session['checkout_order_number'] = order_no
                request.session['checkout_client_secret'] = client_secret
                for k in ('checkout_address', 'checkout_shipping_rate_id', 'checkout_shipping_rate_label'):
                    request.session.pop(k, None)
                # If the order is fully zero-totalled (gift card +
                # store credit covers everything), Stripe doesn't
                # issue a client_secret. Skip the payment step.
                if not client_secret:
                    return redirect(f'/order/confirmation/{order_no}/' if order_no else '/account/orders/')
                return redirect('/checkout/payment/')

    return render(request, 'storefront/checkout_review.html', {
        'cart': cart,
        'address': addr,
        'rate_label': rate_label,
        'error': error,
    })


def checkout_payment(request):
    """Step 4: Stripe Payment Element.

    Renders Stripe.js + the Element keyed to the ``client_secret`` the
    review step stashed. On successful confirmation Stripe redirects
    the browser to ``return_url`` (the order confirmation page); the
    real source of truth for "paid" is the webhook in
    ``payments.services.stripe`` which already transitions the order
    atomically.
    """
    from django.conf import settings as dj_settings

    order_no = request.session.get('checkout_order_number') or ''
    client_secret = request.session.get('checkout_client_secret') or ''
    if not (order_no and client_secret):
        return redirect('/checkout/')
    publishable = getattr(dj_settings, 'STRIPE_PUBLIC_KEY', '') or ''
    return render(request, 'storefront/checkout_payment.html', {
        'order_number': order_no,
        'client_secret': client_secret,
        'stripe_publishable_key': publishable,
        'return_url': request.build_absolute_uri(
            f'/order/confirmation/{order_no}/'
        ),
    })


def search(request):
    q = request.GET.get('q', '').strip()
    use_semantic = request.GET.get('mode') == 'semantic'

    # Semantic mode keeps its dedicated AI-powered explanation page.
    # Plain keyword search bounces to /products/?q=…  — that path runs
    # through _apply_search (which unions in metafield matches), so
    # author/publisher/ISBN queries land on the rich faceted list UI.
    if not use_semantic:
        from django.shortcuts import redirect as _redirect
        target = f'/products/?q={q}' if q else '/products/'
        return _redirect(target)

    data = internal_graphql("""
        query SemanticSearch($query: String!) {
          semanticSearch(query: $query) {
            products { id name slug price { amount currency } primaryImage { url } }
            explanation
          }
        }
    """, variables={'query': q}, request=request) if q else None
    result = (data or {}).get('semanticSearch', {}) if data else {'products': [], 'explanation': None}

    return render(request, 'storefront/search.html', {
        'query': q, 'result': result, 'semantic': use_semantic
    })


# ─────────────────────────────────────────────────────────────────────────────
# Static + content pages
# ─────────────────────────────────────────────────────────────────────────────


# Hardcoded journal entries — TODO: extract to a CMS plugin with editable posts.
_JOURNAL_ENTRIES = [
    {
        'slug': 'a-short-note-on-patience',
        'title': 'A short note on patience and the long sentence',
        'date_label': 'April · 4 min read',
        'excerpt': 'On Cusk, on Sebald, on the way a long paragraph teaches you how to wait.',
        'body': (
            "There's a particular pleasure in a sentence that takes a breath you didn't know "
            "you had to give it. Cusk does this. Sebald does this. The reader is asked to slow "
            "down — to hold a thought in suspension — and in that suspension something settles. "
            "We carry a few of these books on the shelf this season because we believe in the "
            "case for the long take."
        ),
    },
    {
        'slug': 'why-we-dont-carry-books-we-havent-read',
        'title': "Why we don't carry books we haven't read",
        'date_label': 'April · 3 min read',
        'excerpt': 'A diary of how the shelf gets curated, and why it\'s a small one on purpose.',
        'body': (
            "Every title in the shop has been read by at least one of us before it makes it to "
            "the shelf. That's both a constraint and a promise. The constraint: the shop will "
            "always be small. The promise: if a book is here, it earned the spot. We trade "
            "breadth for trust."
        ),
    },
    {
        'slug': 'the-case-for-the-small-press',
        'title': 'The case for the small press, made in numbers',
        'date_label': 'April · 6 min read',
        'excerpt': 'Three years of receipts, and what they say about who\'s actually publishing the work that lasts.',
        'body': (
            "Pull three years of receipts and the picture is unambiguous: the books that customers "
            "come back to, the books they recommend to a friend, the books they buy a second copy "
            "of — they're disproportionately from independent presses. Not because indie is "
            "automatically better, but because the editors there have time to be wrong on purpose."
        ),
    },
]


def about(request):
    return render(request, 'storefront/about.html')


# Editorial intros for genre landing pages. The merchant can override any of
# these by giving the matching Category a non-empty `description` — that wins.
_CATEGORY_INTROS = {
    'fiction': {
        'eyebrow': 'On the shelf — fiction',
        'lede':    'Contemporary literary novels we couldn\'t put down. Slow-burn debuts, '
                   'patient experiments in form, and the occasional re-read of something we still mean.',
    },
    'nonfiction': {
        'eyebrow': 'On the shelf — non-fiction',
        'lede':    'Subject-matter we wanted to live with for a week. Cultural history, science writing '
                   'that earns its metaphors, and ideas books that don\'t mistake length for depth.',
    },
    'poetry': {
        'eyebrow': 'On the shelf — poetry',
        'lede':    'Pamphlets, debut collections, and chapbook-thin volumes you can finish in a sitting '
                   'and reopen for years. Read aloud at least once.',
    },
    'essays': {
        'eyebrow': 'On the shelf — essays',
        'lede':    'Long-form personal and cultural essays. The kind that show up in an annual best-of '
                   'and earn the placement.',
    },
    'art-design': {
        'eyebrow': 'On the shelf — art & design',
        'lede':    'Monographs and field guides. Books that teach you how to look, then make you want to.',
    },
    'children': {
        'eyebrow': 'On the shelf — children',
        'lede':    'Picture books, board books, and early-reader stories that hold up to the 200-times test.',
    },
}


def category_detail(request, slug):
    """Category landing — products in the category plus editorial framing.
    Falls back to hardcoded intros when the merchant hasn't written a
    Category.description yet."""
    from morpheus.views import Http404
    from plugins.installed.catalog.models import Category, Product

    category = Category.objects.filter(slug=slug).first()
    if category is None:
        raise Http404
    products = list(
        Product.objects.filter(status='active', category=category)
        .select_related('category')
        .order_by('-is_featured', '-created_at')[:60]
    )
    intro = _CATEGORY_INTROS.get(slug, {})
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'All books', 'url': request.build_absolute_uri('/products/')},
        {'name': category.name, 'url': request.build_absolute_uri(request.path)},
    ]
    return render(request, 'storefront/category_detail.html', {
        'category': category,
        'products': products,
        'intro_eyebrow': category.description and 'On the shelf' or intro.get('eyebrow', 'On the shelf'),
        'intro_lede':    category.description or intro.get('lede', ''),
        'breadcrumb_items': breadcrumb_items,
        # SEO meta — picked up by base.html's seo_meta tag.
        'seo_title':       f'{category.name} — dot books',
        'seo_description': category.description or intro.get('lede', '')[:160],
        'seo_og_type':     'website',
    })


def newsletter_subscribe(request):
    """Capture a footer newsletter signup as a CRM Lead with source='newsletter'.

    Returns JSON when called as fetch (footer JS uses this), HTML render
    falls back to a minimal thank-you page so users without JS still get
    confirmation.
    """
    from django.http import HttpResponseNotAllowed, JsonResponse

    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    email = (request.POST.get('email') or '').strip().lower()
    is_xhr = (
        request.headers.get('X-Requested-With', '').lower() == 'fetch'
        or 'application/json' in request.headers.get('Accept', '')
    )

    if not email or '@' not in email:
        if is_xhr:
            return JsonResponse({'ok': False, 'error': 'Please enter a valid email.'}, status=400)
        return render(request, 'storefront/newsletter_thanks.html', {
            'email': '', 'error': 'Please enter a valid email.',
        })

    try:
        from plugins.installed.crm.services import upsert_lead
        upsert_lead(email=email, source='newsletter')
    except Exception:  # noqa: BLE001 — CRM is optional; capture is best-effort
        pass

    if is_xhr:
        return JsonResponse({'ok': True, 'email': email})
    return render(request, 'storefront/newsletter_thanks.html', {'email': email, 'error': ''})


def author_detail(request, slug):
    """Author landing page — bibliography + optional bio.

    Slug is the author name run through Django's slugify. Resolution:
      1. Look up books whose `book.author` metafield, slugified, matches.
      2. Optionally pull a CMS Page tagged metadata.category='author' and
         metadata.author_slug==slug for bio + photo.
    Falls back to a minimal page (just the bibliography) when no Page exists.
    """
    from morpheus.views import Http404
    from django.utils.text import slugify

    # Find the canonical author name by reverse-lookup against metafields.
    author_name = ''
    bibliography = []
    try:
        from django.contrib.contenttypes.models import ContentType
        from plugins.installed.catalog.models import Product
        from plugins.installed.metafields.models import Metafield
        ct = ContentType.objects.get_for_model(Product)
        names = (Metafield.objects
                 .filter(content_type=ct, namespace='book', key='author')
                 .exclude(value='')
                 .values_list('value', flat=True).distinct())
        match = next((n for n in names if slugify(n) == slug), None)
        if match is None:
            raise Http404
        author_name = match
        product_ids = list(Metafield.objects.filter(
            content_type=ct, namespace='book', key='author', value__iexact=match,
        ).values_list('object_id', flat=True))
        bibliography = list(
            Product.objects.filter(id__in=product_ids, status='active')
            .order_by('-is_featured', '-created_at')
        )
    except Http404:
        raise
    except Exception:  # noqa: BLE001
        raise Http404

    # Optional bio Page from cms — by convention slug='author-<author_slug>'
    bio_page = None
    try:
        from plugins.installed.cms.models import Page
        bio_page = (Page.objects
                    .filter(slug=f'author-{slug}', state='published',
                            metadata__category='author')
                    .first())
    except Exception:  # noqa: BLE001
        pass

    return render(request, 'storefront/author_detail.html', {
        'author_name': author_name,
        'author_slug': slug,
        'bibliography': bibliography,
        'bio_page': bio_page,
        'seo_title':       f'{author_name} — dot books',
        'seo_description': (bio_page.excerpt if bio_page and bio_page.excerpt
                            else f'Books by {author_name}, on the dot books shelf.')[:160],
        'seo_og_type':     'profile',
    })


def staff_picks(request):
    """Curated staff picks — uses the 'staff-picks' Collection if one exists,
    falling back to 'editors-pick-april' (seeded by demo_data) so a fresh
    install is not empty."""
    from plugins.installed.catalog.models import Collection, Product

    collection = (
        Collection.objects.filter(slug='staff-picks', is_active=True).first()
        or Collection.objects.filter(slug='editors-pick-april', is_active=True).first()
    )
    products = []
    if collection is not None:
        products = list(
            Product.objects.filter(status='active', collections=collection)
            .order_by('-is_featured', '-created_at')[:30]
        )
    description = (
        collection.description if collection and collection.description
        else 'A small rotating shelf of titles we’d hand a friend without hesitation.'
    )
    return render(request, 'storefront/staff_picks.html', {
        'collection': collection,
        'products': products,
        'seo_title':       'Staff picks — dot books',
        'seo_description': description[:160],
        'seo_og_type':     'website',
    })


def contact(request):
    sent = False
    if request.method == 'POST':
        # Minimal: log the message and show a thank-you. A future contact plugin
        # can pipe these into CRM as Leads or Interactions.
        from plugins.installed.crm.services import upsert_lead, log_interaction
        from django.db import DatabaseError
        email = (request.POST.get('email') or '').strip().lower()
        name = (request.POST.get('name') or '').strip()
        body = (request.POST.get('message') or '').strip()
        if email and body:
            try:
                lead = upsert_lead(
                    email=email,
                    first_name=name.split(' ')[0] if name else '',
                    last_name=' '.join(name.split(' ')[1:]) if ' ' in name else '',
                    source='storefront',
                )
                log_interaction(
                    subject=lead, kind='note', direction='inbound',
                    summary='Contact form submission', body=body,
                    actor_name='storefront',
                )
            except (ImportError, DatabaseError):
                pass
        sent = True
    return render(request, 'storefront/contact.html', {'sent': sent})


def journal_index(request):
    # Prefer CMS pages (metadata.category=='journal'); fall back to the
    # baked-in seed entries until a merchant publishes anything in the dashboard.
    try:
        from plugins.installed.cms.services import list_journal_entries
        cms_entries = list_journal_entries()
    except Exception:  # noqa: BLE001 — CMS not installed / db not migrated
        cms_entries = []
    entries = cms_entries or _JOURNAL_ENTRIES
    return render(request, 'storefront/journal_index.html', {
        'entries': entries,
        'seo_title':       'Journal — dot books',
        'seo_description': 'Notes, essays, short pieces from the booksellers. Updated when there\'s something to say.',
        'seo_og_type':     'website',
    })


def journal_detail(request, slug):
    from morpheus.views import Http404
    entry = None
    try:
        from plugins.installed.cms.services import get_journal_entry
        entry = get_journal_entry(slug)
    except Exception:  # noqa: BLE001
        pass
    if entry is None:
        entry = next((e for e in _JOURNAL_ENTRIES if e['slug'] == slug), None)
    if entry is None:
        raise Http404
    return render(request, 'storefront/journal_detail.html', {
        'entry': entry,
        'seo_title':       f'{entry["title"]} — Journal — dot books',
        'seo_description': entry.get('excerpt', '')[:160],
        'seo_og_type':     'article',
    })


def categories(request):
    data = internal_graphql("""
        query Categories {
          categories(topLevel: true, first: 50) {
            id name slug image { url }
          }
        }
    """, request=request) or {}
    return render(request, 'storefront/categories.html', {
        'categories': data.get('categories', []),
    })


def account_home(request):
    if not request.user.is_authenticated:
        from morpheus.views import redirect
        return redirect('/auth/login/?next=/account/')
    summary = _account_summary(request.user)
    return render(request, 'storefront/account_home.html', {
        'user': request.user,
        'summary': summary,
    })


def _account_summary(user) -> dict:
    """Cheap counts + balances for the account home dashboard.

    Each lookup is fail-soft — a missing plugin shouldn't break the
    account page; the customer just sees that section as zero.
    """
    s: dict = {
        'orders_count': 0,
        'pending_returns': 0,
        'store_credit_balance': None,
        'gift_card_count': 0,
        'gift_card_total': None,
        'download_count': 0,
        'loyalty_points': 0,
    }
    try:
        from plugins.installed.loyalty_points.services import get_balance as _lb
        s['loyalty_points'] = _lb(user)
    except Exception:  # noqa: BLE001
        pass
    try:
        from plugins.installed.orders.models import Order
        s['orders_count'] = Order.objects.filter(customer=user).count()
    except Exception:  # noqa: BLE001
        pass
    try:
        from plugins.installed.orders.refunds import ReturnRequest
        s['pending_returns'] = ReturnRequest.objects.filter(
            order__customer=user, state__in=('requested', 'approved', 'received'),
        ).count()
    except Exception:  # noqa: BLE001
        pass
    try:
        from plugins.installed.orders import store_credit as _sc
        s['store_credit_balance'] = _sc.balance(user)
    except Exception:  # noqa: BLE001
        pass
    try:
        from plugins.installed.gift_cards.models import GiftCard
        from decimal import Decimal
        cards = GiftCard.objects.filter(
            issued_to_customer=user, state='active',
        )
        s['gift_card_count'] = cards.count()
        if cards.exists():
            total = sum(
                (Decimal(str(c.balance.amount)) for c in cards),
                Decimal('0'),
            )
            currency = str(cards.first().balance.currency)
            from djmoney.money import Money
            s['gift_card_total'] = Money(total, currency)
    except Exception:  # noqa: BLE001
        pass
    try:
        from plugins.installed.digital_products.models import DownloadToken
        from django.utils import timezone
        s['download_count'] = DownloadToken.objects.filter(
            order__customer=user,
            expires_at__gt=timezone.now(),
            revoked_at__isnull=True,
        ).count()
    except Exception:  # noqa: BLE001
        pass
    return s


def account_credits(request):
    """Combined view: store-credit balance + ledger + active gift cards."""
    if not request.user.is_authenticated:
        from morpheus.views import redirect
        return redirect('/auth/login/?next=/account/credits/')
    store_credit = None
    txns: list = []
    cards: list = []
    try:
        from plugins.installed.orders import store_credit as _sc
        from plugins.installed.orders.models import StoreCreditTxn
        store_credit = _sc.balance(request.user)
        txns = list(
            StoreCreditTxn.objects.filter(customer=request.user)
            .order_by('-created_at')[:30]
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        from plugins.installed.gift_cards.models import GiftCard
        cards = list(
            GiftCard.objects
            .filter(issued_to_customer=request.user, state='active')
            .order_by('-created_at')
        )
    except Exception:  # noqa: BLE001
        pass
    return render(request, 'storefront/account_credits.html', {
        'store_credit': store_credit,
        'txns': txns,
        'cards': cards,
    })


def account_downloads(request):
    """Active digital download links — token-protected, time-bound."""
    if not request.user.is_authenticated:
        from morpheus.views import redirect
        return redirect('/auth/login/?next=/account/downloads/')
    tokens: list = []
    try:
        from plugins.installed.digital_products.models import DownloadToken
        from django.utils import timezone
        tokens = list(
            DownloadToken.objects
            .filter(order__customer=request.user, revoked_at__isnull=True)
            .select_related('product', 'order')
            .order_by('-created_at')[:50]
        )
        # Hide ones already past expiry — user can still see them but
        # we tag them so the template renders the button as disabled.
        now = timezone.now()
        for t in tokens:
            t.is_expired = bool(t.expires_at and t.expires_at <= now)
            t.is_exhausted = t.downloads_used >= t.max_downloads
    except Exception:  # noqa: BLE001
        pass
    return render(request, 'storefront/account_downloads.html', {
        'tokens': tokens,
    })


def account_orders(request):
    if not request.user.is_authenticated:
        from morpheus.views import redirect
        return redirect('/auth/login/?next=/account/orders/')
    try:
        from plugins.installed.orders.models import Order
        orders = list(
            Order.objects.filter(customer=request.user)
            .order_by('-created_at')[:50]
        )
    except Exception:  # noqa: BLE001
        orders = []
    return render(request, 'storefront/account_orders.html', {'orders': orders})


def account_order_detail(request, order_number):
    if not request.user.is_authenticated:
        from morpheus.views import redirect
        return redirect(f'/auth/login/?next=/account/orders/{order_number}/')
    from morpheus.views import get_object_or_404
    from plugins.installed.orders.models import Order
    order = get_object_or_404(
        Order.objects.prefetch_related('items'),
        order_number=order_number, customer=request.user,
    )
    return render(request, 'storefront/account_order_detail.html', {'order': order})


def order_confirmation(request, order_number):
    """Public order confirmation — accessible by order_number alone (signed link).
    Future: token-protect to prevent enumeration.

    Stripe redirects here after a successful confirmPayment, so this is
    also the natural place to clear any leftover checkout session state.
    The actual "paid" transition happens via the Stripe webhook in
    payments.services.stripe — this page just shows the order.
    """
    from morpheus.views import get_object_or_404
    from plugins.installed.orders.models import Order
    order = get_object_or_404(
        Order.objects.prefetch_related('items'), order_number=order_number,
    )
    # Clean up so the Back button doesn't re-confirm.
    for k in ('checkout_order_number', 'checkout_client_secret'):
        request.session.pop(k, None)
    redirect_status = (request.GET.get('redirect_status') or '').lower()
    return render(request, 'storefront/order_confirmation.html', {
        'order': order,
        'payment_status': redirect_status,  # 'succeeded' / 'processing' / 'requires_payment_method'
    })


def coming_soon(request, slug=None):
    """Generic placeholder for footer links that don't have first-class pages
    yet (stockists, staff picks, shipping, returns). One template, many paths."""
    title_map = {
        'stockists': 'Stockists',
        'staff-picks': 'Staff picks',
        'shipping': 'Shipping',
        'returns': 'Returns',
    }
    page_slug = slug or request.path.strip('/').split('/')[-1] or 'coming-soon'
    return render(request, 'storefront/coming_soon.html', {
        'page_title': title_map.get(page_slug, page_slug.replace('-', ' ').title()),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Customer account v2 — addresses, profile, returns
# ─────────────────────────────────────────────────────────────────────────────


def _login_required(request, target):
    if not request.user.is_authenticated:
        from django.shortcuts import redirect as _redirect
        return _redirect(f'/auth/login/?next={target}')
    return None


def account_profile(request):
    redirect_resp = _login_required(request, '/account/profile/')
    if redirect_resp is not None:
        return redirect_resp
    user = request.user
    if request.method == 'POST':
        for field in ('first_name', 'last_name'):
            val = (request.POST.get(field) or '').strip()
            if val:
                setattr(user, field, val[:120])
        new_email = (request.POST.get('email') or '').strip().lower()
        if new_email and new_email != user.email:
            user.email = new_email[:254]
        user.save(update_fields=['first_name', 'last_name', 'email'])
        from django.shortcuts import redirect as _redirect
        return _redirect('storefront:account_profile')
    return render(request, 'storefront/account_profile.html', {'user': user})


def account_addresses(request):
    redirect_resp = _login_required(request, '/account/addresses/')
    if redirect_resp is not None:
        return redirect_resp
    addresses = list(request.user.addresses.all().order_by('-is_default', '-created_at'))
    return render(request, 'storefront/account_addresses.html', {'addresses': addresses})


def account_address_form(request, address_id=None):
    redirect_resp = _login_required(request, '/account/addresses/')
    if redirect_resp is not None:
        return redirect_resp
    from plugins.installed.customers.models import Address
    address = None
    if address_id:
        from morpheus.views import get_object_or_404
        address = get_object_or_404(Address, id=address_id, customer=request.user)
    if request.method == 'POST':
        from django.shortcuts import redirect as _redirect
        data = {
            'first_name': (request.POST.get('first_name') or '')[:100],
            'last_name': (request.POST.get('last_name') or '')[:100],
            'company': (request.POST.get('company') or '')[:200],
            'address_line1': (request.POST.get('address_line1') or '')[:255],
            'address_line2': (request.POST.get('address_line2') or '')[:255],
            'city': (request.POST.get('city') or '')[:100],
            'state': (request.POST.get('state') or '')[:100],
            'postal_code': (request.POST.get('postal_code') or '')[:20],
            'country': (request.POST.get('country') or 'US')[:2].upper(),
            'phone': (request.POST.get('phone') or '')[:30],
            'is_default': bool(request.POST.get('is_default')),
            'address_type': request.POST.get('address_type', 'shipping'),
        }
        if address is not None:
            for k, v in data.items():
                setattr(address, k, v)
            address.save()
        else:
            Address.objects.create(customer=request.user, **data)
        return _redirect('storefront:account_addresses')
    return render(request, 'storefront/account_address_form.html', {'address': address})


def account_address_delete(request, address_id):
    redirect_resp = _login_required(request, '/account/addresses/')
    if redirect_resp is not None:
        return redirect_resp
    from django.shortcuts import get_object_or_404, redirect as _redirect
    from plugins.installed.customers.models import Address
    address = get_object_or_404(Address, id=address_id, customer=request.user)
    if request.method == 'POST':
        address.delete()
    return _redirect('storefront:account_addresses')


def account_returns(request):
    redirect_resp = _login_required(request, '/account/returns/')
    if redirect_resp is not None:
        return redirect_resp
    try:
        from plugins.installed.orders.refunds import ReturnRequest
        rrs = list(ReturnRequest.objects.filter(
            order__customer=request.user,
        ).order_by('-created_at'))
    except Exception:  # noqa: BLE001
        rrs = []
    return render(request, 'storefront/account_returns.html', {'returns': rrs})


def account_return_status(request, rma_id):
    """Per-RMA status page — what the customer comes back to after submitting.

    Renders the same `state` field as a four-step pill row so the customer
    can see at a glance where their return is in the lifecycle, without
    having to email support.
    """
    redirect_resp = _login_required(request, f'/account/returns/{rma_id}/')
    if redirect_resp is not None:
        return redirect_resp
    from django.shortcuts import get_object_or_404
    from plugins.installed.orders.refunds import ReturnRequest
    rr = get_object_or_404(
        ReturnRequest.objects.select_related('order'),
        pk=rma_id, order__customer=request.user,
    )

    happy_path = ['requested', 'approved', 'received', 'refunded']
    labels = {
        'requested': 'Requested', 'approved': 'Approved',
        'received': 'Received', 'refunded': 'Refunded',
    }
    cur_idx = happy_path.index(rr.state) if rr.state in happy_path else -1
    status_steps = [
        {'key': k, 'label': labels[k],
         'done': cur_idx > i, 'current': cur_idx == i}
        for i, k in enumerate(happy_path)
    ]

    from plugins.installed.orders.models import OrderItem
    items_by_id = {str(o.pk): o for o in OrderItem.objects.filter(order=rr.order)}
    line_items = []
    for entry in (rr.items or []):
        oi = items_by_id.get(str(entry.get('order_item_id', '')))
        if oi is None:
            continue
        line_items.append({
            'name': oi.product_name, 'sku': oi.sku,
            'quantity': entry.get('quantity', 0),
            'unit_price': oi.unit_price,
        })

    return render(request, 'storefront/account_return_status.html', {
        'rma': rr, 'order': rr.order,
        'status_steps': status_steps,
        'line_items': line_items,
        'is_terminal': rr.state in ('refunded', 'cancelled', 'rejected'),
    })


def account_order_return(request, order_number):
    redirect_resp = _login_required(request, f'/account/orders/{order_number}/return/')
    if redirect_resp is not None:
        return redirect_resp
    from django.shortcuts import get_object_or_404, redirect as _redirect
    from plugins.installed.orders.models import Order
    order = get_object_or_404(
        Order.objects.prefetch_related('items'),
        order_number=order_number, customer=request.user,
    )
    if request.method == 'POST':
        from plugins.installed.orders.refunds import ReturnService
        items = []
        for item in order.items.all():
            qty = int(request.POST.get(f'qty_{item.id}', 0) or 0)
            if qty > 0:
                items.append({'order_item_id': str(item.id), 'quantity': min(qty, item.quantity)})
        if items:
            rr = ReturnService.create_request(
                order=order, items=items,
                reason=request.POST.get('reason', 'other'),
                customer_note=(request.POST.get('note', '') or '')[:2000],
                requested_by=request.user,
            )
            # Land on the new status page so the customer sees the request
            # they just made + can come back to track it later.
            return _redirect('storefront:account_return_status', rma_id=rr.id)
        return _redirect('storefront:account_returns')
    return render(request, 'storefront/account_order_return.html', {'order': order})
