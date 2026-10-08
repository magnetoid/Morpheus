"""hreflang for a book's language editions, through the head document.

A translated work is several products — one per language — linked through
`BookProduct.translation_of`. Each edition's page names the others as its
language alternates. The dot_books theme used to print those `<link>`s itself
in the product template: outside the head document, so beside whatever the seo
app emitted, with no check that the page was indexable, and with whatever the
`language` field held (`English`) as the hreflang code.

Now this app adds them to the document after the seo app has decided the page:
only on an indexable product page, only when the store serves ONE interface
language (a multilingual store's hreflang axis is its UI languages, and the two
cannot share `link:alternate:<code>` keys), and with ISO codes.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger('morpheus.book_product')


def on_storefront_head(value, request=None, context=None, **kwargs):
    """STOREFRONT_HEAD — runs after seo; adds edition alternates to a product page."""
    try:
        _add_edition_alternates(value, request)
    except Exception as e:  # noqa: BLE001 — the head must survive a bad edition graph
        logger.warning('book_product: edition hreflang failed: %s', e, exc_info=True)
    return value


def _add_edition_alternates(doc, request) -> None:
    from django.conf import settings

    from core.utils.i18n import localized_path
    from plugins.installed.book_product.facets import canonical_language
    from plugins.installed.book_product.models import BookProduct

    match = getattr(request, 'resolver_match', None)
    if match is None or getattr(match, 'view_name', '') != 'storefront:product_detail':
        return
    if len(getattr(settings, 'LANGUAGES', None) or []) > 1:
        return
    if 'noindex' in (doc.meta_content('robots') or ''):
        return
    canonical = doc.link_href('canonical')
    slug = (match.kwargs or {}).get('slug')
    if not canonical or not slug:
        return
    book = (
        BookProduct.objects.filter(product__slug=slug, product__status='active')
        .select_related('product', 'translation_of')
        .first()
    )
    if book is None:
        return
    editions = book.language_editions()
    if len(editions) < 2:
        return
    origin = urlsplit(canonical)
    # The page's own edition last, so where two editions share a language the
    # page names itself — an hreflang set must include the page it is on.
    for edition in sorted(editions, key=lambda e: e.pk == book.pk):
        code = canonical_language(edition.language or 'en')
        if not code:
            continue
        path = localized_path(request, f'/products/{edition.product.slug}/')
        href = (
            canonical if edition.pk == book.pk else urlunsplit(origin._replace(path=path, query=''))
        )
        doc.link('alternate', href, hreflang=code, source='book_product')
