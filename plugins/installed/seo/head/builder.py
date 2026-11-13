"""Assemble the storefront `<head>` for a resolved page.

This subscriber is where "SEO" stops being a property of the theme. It receives
the `HeadDocument` core seeded with the shell's fallback title, resolves which
page is being rendered, and fills in: the branded `<title>`, the description,
robots (with an explicit reason when a page is held back), the canonical, Open
Graph + Twitter cards, search-engine verification metas, hreflang alternates
(per language), pagination links, the LLM discovery hint, and one
JSON-LD `@graph`.

Four rules run through all of it:

* **Every entry is keyed**, so the theme's fallback title is *replaced*, not
  joined by a second `<title>`.
* **Nothing here may raise.** A head that fails must degrade to the seeded
  fallback, never take down a product page — so each section is guarded
  independently rather than the whole build sharing one try/except.
* **An error page is not a page.** A 404 gets its title, description and
  `noindex, follow` — no canonical, alternates, Open Graph or graph. Each of
  those names a URL or describes an entity, and the live 404s on every store
  named the dead URL five different ways under a correct status code.
* **A noindex page never names another URL.** No hreflang (an alternate must be
  an indexable canonical), no prev/next, no graph, and a canonical only when it
  is the page itself. `noindex` beside a canonical naming a different URL is two
  claims about two URLs, and the noindex can travel to the target.
* **A duplicate declares nothing of its own.** A page whose canonical names
  another path (its owner's `SeoPage.canonical`, a merchant override) gets no
  hreflang, prev/next or graph either: those describe the canonical page.
"""

from __future__ import annotations

import logging
from contextlib import suppress
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from plugins.installed.seo.head.canonical import canonical_for, paginated_links
from plugins.installed.seo.pages import resolve_page
from plugins.installed.seo.pages.resolve import is_error_page
from plugins.installed.seo.pages.types import KIND_PRODUCT, SeoPage

logger = logging.getLogger('morpheus.seo')

# Google reads these as "you may show a full snippet / a large image". They are
# also the levers that decide how much of a page can appear inside AI Overviews
# and AI Mode, so they only make sense on pages we actually want indexed.
_AI_SNIPPET_DIRECTIVES = 'max-snippet:-1, max-image-preview:large, max-video-preview:-1'


def on_storefront_head(value, request=None, context=None, **kwargs):
    """`STOREFRONT_HEAD` subscriber. Returns the document, always."""
    try:
        return build_document(value, request=request, context=context or {})
    except Exception as e:  # noqa: BLE001 — the shell's fallback head must survive
        logger.error('seo: head build failed: %s', e, exc_info=True)
        return value


def build_document(doc, *, request=None, context=None):
    context = dict(context or {})
    # Whatever the shell seeded (`{% storefront_head title=… description=… %}`)
    # is the theme's own fallback copy — the home page's tagline, say. Feed it to
    # the resolver as if the view had supplied it, so the priority order stays
    # merchant value → view/theme copy → derived-from-the-object.
    if doc.title and not context.get('seo_title'):
        context['seo_title'] = doc.title
    seeded_description = doc.meta_content('description')
    if seeded_description and not context.get('seo_description'):
        context['seo_description'] = seeded_description

    page = resolve_page(request, context)
    doc.note(f'page kind: {page.kind}{"/" + page.subtype if page.subtype else ""}')
    _section(_apply_content_languages, page, context)

    meta = _safe_meta(page)
    # Each section is guarded on its own: a store whose markets rows are broken
    # should still get a title and a canonical, and a product whose price field
    # was deferred by the view must not cost the page its whole head.
    _section(_apply_title_and_description, doc, page, meta)
    if is_error_page(page):
        _section(_apply_error_head, doc, page)
        return doc
    _section(_apply_canonical_and_robots, doc, page, meta, request)
    _section(_apply_social, doc, page, meta)
    _section(_apply_site_links, doc, request)
    # Decided by `_apply_canonical_and_robots` above (blocked parameters, the
    # merchant's robots, thin content), so the gate reads it afterwards.
    # A page canonicalised onto another path is a duplicate of that page: it
    # declares no alternates, prev/next or graph of its own (the graph's `@id`s
    # would be the other page's, with this page's trail and items in them).
    if not page.noindex and _canonical_is_here(doc, request):
        _section(_apply_alternates, doc, page, request)
        _section(_apply_pagination, doc, page, request)
        _section(_apply_graph, doc, page, request)
    return doc


