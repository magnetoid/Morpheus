"""Turn a request (+ template context) into a `SeoPage`.

Three sources, in order:

1. **An explicit hint.** A view that knows exactly what it is rendering can put
   a `SeoPage` (or the legacy `seo_object`) in the context.
2. **An owner.** `SEO_RESOLVE_PAGE` lets the app that owns a URL shape answer —
   book_product for `/author/…` and its taxonomy landings, cms for pages,
   marketplace for vendor pages. First non-None answer wins, which is how this
   module stays free of imports it has no business having.
3. **Built-in knowledge of the storefront.** Keyed on `resolver_match.url_name`,
   because URL *names* are stable while paths are merchant-editable.

Anything unrecognised resolves to a plain indexable page rather than nothing:
an unknown page with a title beats a known page with none.
"""

from __future__ import annotations

import logging

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

# url_name → (kind, subtype). The storefront's own routes; everything else
# arrives through SEO_RESOLVE_PAGE or falls back to a static page.
_KIND_BY_URL_NAME: dict[str, tuple[str, str]] = {
    'home': (KIND_HOME, ''),
    'product_list': (KIND_LISTING, 'products'),
    'product_detail': (KIND_PRODUCT, ''),
    'categories': (KIND_LISTING, 'categories'),
    'category_detail': (KIND_LISTING, 'category'),
    'collection_detail': (KIND_LISTING, 'collection'),
    'author_detail': (KIND_LISTING, 'author'),
    'vendors': (KIND_LISTING, 'vendors'),
    'vendor_detail': (KIND_LISTING, 'vendor'),
    'marketplace_landing': (KIND_LISTING, 'marketplace'),
    'staff_picks': (KIND_LISTING, 'staff_picks'),
    'journal_index': (KIND_LISTING, 'journal'),
    'journal_detail': (KIND_ARTICLE, 'journal'),
    'journal_amp': (KIND_ARTICLE, 'journal_amp'),
    'search': (KIND_SEARCH, ''),
    'about': (KIND_STATIC, 'about'),
    'contact': (KIND_STATIC, 'contact'),
    'shipping': (KIND_STATIC, 'shipping'),
    'returns': (KIND_STATIC, 'returns'),
    'stockists': (KIND_STATIC, ''),
    'affiliate_terms': (KIND_STATIC, ''),
    'do_not_sell': (KIND_STATIC, ''),
    'page_detail': (KIND_PAGE, ''),
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


def _builtin(request, context) -> SeoPage:
    path = _path_of(request)
    url_name = getattr(getattr(request, 'resolver_match', None), 'url_name', '') or ''
    kind, subtype = _KIND_BY_URL_NAME.get(url_name, ('', ''))

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
    page.description = _clean(context.get('seo_description'))
    page.image = _clean(context.get('seo_image'))
    page.og_type = _clean(context.get('seo_og_type')) or _og_type_for(kind)
    page.breadcrumbs = context.get('breadcrumb_items') or []
    page.page_obj = context.get('page_obj') or context.get('products')
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
    return page


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
