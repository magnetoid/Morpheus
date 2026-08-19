"""Build the page's JSON-LD graph.

The node set is decided by the page kind; the *data* comes from the template
context, using the same conventional keys the storefront has always populated
(`plp_items`, `breadcrumb_items`, `product_seo_extra`, `entry`, …). That is what
makes this work for an arbitrary theme: a theme supplies content, not markup,
and any theme that renders a list of products through the usual context keys
gets a correct ItemList without writing a line of schema.

Everything is defensive. A graph that raises would take a product page down; a
graph that silently omits a node costs a rich result. Both are bad, but only one
is an outage — so every builder here is individually guarded.
"""

from __future__ import annotations

import logging
from contextlib import suppress

from plugins.installed.seo.pages.types import (
    KIND_ARTICLE,
    KIND_LISTING,
    KIND_PRODUCT,
    KIND_SEARCH,
    SeoPage,
)

logger = logging.getLogger('morpheus.seo')

# Context keys that hold "the things this page lists", most specific first. A
# theme picks whichever name fits its template; the graph does not care.
_ITEM_KEYS = (
    'plp_items',
    'collection_items',
    'bib_items',
    'post_items',
    'cat_items',
    'pick_items',
    'jsonld_items',
    'search_items',
)

# The parts of a page a voice assistant may read aloud. Kept as a graph property
# on WebPage rather than its own block — `speakable` is a property, and emitting
# it as a standalone node was always a workaround for having no graph.
_SPEAKABLE_SELECTORS = ['h1', '[data-speakable]', '.product-summary', '.entry-summary']


def build_graph(page: SeoPage, *, request=None) -> dict | None:
    """Assemble `{'@context': …, '@graph': [...]}` for a resolved page."""
    base = _base_url()
    url = _absolute(request, page.path)
    nodes: list[dict] = []

    org = _safe(_organization)
    if org:
        org['@id'] = f'{base}#organization'
        nodes.append(org)

    website = _safe(_website)
    if website:
        website['@id'] = f'{base}#website'
        if org:
            website['publisher'] = {'@id': org['@id']}
        nodes.append(website)

    webpage = _webpage(page, url, website, org)
    if webpage:
        nodes.append(webpage)

    breadcrumb = _safe(_breadcrumb, page, url)
    if breadcrumb:
        nodes.append(breadcrumb)
        if webpage:
            webpage['breadcrumb'] = {'@id': breadcrumb['@id']}

    for node in _kind_nodes(page, url, base):
        # A listing's ItemList belongs TO the page, not beside it: bind it as
        # `mainEntity` so the graph says "this URL is a list of these things"
        # rather than shipping an orphan list a crawler has to guess about.
        if webpage is not None and node.get('@type') == 'ItemList':
            webpage['mainEntity'] = node
            continue
        nodes.append(node)

    graph = {'@context': 'https://schema.org', '@graph': [n for n in nodes if n]}
    graph = _fire_filter(graph, page, request)
    return graph if graph.get('@graph') else None


def graph_for_object(obj) -> dict | None:
    """The graph for a single object, outside a request.

    This is what answers `SEO_STRUCTURED_DATA_FOR_OBJECT`, so GraphQL's
    `structuredData` fields stop importing seo's internals.
    """
    from plugins.installed.seo.services import _structured_data_for, product_jsonld

    if obj is None:
        return None
    try:
        if obj.__class__.__name__ == 'Product':
            return product_jsonld(obj)
        return _structured_data_for(
            obj,
            title=str(getattr(obj, 'name', '') or ''),
            description=str(getattr(obj, 'description', '') or ''),
            image='',
        )
    except Exception as e:  # noqa: BLE001
        logger.debug('seo: structured data for %r failed: %s', obj, e)
        return None


# -- node builders -------------------------------------------------------
def _organization() -> dict | None:
    from plugins.installed.seo.services import organization_jsonld

    return _strip_context(organization_jsonld())


def _website() -> dict | None:
    from plugins.installed.seo.services import website_jsonld

    node = _strip_context(website_jsonld())
    if node:
        # Google retired the sitelinks search box on 2024-11-21: the markup is
        # ignored, so emitting it is noise the validator would have to excuse.
        node.pop('potentialAction', None)
    return node