def _canonical_is_here(doc, request) -> bool:
    canonical = doc.link_href('canonical')
    return not canonical or _same_path(canonical, request)


def _section(func, *args) -> None:
    try:
        func(*args)
    except Exception as e:  # noqa: BLE001
        logger.warning('seo: head section %s failed: %s', func.__name__, e, exc_info=True)


# -- sections ------------------------------------------------------------
def _safe_meta(page: SeoPage):
    """Resolution must not be able to blank the head.

    A single object with an odd shape (a dict where a model was expected)
    would otherwise raise before the first tag was written, and the page
    would ship with only the shell's fallback title.
    """
    try:
        return _resolve_meta(page)
    except Exception as e:  # noqa: BLE001
        logger.warning('seo: meta resolution failed for %s: %s', page.path, e, exc_info=True)
        from plugins.installed.seo.services import ResolvedMeta

        return ResolvedMeta(title=page.title, description=page.description)


def _resolve_meta(page: SeoPage):
    """Merchant overrides → native model fields → the page's own defaults.

    `resolve_meta` is the long-standing precedence chain (SeoMeta wins, then the
    model's own SEO columns, then fallbacks) plus token expansion and OG-image
    absolutisation. The head builder reuses it rather than re-deriving values, so
    a merchant's saved title still wins after the pipeline moved.
    """
    from plugins.installed.seo.services import resolve_meta

    return resolve_meta(
        obj=page.obj,
        fallback_title=page.title,
        fallback_description=page.description,
        fallback_image=page.image,
        last_resort_image=page.fallback_image,
        og_type=page.og_type,
        page_kind=page.kind,
    )


def _apply_title_and_description(doc, page: SeoPage, meta) -> None:
    from plugins.installed.seo.rules import paginated_title
    from plugins.installed.seo.services.meta import format_document_title

    # "Page 2" before the brand, so a listing's pages stop sharing one title.
    clean_title = paginated_title((meta.title or page.title).strip(), page.page_obj)
    title = format_document_title(clean_title) if page.brand_title else clean_title
    if title:
        doc.set_title(title, source='seo')
    # A page with no description of its own falls back to the store's, which the
    # merchant edits in Settings → General. The theme used to hardcode that
    # sentence, so changing it meant editing a template.
    description = meta.description or page.description or _store_description()
    doc.meta(description, name='description', source='seo')
    page.description = page.description or description
    # No `<meta name="keywords">`. Engines have ignored it since 2009, and the
    # field now holds the merchant's INTERNAL focus keyword — the panel says so
    # in as many words, while the page was publishing it.


def _apply_content_languages(page: SeoPage, context: dict) -> None:
    """Which languages the page's object exists in, and which one the page shows.

    A page about one object exists in a language only when the object has a
    reviewed translation there (`core.i18n.content_languages`); a page with no
    registered object keeps every language. A view whose `seo_object` would change
    the head (a place, an event) names the object as `seo_content_object`.
    """
    from django.conf import settings
    from django.utils.translation import get_language

    from core.i18n.services import active_language, content_languages

    obj = context.get('seo_content_object') or page.obj
    if obj is None or isinstance(obj, dict):
        return
    page.languages = content_languages(obj)
    if page.languages is None:
        return
    page.language = (
        get_language() if active_language() in page.languages else settings.LANGUAGE_CODE
    ) or ''


def _shown_in_its_language(page: SeoPage) -> bool:
    from core.i18n.services import active_language

    return page.languages is None or active_language() in page.languages


def _default_language_url(url: str) -> str:
    """The same page in the store's default language."""
    from django.conf import settings
    from django.urls import translate_url

    with suppress(Exception):
        return translate_url(url, settings.LANGUAGE_CODE)
    return url


