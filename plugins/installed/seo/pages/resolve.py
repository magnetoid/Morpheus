"""Turn a request (+ template context) into a `SeoPage`.

Three sources, in order:

1. **An explicit hint.** A view that knows exactly what it is rendering can put
   a `SeoPage` (or the legacy `seo_object`) in the context.
2. **An owner.** `SEO_RESOLVE_PAGE` lets the app that owns a URL shape answer —
   book_product for `/author/…` and its taxonomy landings, cms for pages,
   marketplace for vendor pages. First non-None answer wins, which is how this
   module stays free of imports it has no business having.
3. **Built-in knowledge of the storefront.** Keyed on the NAMESPACED view name
   (`storefront:home`), because URL names are stable while paths are
   merchant-editable — and a bare `home` is also wishlist's index.

Anything unrecognised resolves to a plain indexable page rather than nothing:
an unknown page with a title beats a known page with none.

`_finish` then applies the rules that hold whoever resolved the page: a private
path is never indexed, a listing carrying a search query is search results, a
listing with nothing on it is an empty shelf (a soft 404 to a search engine),
and a view may hold its own page back with `seo_noindex_reason`.
"""

from __future__ import annotations

import logging

from django.utils.translation import gettext

from .types import (
    KIND_ARTICLE,
    KIND_HOME,
    KIND_LISTING,
    KIND_PAGE,
    KIND_PRIVATE,
    KIND_PRODUCT,
    KIND_SEARCH,
    KIND_STATIC,
    SeoPage,
)

logger = logging.getLogger('morpheus.seo')

# view name → (kind, subtype). The storefront's own routes; everything else
# arrives through SEO_RESOLVE_PAGE or falls back to a static page. Namespaced:
# matching on the bare url_name made wishlist's `home` route the home page.
_KIND_BY_VIEW_NAME: dict[str, tuple[str, str]] = {
    'storefront:home': (KIND_HOME, ''),
    'storefront:product_list': (KIND_LISTING, 'products'),
    'storefront:product_detail': (KIND_PRODUCT, ''),
    'storefront:categories': (KIND_LISTING, 'categories'),
    'storefront:category_detail': (KIND_LISTING, 'category'),
    'storefront:collection_detail': (KIND_LISTING, 'collection'),
    'storefront:author_detail': (KIND_LISTING, 'author'),
    'storefront:vendors': (KIND_LISTING, 'vendors'),
    'storefront:vendor_detail': (KIND_LISTING, 'vendor'),
    'storefront:marketplace_landing': (KIND_LISTING, 'marketplace'),
    'storefront:staff_picks': (KIND_LISTING, 'staff_picks'),
    'storefront:journal_index': (KIND_LISTING, 'journal'),
    'storefront:journal_detail': (KIND_ARTICLE, 'journal'),
    'storefront:journal_amp': (KIND_ARTICLE, 'journal_amp'),
    'storefront:search': (KIND_SEARCH, ''),
    'storefront:about': (KIND_STATIC, 'about'),
    'storefront:contact': (KIND_STATIC, 'contact'),
    'storefront:shipping': (KIND_STATIC, 'shipping'),
    'storefront:returns': (KIND_STATIC, 'returns'),
    'storefront:stockists': (KIND_STATIC, ''),
    'storefront:affiliate_terms': (KIND_STATIC, ''),
    'storefront:do_not_sell': (KIND_STATIC, ''),
    'cms:page': (KIND_PAGE, ''),
}