def _webpage(page: SeoPage, url: str, website: dict | None, org: dict | None) -> dict | None:
    if not url:
        return None
    node = {
        '@type': _webpage_type(page),
        '@id': f'{url}#webpage',
        'url': url,
        'name': page.title or '',
        'isPartOf': {'@id': website['@id']} if website else None,
        'inLanguage': _language(),
    }
    if page.description:
        node['description'] = page.description[:400]
    if page.image:
        node['primaryImageOfPage'] = page.image
    if org:
        node['publisher'] = {'@id': org['@id']}
    if page.kind in (KIND_PRODUCT, KIND_ARTICLE):
        node['speakable'] = {
            '@type': 'SpeakableSpecification',
            'cssSelector': _SPEAKABLE_SELECTORS,
        }
    return {k: v for k, v in node.items() if v not in (None, '', [])}


def _webpage_type(page: SeoPage) -> str:
    if page.kind == KIND_SEARCH:
        return 'SearchResultsPage'
    if page.subtype == 'about':
        return 'AboutPage'
    if page.subtype == 'contact':
        return 'ContactPage'
    if page.kind == KIND_LISTING:
        return 'CollectionPage'
    return 'WebPage'


def _breadcrumb(page: SeoPage, url: str) -> dict | None:
    from plugins.installed.seo.services import breadcrumb_jsonld

    items = [i for i in (page.breadcrumbs or []) if i and i.get('name')]
    if not items:
        return None
    node = _strip_context(breadcrumb_jsonld(items))
    if node:
        node['@id'] = f'{url}#breadcrumb'
    return node


def _kind_nodes(page: SeoPage, url: str, base: str) -> list[dict]:
    if page.kind == KIND_PRODUCT:
        return _product_nodes(page, url)
    if page.kind in (KIND_LISTING, KIND_SEARCH):
        nodes = _list_nodes(page, url)
        person = _person_node(page, url)
        return [*nodes, person] if person else nodes
    if page.kind == KIND_ARTICLE:
        return _article_nodes(page, url)
    return []


def _person_node(page: SeoPage, url: str) -> dict | None:
    """An author landing describes a Person, not just a list of their books.

    Entity pages are how a search engine connects "books by X" across a site;
    without the Person node the page is an anonymous list.
    """
    if page.subtype != 'author':
        return None
    name = str(page.context.get('author_name') or page.title or '').strip()
    if not name:
        return None
    return {'@type': 'Person', '@id': f'{url}#person', 'name': name, 'url': url}


def _product_nodes(page: SeoPage, url: str) -> list[dict]:
    from plugins.installed.seo.services import (
        book_jsonld,
        faq_jsonld,
        product_jsonld,
        qa_page_jsonld,
        video_jsonld,
    )

    ctx = page.context
    nodes: list[dict] = []

    # BOTH, and the distinction is load-bearing. The rendered payload is what
    # the shopper sees, so price and availability come from it (the view's model
    # row has `price` deferred). The model row is the only way to reach the
    # things a merchant listing is judged on — the image gallery, GTIN/ISBN
    # identifiers, aggregateRating, reviews, the Book subtype — and passing only
    # the dict is why none of them appeared on a single product page.
    subject = page.rendered or page.obj
    model = page.obj if page.rendered is not None else None
    product = _safe(product_jsonld, subject, extra=ctx.get('product_seo_extra'), model=model)
    if product:
        product = _strip_context(product)
        product['@id'] = f'{url}#product'
        product.setdefault('url', url)
        nodes.append(product)

    book_data = ctx.get('book_jsonld_data')
    if book_data:
        book = _strip_context(_safe(book_jsonld, book_data))
        if book:
            nodes.append(book)
            # One Book claim per page. `product_jsonld` upgrades a book's @type
            # to ['Product', 'Book'] from its metafields, which is right when
            # the Product node stands alone — but beside a dedicated Book node
            # it means two Book-typed nodes describing the same thing, the
            # duplication this graph exists to end.
            if product and isinstance(product.get('@type'), list):
                product['@type'] = 'Product'

    videos = ctx.get('video_seo')
    if videos:
        for video in _safe(video_jsonld, videos) or []:
            stripped = _strip_context(video)
            if stripped:
                nodes.append(stripped)

    faqs = ctx.get('pdp_faqs')
    if faqs:
        # FAQ rich results ended on 2026-05-07, but the markup still describes
        # the page's content for answer engines, which read entity data rather
        # than rich-result eligibility.
        for builder, args in (
            (faq_jsonld, (faqs,)),
            (qa_page_jsonld, ()),
        ):
            node = (
                _safe(builder, *args)
                if args
                else _safe(builder, name=_product_name(page), url=url, qa=faqs)
            )
            stripped = _strip_context(node)
            if stripped:
                nodes.append(stripped)
    return nodes