def _apply_canonical_and_robots(doc, page: SeoPage, meta, request) -> None:
    canonical, blocked_params = canonical_for(request, page.page_obj)
    owned = _owner_canonical(page.canonical, request)
    if owned:
        canonical = owned  # the page's owner names its better address
    if canonical and not _shown_in_its_language(page):
        # `/sr/x/` showing an object nobody translated is the English page: say so,
        # never `noindex` beside a canonical naming another url.
        canonical = _default_language_url(canonical)
    if meta.canonical_url:
        canonical = meta.canonical_url  # an explicit merchant override wins
    if canonical:
        doc.link('canonical', canonical, source='seo')

    if blocked_params:
        # A facet value the merchant chose not to index: keep crawling the
        # links, stop indexing the duplicate. The canonical the engine returned
        # for this case is *self*-referential — a page that says "don't index
        # me" while pointing its canonical at the category is making two
        # contradictory claims about two URLs, and the noindex can travel to
        # the canonical target and take the category down with it.
        page.deny_index(f'query parameter: {", ".join(blocked_params)}')

    # An explicit SeoMeta/native robots value is a merchant decision — honour it,
    # but never let it *open up* a page the platform holds back (a cart page with
    # `index, follow` saved on it stays private).
    explicit = (meta.robots or '').strip().lower()
    if 'noindex' in explicit and not page.noindex:
        page.deny_index('merchant set noindex')
    if 'nofollow' in explicit:
        page.nofollow = True

    _apply_thin_content_rule(page, meta)

    robots = page.robots()
    if 'noindex' not in robots:
        robots = f'{robots}, {_snippet_directives(meta)}'
    doc.meta(robots, name='robots', source='seo')
    if page.reason:
        doc.note(f'noindex: {page.reason}')
    if page.noindex and not _is_self(doc.link_href('canonical'), request):
        # `/products/?q=x` canonicalised to `/products/` — "this search result
        # is the catalogue" beside "do not index me". Say nothing instead.
        doc.remove('link:canonical')


def _owner_canonical(value: str, request) -> str:
    """A page's own canonical (`SeoPage.canonical`) as an absolute url, or ''.

    A path, or an absolute http(s) url on the host being served: anything else would
    hand this page's ranking to another site, so it is ignored.
    """
    value = (value or '').strip()
    if not value or request is None:
        return ''
    try:
        if value.startswith('/') and not value.startswith('//'):
            return request.build_absolute_uri(value)
        parts = urlsplit(value)
        if parts.scheme in ('http', 'https') and parts.netloc == request.get_host():
            return value
    except Exception:  # noqa: BLE001
        return ''
    return ''


def _apply_error_head(doc, page: SeoPage) -> None:
    """Robots for a page that does not exist — the only other thing it says."""
    doc.meta(page.robots(), name='robots', source='seo')
    doc.note(f'noindex: {page.reason or "error page"}')


def _is_self(canonical: str, request) -> bool:
    """Does `canonical` name exactly the URL being rendered (same path, same query)?"""
    if not canonical or request is None:
        return False
    try:
        current = urlsplit(request.build_absolute_uri())
    except Exception:  # noqa: BLE001
        return False
    target = urlsplit(canonical)
    return (target.path or '/') == (current.path or '/') and sorted(
        parse_qsl(target.query, keep_blank_values=True)
    ) == sorted(parse_qsl(current.query, keep_blank_values=True))


def _apply_thin_content_rule(page: SeoPage, meta) -> None:
    """Hold back a product page whose description is too short to rank.

    The merchant sets the word threshold in SEO settings ("Auto-noindex PDPs
    with descriptions shorter than N words"); 0 — the default — disables it.
    The knob has existed since v0.2 and, since the head moved off the template
    tags in v0.46, had NO consumer at all: setting it did nothing, which is
    exactly the kind of control-shaped-like-a-mechanism this codebase keeps
    getting bitten by.
    """
    if page.kind != KIND_PRODUCT or page.noindex:
        return
    from plugins.installed.seo.services import _seo_plugin_cfg

    try:
        threshold = int((_seo_plugin_cfg() or {}).get('noindex_thin_pdp_below_words') or 0)
    except (TypeError, ValueError):
        return
    if threshold <= 0:
        return
    text = (meta.description or page.description or '').strip()
    words = len(text.split())
    if words < threshold:
        page.deny_index(f'thin description: {words} words, minimum {threshold}')


