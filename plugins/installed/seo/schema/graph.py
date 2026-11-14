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

from plugins.installed.seo.pages.resolve import _item_count
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

# No `speakable`: Google reads it only to answer topical news queries, for users
# in the U.S. whose Google Home devices are set to English, and calls it a beta
# (Search Central, appearance/structured-data/speakable, read 2026-11-12). These
# stores sell goods and trips; the property claimed a use no reader makes of it.

# An article's `articleBody` is kept under 5,000 characters: the graph is in every
# page's head, and the reader already has the whole text below it.
_ARTICLE_BODY_LIMIT = 4999


def build_graph(page: SeoPage, *, request=None, url: str = '') -> dict | None:
    """Assemble `{'@context': …, '@graph': [...]}` for a resolved page.

    `url` is the page's canonical. The head builder passes it so every `@id`
    names the URL the page claims to be, not the one the visitor arrived at.
    """
    base = _base_url()
    url = url or _absolute(request, page.path)
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

    breadcrumb = _safe(_breadcrumb, page, url, request)
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
    # After every app's nodes, so a merchant's block never doubles one of them.
    _safe(_add_editor_blocks, graph, page, url)
    _safe(_absolute_list_urls, graph, base)
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
        # The language the main content is in: the default one for an untranslated object.
        'inLanguage': page.language or _language(),
    }
    if page.description:
        node['description'] = page.description[:400]
    if page.image:
        node['primaryImageOfPage'] = page.image
    if org:
        node['publisher'] = {'@id': org['@id']}
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


def _breadcrumb(page: SeoPage, url: str, request=None) -> dict | None:
    from core.i18n_links import localize_url, page_language
    from plugins.installed.seo.services import breadcrumb_jsonld

    items = [i for i in (page.breadcrumbs or []) if i and i.get('name')]
    if not items:
        return None
    # On a /sr/ page the trail is the Serbian tree. Views build it with
    # build_absolute_uri('/'), which names the English one.
    language = page_language(request) if request is not None else ''
    if language:
        host = request.get_host()
        items = [{**i, 'url': localize_url(i.get('url') or '', language, host)} for i in items]
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
            # the node stands alone — but beside a dedicated Book node it means
            # two Book-typed nodes describing the same thing, the duplication
            # this graph exists to end.
            #
            # Remove ONLY 'Book'. Flattening the whole list to 'Product' also
            # erased 'ProductGroup', so a book sold in several editions kept its
            # hasVariant / variesBy / productGroupID while declaring itself a
            # plain Product — properties that belong to ProductGroup and which
            # Google therefore ignores.
            if product and isinstance(product.get('@type'), list):
                kept = [t for t in product['@type'] if t != 'Book']
                product['@type'] = kept[0] if len(kept) == 1 else (kept or 'Product')

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
    # The list is the whole listing, not this page of it: schema.org's
    # numberOfItems counts every item across the pages, and the positions go
    # on from the previous page.
    total = _item_count(page, page.context)
    start = getattr(page.page_obj, 'start_index', None)
    start = start() if callable(start) else 1
    node = _safe(
        collection_page_jsonld,
        name=page.title or 'Collection',
        url=url,
        description=page.description or '',
        items=normalised,
        offers=_safe(aggregate_offer, prices, currency),
        total=max(total, len(normalised)) if total is not None else None,
        start=start if isinstance(start, int) and start > 0 else 1,
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
    from core.text import clip, plain_text
    from plugins.installed.seo.services import article_jsonld

    entry = page.context.get('entry') or page.obj
    if not entry:
        return []
    get = entry.get if isinstance(entry, dict) else lambda k, d=None: getattr(entry, k, d)
    node = _safe(
        article_jsonld,
        headline=str(get('title') or page.title or ''),
        # The text a reader sees: markdown's markers and the tags gone, entities
        # read, one space between words, cut at a sentence or word (v0.163.0).
        body=clip(plain_text(get('body') or ''), _ARTICLE_BODY_LIMIT),
        url=url,
        kind='BlogPosting',
        description=str(get('excerpt') or page.description or ''),
        author=str(get('author') or ''),
        published_at=get('published_at') or get('publish_at'),
        updated_at=get('updated_at'),
        image=str(get('image') or page.image or ''),
        # E-E-A-T + provenance. `journal_dict` has assembled these since v0.46
        # and the themes' journal templates passed them to `seo_article_jsonld`
        # (removed in v0.164.0), which the head contract shimmed to '': the GRAPH
        # is what ships, so every author sameAs and citation the merchant entered
        # was silently dropped on every live article until it read them here.
        word_count=get('word_count') or None,
        author_same_as=get('author_same_as') or None,
        citations=get('citations') or None,
    )
    node = _strip_context(node)
    if not node:
        return []
    node['@id'] = f'{url}#article'
    return [node]


def _add_editor_blocks(graph: dict, page: SeoPage, url: str) -> None:
    """The schema editor's blocks for the page's object (``SeoMeta.schema_blocks``).

    A block whose type the graph already holds is skipped, whoever wrote it:
    one page, one FAQPage or VideoObject. Types the store's apps own are refused
    by ``schema_types.build_blocks`` before they get here.
    """
    if page.obj is None:
        return
    from plugins.installed.seo.models import SeoMeta
    from plugins.installed.seo.schema_types import build_blocks

    meta = SeoMeta.for_obj(page.obj)
    if meta is None or not meta.schema_blocks:
        return
    nodes = graph.setdefault('@graph', [])
    present = set()
    for node in nodes:
        present.update(_types_of(node))
    for number, block in enumerate(build_blocks(meta.schema_blocks), start=1):
        kinds = _types_of(block)
        if not kinds or kinds & present:
            continue
        node = _strip_context(block)
        node['@id'] = f'{url}#schema-{number}'
        nodes.append(node)
        present.update(kinds)


def _types_of(node) -> set[str]:
    kind = node.get('@type') if isinstance(node, dict) else None
    if isinstance(kind, str):
        return {kind}
    if isinstance(kind, list):
        return {k for k in kind if isinstance(k, str)}
    return set()


def _absolute_list_urls(graph: dict, base: str) -> None:
    """Every ItemList entry's ``url`` and ``image`` (and its item's) absolute,
    whoever built the list.

    Themes and apps hand the graph site-relative paths (``/products/x/``); a
    crawler reading the list out of context cannot resolve them.
    """

    def walk(node):
        if isinstance(node, list):
            for child in node:
                walk(child)
        elif isinstance(node, dict):
            if node.get('@type') == 'ItemList':
                for entry in node.get('itemListElement') or []:
                    _absolute_entry(entry, base)
            for value in node.values():
                walk(value)

    walk(graph.get('@graph'))


def _absolute_entry(entry, base: str) -> None:
    if not isinstance(entry, dict):
        return
    item = entry.get('item')
    if isinstance(item, str):
        entry['item'] = _absolute_path(item, base)
    for holder in (entry, item if isinstance(item, dict) else {}):
        for key in ('url', 'image'):
            if key in holder:
                holder[key] = _absolute_path(holder[key], base)


def _absolute_path(value, base: str):
    if isinstance(value, str) and value.startswith('/') and not value.startswith('//'):
        return f'{base}{value}'
    return value


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