def _list_nodes(page: SeoPage, url: str) -> list[dict]:
    """CollectionPage's ItemList — merged INTO the WebPage node's mainEntity.

    A listing page is one thing, not two: the previous implementation emitted a
    standalone CollectionPage alongside the page's own, so a category page
    carried two CollectionPage nodes describing the same URL.
    """
    from plugins.installed.seo.services import aggregate_offer, collection_page_jsonld

    items = _first_items(page.context)
    if not items:
        return []
    normalised, prices, currency = _normalise_items(items)
    node = _safe(
        collection_page_jsonld,
        name=page.title or 'Collection',
        url=url,
        description=page.description or '',
        items=normalised,
        offers=_safe(aggregate_offer, prices, currency),
    )
    node = _strip_context(node)
    if not node:
        return []
    main_entity = node.get('mainEntity')
    if main_entity:
        main_entity['@id'] = f'{url}#itemlist'
    # The list belongs to the page node; return only the ItemList so we never
    # emit a second page-level node for the same URL.
    return [main_entity] if main_entity else []


def _article_nodes(page: SeoPage, url: str) -> list[dict]:
    from plugins.installed.seo.services import article_jsonld
    from plugins.installed.seo.services._helpers import strip_html

    entry = page.context.get('entry') or page.obj
    if not entry:
        return []
    get = entry.get if isinstance(entry, dict) else lambda k, d=None: getattr(entry, k, d)
    node = _safe(
        article_jsonld,
        headline=str(get('title') or page.title or ''),
        body=strip_html(get('body') or '')[:5000],
        url=url,
        kind='BlogPosting',
        description=str(get('excerpt') or page.description or ''),
        author=str(get('author') or ''),
        published_at=get('published_at') or get('publish_at'),
        updated_at=get('updated_at'),
        image=str(get('image') or page.image or ''),
    )
    node = _strip_context(node)
    if not node:
        return []
    node['@id'] = f'{url}#article'
    return [node]


# -- plumbing ------------------------------------------------------------
def _fire_filter(graph: dict, page: SeoPage, request) -> dict:
    try:
        from core.hooks import MorpheusEvents, hook_registry

        result = hook_registry.filter(
            MorpheusEvents.SEO_JSONLD_GRAPH, graph, page=page, request=request
        )
    except Exception as e:  # noqa: BLE001 — a bad enricher must not lose the graph
        logger.warning('seo: SEO_JSONLD_GRAPH failed: %s', e, exc_info=True)
        return graph
    return result if isinstance(result, dict) and result.get('@graph') else graph


def _safe(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:  # noqa: BLE001
        logger.debug('seo: graph node %s failed: %s', getattr(func, '__name__', func), e)
        return None


def _strip_context(node):
    """Drop the per-node `@context` — the graph carries one for all of them."""
    if not isinstance(node, dict):
        return None
    return {k: v for k, v in node.items() if k != '@context'}


def _first_items(context: dict) -> list:
    for key in _ITEM_KEYS:
        items = context.get(key)
        if items:
            return list(items)
    return []


def _normalise_items(items: list) -> tuple[list[dict], list, str]:
    normalised: list[dict] = []
    prices: list = []
    currency = ''
    for item in items:
        if not isinstance(item, dict):
            continue
        image = item.get('image') or ''
        primary = item.get('primaryImage')
        if not image and isinstance(primary, dict):
            image = primary.get('url') or ''
        normalised.append(
            {
                'name': item.get('name') or item.get('title') or '',
                'url': item.get('url') or '',
                'image': image,
            }
        )
        price = item.get('price')
        if price is None:
            continue
        if isinstance(price, dict):
            prices.append(price.get('amount'))
            currency = currency or str(price.get('currency') or '')
        else:
            prices.append(getattr(price, 'amount', price))
            currency = currency or str(getattr(price, 'currency', '') or '')
    return normalised, prices, currency


def _product_name(page: SeoPage) -> str:
    obj = page.rendered or page.obj
    if isinstance(obj, dict):
        return str(obj.get('name') or page.title or 'Q&A')
    return str(getattr(obj, 'name', '') or page.title or 'Q&A')


def _base_url() -> str:
    from morpheus.core import site_base_url

    return site_base_url().rstrip('/')


def _absolute(request, path: str) -> str:
    if request is not None:
        with suppress(Exception):
            return request.build_absolute_uri()
    return f'{_base_url()}{path}' if path else _base_url()


def _language() -> str:
    from django.utils.translation import get_language

    return get_language() or 'en'