def _snippet_directives(meta) -> str:
    """How much of the page engines — and AI Overviews — may reproduce.

    Defaults to "as much as you like", which is what a store selling things
    wants. A merchant can tighten it per entity through the panel's advanced
    robots settings, which is the only lever Google offers over AI Mode input.
    """
    extra = getattr(meta, 'robots_extra', None) or {}
    if not isinstance(extra, dict) or not extra:
        return _AI_SNIPPET_DIRECTIVES
    parts: list[str] = []
    if extra.get('nosnippet'):
        parts.append('nosnippet')
    else:
        snippet = extra.get('max_snippet', -1)
        parts.append(f'max-snippet:{int(snippet)}')
        preview = str(extra.get('max_image_preview') or 'large').lower()
        parts.append(
            f'max-image-preview:{preview if preview in {"none", "standard", "large"} else "large"}'
        )
        parts.append(f'max-video-preview:{int(extra.get("max_video_preview", -1))}')
    if extra.get('noimageindex'):
        parts.append('noimageindex')
    if extra.get('unavailable_after'):
        parts.append(f'unavailable_after: {extra["unavailable_after"]}')
    return ', '.join(parts)


def _apply_social(doc, page: SeoPage, meta) -> None:
    og_title = meta.og_title or meta.title or page.title
    og_description = meta.og_description or meta.description or page.description
    canonical = doc.link_href('canonical')

    doc.meta(og_title, property='og:title', source='seo')
    doc.meta(og_description, property='og:description', source='seo')
    doc.meta(meta.og_type or page.og_type or 'website', property='og:type', source='seo')
    doc.meta(canonical, property='og:url', source='seo')
    doc.meta(meta.site_name, property='og:site_name', source='seo')
    doc.meta(_og_locale(page), property='og:locale', source='seo')

    if meta.og_image:
        doc.meta(meta.og_image, property='og:image', source='seo')
        doc.meta(meta.og_image, property='og:image:secure_url', source='seo')
        # The size only when the file says it: every og:image was declared
        # 1200x630 until v0.83.6, square product photos included.
        from plugins.installed.seo.services.images import image_size

        if _same_site(meta.og_image):
            size = image_size(meta.og_image)
            if size:
                doc.meta(str(size[0]), property='og:image:width', source='seo')
                doc.meta(str(size[1]), property='og:image:height', source='seo')
        doc.meta(og_title, property='og:image:alt', source='seo')

    doc.meta(meta.twitter_card or 'summary_large_image', name='twitter:card', source='seo')
    if meta.twitter_site:
        handle = meta.twitter_site if meta.twitter_site.startswith('@') else f'@{meta.twitter_site}'
        doc.meta(handle, name='twitter:site', source='seo')
    doc.meta(meta.twitter_title or og_title, name='twitter:title', source='seo')
    doc.meta(meta.twitter_description or og_description, name='twitter:description', source='seo')
    doc.meta(meta.og_image, name='twitter:image', source='seo')

    # Product pages carry price + availability in Open Graph too: the social
    # scrapers and several shopping surfaces read these before the JSON-LD.
    if page.kind == KIND_PRODUCT:
        _apply_product_og(doc, page)


def _same_site(url: str) -> bool:
    """True for a relative URL or one on this store's host (only those are ours to measure)."""
    from core.utils.site import site_base_url

    host = (urlsplit(url).hostname or '').lower()
    return not host or host == (urlsplit(site_base_url()).hostname or '').lower()


def _apply_product_og(doc, page: SeoPage) -> None:
    product = page.rendered or page.obj
    if product is None:
        return
    price = _product_price(product)
    if price:
        doc.meta(price[0], property='product:price:amount', source='seo')
        doc.meta(price[1], property='product:price:currency', source='seo')
    # Open Graph has its own availability vocabulary ('in stock'), distinct from
    # the schema.org URL the JSON-LD carries. Emitting the schema URL here would
    # be invalid OG — the two must not be conflated.
    availability = _product_availability(product)
    if availability:
        doc.meta(
            'in stock' if availability.endswith('InStock') else 'out of stock',
            property='product:availability',
            source='seo',
        )

    # The plain-text mirror of this product, for LLM crawlers that would rather
    # read Markdown than parse a storefront.
    slug = product.get('slug') if isinstance(product, dict) else getattr(product, 'slug', '')
    if slug:
        doc.link(
            'alternate',
            f'/md/products/{slug}',
            key='link:alternate:markdown',
            type='text/markdown',
            title='Plain-text product description for LLM crawlers',
            source='seo',
        )