# Pages a shopper reaches while signing in, paying or managing an account. Their
# views pass no title (the theme templates carried `{% block title %}`s that no
# base template renders), so the fallback read "Account Payment Methods" or,
# for allauth's routes, "Account Login". Looked up at render time so the words
# follow the page's language.
_TITLE_BY_VIEW_NAME: dict[str, str] = {
    'storefront:cart': 'Your cart',
    'storefront:checkout': 'Checkout',
    'storefront:checkout_one_page': 'Checkout',
    'storefront:checkout_shipping': 'Delivery details',
    'storefront:checkout_review': 'Review your order',
    'storefront:checkout_payment': 'Payment',
    'storefront:order_confirmation': 'Order received',
    'storefront:account_home': 'Your account',
    'storefront:account_profile': 'Profile',
    'storefront:account_orders': 'Order history',
    'storefront:account_order_detail': 'Order details',
    'storefront:account_order_return': 'Return an order',
    'storefront:account_addresses': 'Addresses',
    'storefront:account_address_new': 'New address',
    'storefront:account_address_edit': 'Edit address',
    'storefront:account_returns': 'Returns',
    'storefront:account_return_status': 'Return status',
    'storefront:account_credits': 'Store credit & gift cards',
    'storefront:account_payment_methods': 'Saved cards',
    'account_login': 'Sign in',
    'account_signup': 'Create an account',
    'account_logout': 'Sign out',
    'account_reset_password': 'Reset your password',
    'account_reset_password_done': 'Check your inbox',
    'account_reset_password_from_key': 'Choose a new password',
    'account_reset_password_from_key_done': 'Password changed',
    'account_email_verification_sent': 'Confirm your email',
    'account_confirm_email': 'Confirm your email',
    'account_change_password': 'Change your password',
    'account_email': 'Email addresses',
    'core_auth:otp_request': 'Sign in with a code',
    'staff_mfa:challenge': 'Two-factor verification',
    'core_auth:otp_verify': 'Enter your code',
}

# Surfaces that must never be indexed. Prefix-matched on the path so a plugin
# adding `/account/wishlist/` inherits the rule instead of leaking a customer's
# page into a search index.
_PRIVATE_PREFIXES = (
    '/cart/',
    '/checkout/',
    '/account/',
    '/auth/',
    '/order/',
    '/wishlist/',
    '/returns/portal/',
)
# Exact private paths (prefix match would catch too much, e.g. '/returns/').
_PRIVATE_PATHS = frozenset({'/cart', '/checkout'})


def resolve_page(request, context=None) -> SeoPage:
    """Resolve the page. Never raises; worst case returns a bare static page."""
    context = context or {}

    hinted = context.get('seo_page')
    if isinstance(hinted, SeoPage):
        return _finish(hinted, request, context)

    if _is_error_render(context):
        page = SeoPage(kind=KIND_PRIVATE, subtype='error', path=_path_of(request), context=context)
        # `noindex, follow`, not `nofollow`: the page is not worth indexing, but
        # its nav is the same nav as everywhere else and there is no reason to
        # strand a crawler that arrived on a dead URL.
        page.deny_index('error page')
        # Title it explicitly. `_title_from_object` only reads the page's OBJECT,
        # and an error render has none, so `_fallback_title` would Title-Case the
        # subtype — the live 404 read "Error — <store>" rather than the
        # "Page not found" its template passes to `{% storefront_head %}`. The
        # default is translated: `/sr/<missing>/` used to say it in English.
        page.title = (context.get('seo_title') or '').strip() or gettext('Page not found')
        return _finish(page, request, context)

    page = _from_hook(request, context)
    if page is None:
        page = _builtin(request, context)
    return _finish(page, request, context)


def _is_error_render(context) -> bool:
    """True while Django is rendering `404.html`.

    `django.views.defaults.page_not_found` renders the template with exactly
    `{'request_path': …, 'exception': …}` — that pair is the documented contract
    and nothing else in a storefront render supplies it.

    Without this the error page resolved as an ordinary static page and shipped
    `index, follow`. Themes papered over it by emitting their own `noindex`
    beside the document's, which is how montenegro's 404 came to carry two
    robots directives (v0.70.2). The status code is the stronger signal to a
    crawler either way, but a page must not *ask* to be indexed and then 404.
    """
    return bool(context) and 'request_path' in context and 'exception' in context


def is_error_page(page: SeoPage) -> bool:
    """The page Django renders for a 404 — not a page in any search sense."""
    return page.kind == KIND_PRIVATE and page.subtype == 'error'


def _from_hook(request, context) -> SeoPage | None:
    try:
        from core.hooks import MorpheusEvents, hook_registry

        answer = hook_registry.filter(
            MorpheusEvents.SEO_RESOLVE_PAGE, None, request=request, context=context
        )
    except Exception as e:  # noqa: BLE001 — a bad subscriber must not break the head
        logger.warning('seo: SEO_RESOLVE_PAGE failed: %s', e, exc_info=True)
        return None
    return answer if isinstance(answer, SeoPage) else None


