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
    return render(request, 'storefront/home.html', data)


def product_list(request):
    """Product list with merchant-friendly facets: category, tag, price range, sort."""
    from decimal import Decimal, InvalidOperation
    from plugins.installed.catalog.models import Category, Product

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

    products = list(qs[:60])
    categories = list(Category.objects.filter(parent__isnull=True).order_by('name'))

    return render(request, 'storefront/product_list.html', {
        'products': products,
        'categories': categories,
        'search_query': q,
        'selected_category': cat_slug,
        'selected_tag': tag_slug,
        'selected_sort': sort,
        'price_min': pmin or '',
        'price_max': pmax or '',
    })


def _apply_search(qs, q: str):
    """Postgres full-text search with relevance ranking.

    Builds a SearchVector over name + short_description + tags and orders
    by SearchRank. Falls back to ILIKE on non-Postgres backends so the
    storefront still works in dev sqlite without crashing.
    """
    from django.db import connection
    from django.db.models import Q

    if connection.vendor == 'postgresql':
        try:
            from django.contrib.postgres.search import (
                SearchQuery, SearchRank, SearchVector,
            )
            vector = (
                SearchVector('name', weight='A')
                + SearchVector('short_description', weight='B')
                + SearchVector('description', weight='C')
            )
            search_q = SearchQuery(q, search_type='websearch')
            return (
                qs.annotate(_rank=SearchRank(vector, search_q))
                .filter(Q(_rank__gt=0) | Q(sku__iexact=q))
                .order_by('-_rank', '-created_at')
            )
        except Exception:  # noqa: BLE001 — fall through to LIKE
            pass

    return qs.filter(
        Q(name__icontains=q)
        | Q(short_description__icontains=q)
        | Q(sku__iexact=q)
    )


def product_detail(request, slug):
    data = internal_graphql(PRODUCT_DETAIL_QUERY, variables={'slug': slug}, request=request)
    product = (data or {}).get('product')
    if not product:
        from morpheus.views import Http404
        raise Http404
    return render(request, 'storefront/product_detail.html', {'product': product})


def cart(request):
    data = internal_graphql(CART_QUERY, request=request)
    return render(request, 'storefront/cart.html', {'cart': (data or {}).get('cart', {})})


def checkout(request):
    if request.method == 'GET':
        return render(request, 'storefront/checkout.html')
    # POST — handled via GraphQL mutation from JS
    return redirect('storefront:cart')


def search(request):
    q = request.GET.get('q', '').strip()
    use_semantic = request.GET.get('mode') == 'semantic'

    if use_semantic and q:
        data = internal_graphql("""
            query SemanticSearch($query: String!) {
              semanticSearch(query: $query) {
                products { id name slug price { amount currency } primaryImage { url } }
                explanation
              }
            }
        """, variables={'query': q}, request=request)
        result = (data or {}).get('semanticSearch', {})
    else:
        data = internal_graphql(PRODUCT_LIST_QUERY, variables={
            'first': 24, 'search': q, 'category': ''
        }, request=request)
        result = {'products': (data or {}).get('products', []), 'explanation': None}

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
    return render(request, 'storefront/journal_index.html', {'entries': _JOURNAL_ENTRIES})


def journal_detail(request, slug):
    from morpheus.views import Http404
    entry = next((e for e in _JOURNAL_ENTRIES if e['slug'] == slug), None)
    if entry is None:
        raise Http404
    return render(request, 'storefront/journal_detail.html', {'entry': entry})


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
    return render(request, 'storefront/account_home.html', {
        'user': request.user,
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
    Future: token-protect to prevent enumeration."""
    from morpheus.views import get_object_or_404
    from plugins.installed.orders.models import Order
    order = get_object_or_404(
        Order.objects.prefetch_related('items'), order_number=order_number,
    )
    return render(request, 'storefront/order_confirmation.html', {'order': order})


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
            ReturnService.create_request(
                order=order, items=items,
                reason=request.POST.get('reason', 'other'),
                customer_note=(request.POST.get('note', '') or '')[:2000],
                requested_by=request.user,
            )
        return _redirect('storefront:account_returns')
    return render(request, 'storefront/account_order_return.html', {'order': order})