def _apply_site_links(doc, request) -> None:
    """Verification metas, CDN preconnect and the LLM discovery hint."""
    from plugins.installed.seo.services import _seo_plugin_cfg, site_settings

    try:
        settings_row = site_settings()
    except Exception:  # noqa: BLE001 — unmigrated DB during boot
        return

    for name, value in (
        ('google-site-verification', settings_row.google_site_verification),
        ('msvalidate.01', settings_row.bing_verification),
        ('p:domain_verify', settings_row.pinterest_verification),
        ('facebook-domain-verification', settings_row.facebook_domain_verification),
    ):
        doc.meta(value or '', name=name, source='seo')

    host = ((_seo_plugin_cfg() or {}).get('preconnect_to_cdn') or '').strip()
    if host:
        if not host.startswith(('http://', 'https://')):
            host = f'https://{host}'
        doc.link('preconnect', host, key='link:preconnect:cdn', crossorigin='', source='seo')
        doc.link('dns-prefetch', host, key='link:dns-prefetch:cdn', source='seo')

    if getattr(settings_row, 'llms_txt_enabled', False):
        doc.link(
            'alternate',
            '/llms.txt',
            key='link:alternate:llms',
            type='text/plain',
            title='LLM-friendly site map',
            source='seo',
        )

    # OpenSearch autodiscovery — the browser's address-bar search. The theme used
    # to hardcode this path, which 404'd whenever the seo app was disabled.
    doc.link(
        'search',
        '/opensearch.xml',
        key='link:search:opensearch',
        type='application/opensearchdescription+xml',
        title=_brand(),
        source='seo',
    )


def _apply_alternates(doc, page: SeoPage, request) -> None:
    """hreflang for languages.

    A language alternate is a different URL of the same page (`/fr/products/x/`).
    A market is not one: it changes the currency, never the page, so it declares
    no alternate (markets release 1; the `?market=` alternates are gone). One
    `x-default` names the default-language url for the whole cluster — see
    `_x_default_href`.

    Every href is derived from the CANONICAL, never from the request. Built from
    `build_absolute_uri()`, each alternate echoed whatever the visitor arrived
    with — `?utm_source=`, `?fbclid=` — while the canonical beside it had already
    dropped them, and Google ignores an alternate that is not a canonical URL. A
    page canonicalised onto another path is a duplicate and declares nothing.
    """
    canonical = doc.link_href('canonical')
    if not canonical or not _same_path(canonical, request):
        return
    languages = _language_alternates(canonical, page)
    for code, href in languages:
        doc.link('alternate', href, hreflang=code, source='seo')
    if not languages:
        return
    default = _x_default_href(languages, _without_market(canonical))
    if default:
        doc.link('alternate', default, hreflang='x-default', source='seo')


def _same_path(url: str, request) -> bool:
    if request is None:
        return False
    try:
        return (urlsplit(url).path or '/') == (urlsplit(request.build_absolute_uri()).path or '/')
    except Exception:  # noqa: BLE001
        return False


def _without_market(url: str) -> str:
    parts = urlsplit(url)
    rest = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != 'market']
    return urlunsplit(parts._replace(query=urlencode(rest)))


def _x_default_href(languages: list[tuple[str, str]], canonical: str) -> str:
    """`x-default` names ONE url for the whole cluster: the default language.

    It used to be the *current* page's canonical, which meant every page
    declared itself the default — so a bilingual store shipped two conflicting
    `x-default` claims per cluster (`/` said `/`, `/sr/` said `/sr/`) and the
    annotation carried no information at all. It reads as valid markup either
    way, which is why it survived a live crawl of 346 urls.

    With no language axis (a market-only store) the canonical IS the default.
    """
    from django.conf import settings

    if not languages:
        return canonical
    wanted = (getattr(settings, 'LANGUAGE_CODE', '') or '').lower()
    by_code = {code.lower(): href for code, href in languages}
    # `LANGUAGE_CODE` may be regional (`en-us`) while `LANGUAGES` lists the
    # base tag (`en`), so fall back to the base before giving up.
    return by_code.get(wanted) or by_code.get(wanted.split('-')[0]) or languages[0][1]