def _view_name(request) -> tuple[str, str]:
    """`(view_name, url_name)` of the matched route — `('', '')` when unmatched."""
    match = getattr(request, 'resolver_match', None)
    if match is None:
        return '', ''
    return (getattr(match, 'view_name', '') or ''), (getattr(match, 'url_name', '') or '')


def _builtin(request, context) -> SeoPage:
    path = _path_of(request)
    view_name, url_name = _view_name(request)
    kind, subtype = _KIND_BY_VIEW_NAME.get(view_name, ('', ''))

    if not kind:
        kind = KIND_PRIVATE if _is_private(path) else KIND_STATIC
        # Keep the route name as the subtype so even an unmapped page gets a
        # human title ("account_orders" → "Account Orders") instead of the bare
        # brand — a titleless page is a usability bug in the browser tab too.
        subtype = url_name

    page = SeoPage(kind=kind, subtype=subtype, path=path, context=context)

    # The object the page is about. `seo_object` is the long-standing storefront
    # convention; the specific keys are the fallback for views that set only the
    # object they render.
    page.obj = context.get('seo_object')
    if page.obj is None:
        for key in ('product', 'category', 'collection', 'vendor', 'page', 'entry'):
            candidate = context.get(key)
            if candidate is not None and not isinstance(candidate, str | int | float | bool):
                page.obj = candidate
                break
    # …and what the template rendered, when that is a different shape (the PDP
    # renders a GraphQL dict). Structured data and Open Graph prefer it because
    # it carries the price and stock the shopper is looking at.
    rendered = context.get('product') if kind == KIND_PRODUCT else None
    if isinstance(rendered, dict):
        page.rendered = rendered
    # A dict can never carry a SeoMeta override (it has no content type), so it
    # must not be used as `obj`.
    if isinstance(page.obj, dict):
        page.rendered = page.rendered or page.obj
        page.obj = None

    page.title = _clean(context.get('seo_title'))
    if not page.title and view_name in _TITLE_BY_VIEW_NAME:
        page.title = gettext(_TITLE_BY_VIEW_NAME[view_name])
    page.description = _clean(context.get('seo_description'))
    page.image = _clean(context.get('seo_image'))
    page.og_type = _clean(context.get('seo_og_type')) or _og_type_for(kind)
    page.breadcrumbs = context.get('breadcrumb_items') or []
    # `is None`, not `or`: a Django paginator Page defines `__len__`, so an EMPTY
    # page is falsy — and `or` swapped it for the product list, losing the very
    # paginator that says the listing is empty.
    page.page_obj = context.get('page_obj')
    if page.page_obj is None:
        page.page_obj = context.get('products')
    page.query = _clean(context.get('query') or (request.GET.get('q') if request else ''))

    # The home page's title IS the brand — appending it again gives
    # the brand twice ("dot books — dot books"; ADR 0007).
    page.brand_title = kind != KIND_HOME

    if kind == KIND_PRIVATE:
        page.deny_index('private surface (cart / checkout / account)', nofollow=True)
    elif kind == KIND_SEARCH:
        # Follow the links, don't index the query permutations — Google lists
        # internal search results as a canonical low-value URL class.
        page.deny_index('internal search results')
    return page


def _finish(page: SeoPage, request, context) -> SeoPage:
    """Fill in whatever the source left blank, and apply path-level rules."""
    if not page.path:
        page.path = _path_of(request)
    if not page.context:
        page.context = context
    if not page.og_type:
        page.og_type = _og_type_for(page.kind)
    if not page.breadcrumbs:
        page.breadcrumbs = context.get('breadcrumb_items') or []
    if page.page_obj is None:
        page.page_obj = context.get('page_obj')
    if not page.title:
        page.title = _title_from_object(page) or _fallback_title(page)
    if not page.description:
        page.description = _description_from_object(page)
    # A private path always wins, whoever resolved the page: an app that
    # mistakenly claims `/account/orders/` must not make it indexable.
    if _is_private(page.path) and not page.noindex:
        page.kind = KIND_PRIVATE
        page.deny_index('private surface (cart / checkout / account)', nofollow=True)
    # A listing filtered by a search query IS internal search results, whoever
    # owns the listing: `/search/?q=` lands on `/products/?q=`, and that page
    # shipped `index, follow` on every store — one indexable page per query.
    query = _search_query(request)
    if page.kind == KIND_LISTING and query:
        page.kind = KIND_SEARCH
        page.query = page.query or query
        page.deny_index('internal search results')
    _deny_before_launch(page)
    # A view that knows its page should stay out (a placeholder, a preview)
    # says so with a reason, and the reason surfaces in the head inspector.
    reason = _clean(context.get('seo_noindex_reason'))
    if reason:
        page.deny_index(reason)
    # An empty shelf is a soft 404 to a search engine: a 200 page that says
    # "nothing here". 181 of 520 sitemap urls on the travel store were exactly
    # that. Follow the links, keep it out of the index.
    if page.kind == KIND_LISTING and _item_count(page, context) == 0:
        page.deny_index('empty listing')
    return page