def _apply_pagination(doc, page: SeoPage, request) -> None:
    for rel, href in paginated_links(request, page.page_obj).items():
        doc.link(rel, href, source='seo')


def _apply_graph(doc, page: SeoPage, request) -> None:
    from plugins.installed.seo.schema import build_graph

    # The graph describes the canonical URL: built from the request, the
    # WebPage `@id` carried `?utm_source=` on every campaign landing.
    graph = build_graph(page, request=request, url=doc.link_href('canonical'))
    if graph:
        doc.jsonld(graph, source='seo')


# -- helpers -------------------------------------------------------------
def _og_locale(page: SeoPage | None = None) -> str:
    """The language the main content is in: the default one for an untranslated object."""
    from django.utils.translation import get_language

    language = (page.language if page is not None else '') or get_language() or 'en-US'
    return language.replace('-', '_')


def _brand() -> str:
    from plugins.installed.seo.services.meta import brand_name

    return brand_name() or 'Search'


def _store_description() -> str:
    """The merchant's site-wide meta description (Settings → General)."""
    from plugins.installed.seo.services._helpers import strip_html

    try:
        from core.models import StoreSettings

        store = StoreSettings.objects.first()
        return strip_html(getattr(store, 'meta_description', '') or '')[:320]
    except Exception:  # noqa: BLE001 — unmigrated DB during boot
        return ''


def _language_alternates(canonical: str, page: SeoPage | None = None) -> list[tuple[str, str]]:
    """One alternate per language the page exists in, using the i18n URL prefix.

    Only meaningful once the store actually serves more than one language —
    `LANGUAGES` is derived from `MORPHEUS_LANGUAGES`, so a single-language shop
    emits nothing and keeps a clean head. A page about one object names only the
    languages the object has a reviewed translation in (`page.languages`), so an
    object nobody translated declares no alternates at all.
    """
    from django.conf import settings
    from django.urls import translate_url

    languages = [code for code, _ in (getattr(settings, 'LANGUAGES', None) or [])]
    available = getattr(page, 'languages', None)
    if available is not None:
        languages = [code for code in languages if code.lower() in available]
    if not canonical or len(languages) < 2:
        return []
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for code in languages:
        # An untranslatable URL (a route outside i18n_patterns) is not fatal —
        # it simply has no alternate in that language. `translate_url` hands
        # back its input when it cannot translate, so an href already claimed
        # by another language is that failure, not a second alternate.
        with suppress(Exception):
            href = translate_url(canonical, code)
            if href not in seen:
                seen.add(href)
                out.append((code, href))
    return out if len(out) > 1 else []


def _product_price(product) -> tuple[str, str] | None:
    """(amount, currency) from a model or the PDP's GraphQL dict.

    The PDP renders a product the view loaded with `price` DEFERRED — touching
    the attribute then raises `KeyError` out of djmoney rather than lazily
    loading, so this must never assume the field is there.
    """
    if isinstance(product, dict):
        price = product.get('price')
        if isinstance(price, dict):
            amount, currency = price.get('amount'), price.get('currency')
        else:
            amount, currency = price, product.get('currency')
    else:
        deferred = getattr(product, 'get_deferred_fields', None)
        if callable(deferred) and 'price' in (deferred() or ()):
            return None
        try:
            money = getattr(product, 'price', None)
        except Exception:  # noqa: BLE001 — deferred / unsaved instance
            return None
        amount = getattr(money, 'amount', None)
        currency = str(getattr(money, 'currency', '') or '')
    if amount in (None, ''):
        return None
    return f'{amount}', (currency or 'USD')


def _product_availability(product) -> str:
    from plugins.feed_mapping import availability_to_schema

    try:
        return availability_to_schema(product)
    except Exception:  # noqa: BLE001
        return ''