def _deny_before_launch(page: SeoPage) -> None:
    """A store that has not launched keeps every page out of the index.

    An error page keeps its own `noindex, follow`.
    """
    if is_error_page(page):
        return
    from plugins.installed.seo.services.launch import hidden_until_launch

    if hidden_until_launch():
        page.deny_index('the store is hidden until launch (Settings → SEO)', nofollow=True)


def _search_query(request) -> str:
    try:
        return (request.GET.get('q') or '').strip() if request is not None else ''
    except Exception:  # noqa: BLE001 — a request-like object without a QueryDict
        return ''


def _item_count(page: SeoPage, context) -> int | None:
    """How many things the listing shows, or None when nobody said.

    A view reports it as `seo_item_count` (the reliable source: it knows what it
    rendered, including items another app contributed); otherwise a real
    paginator's total is used. Unknown is not zero — the rule must never hold
    back a listing whose count was simply not reported.
    """
    explicit = (context or {}).get('seo_item_count')
    if isinstance(explicit, int) and not isinstance(explicit, bool):
        return explicit
    paginator = getattr(page.page_obj, 'paginator', None)
    count = getattr(paginator, 'count', None)
    return count if isinstance(count, int) and not isinstance(count, bool) else None


# -- helpers -------------------------------------------------------------
def _path_of(request) -> str:
    if request is None:
        return ''
    try:
        return request.get_full_path()
    except Exception:  # noqa: BLE001
        return ''


def _is_private(path: str) -> bool:
    bare = (path or '').split('?', 1)[0].rstrip('/')
    if bare in _PRIVATE_PATHS:
        return True
    return any((path or '').startswith(prefix) for prefix in _PRIVATE_PREFIXES)


def _og_type_for(kind: str) -> str:
    if kind == KIND_PRODUCT:
        return 'product'
    if kind == KIND_ARTICLE:
        return 'article'
    return 'website'


def _clean(value) -> str:
    if value is None or isinstance(value, bool):
        return ''
    return str(value).strip()


def _attr(obj, name: str) -> str:
    """Objects arrive as models OR as GraphQL dicts (the PDP renders a dict)."""
    if obj is None:
        return ''
    if isinstance(obj, dict):
        return _clean(obj.get(name))
    return _clean(getattr(obj, name, ''))


def _title_from_object(page: SeoPage) -> str:
    for source in (page.obj, page.rendered):
        for field in ('meta_title', 'name', 'title'):
            value = _attr(source, field)
            if value:
                return value
    return ''


def _description_from_object(page: SeoPage) -> str:
    from plugins.installed.seo.services._helpers import strip_html

    # `body` last: a journal post with no excerpt still deserves a description,
    # and its opening paragraph is a better one than nothing at all.
    for source in (page.obj, page.rendered):
        for field in ('meta_description', 'short_description', 'excerpt', 'description', 'body'):
            value = _attr(source, field)
            if value:
                return strip_html(value)[:320]
    return ''


def _fallback_title(page: SeoPage) -> str:
    """Last resort so no page ever renders untitled.

    `/search/` used to render with no `<title>` at all, because the theme's
    title lived inside the same template block the page overrode to force
    `noindex` — exactly the class of bug a shell-level fallback removes.
    """
    from plugins.installed.seo.services.meta import brand_name

    if page.kind == KIND_SEARCH:
        return f'Search: {page.query}' if page.query else 'Search'
    if page.subtype:
        return page.subtype.replace('_', ' ').title()
    return brand_name() or 'Home'
