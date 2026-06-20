"""Dashboard product-edit integration for Book Product.

`admin_dashboard.product_edit` calls these (guarded by try/except), so the
book logic lives here in the owning plugin — disabling/removing book_product
removes the widget with no dangling code in admin_dashboard.
"""

from __future__ import annotations

from typing import Any

# Book fields read straight off the POST as strings.
_TEXT_FIELDS = (
    'author',
    'subtitle',
    'publisher',
    'imprint',
    'edition',
    'language',
    'series',
    'series_position',
    'synopsis',
    'binding',
    'print_type',
    'paper_type',
)
_INT_FIELDS = ('page_count', 'width_mm', 'height_mm', 'spine_mm', 'weight_g')


def book_widget_context(product) -> dict[str, Any]:
    """Context for the 'Book details' card on the product-edit page."""
    from django.utils.text import slugify  # noqa: PLC0415

    from plugins.installed.book_product.models import (  # noqa: PLC0415
        BookProduct,
        Genre,
        PaperType,
        PrintType,
        Topic,
    )

    book = BookProduct.objects.filter(product=product).first()
    selected_genres = {str(i) for i in book.genres.values_list('id', flat=True)} if book else set()
    selected_topics = {str(i) for i in book.topics.values_list('id', flat=True)} if book else set()
    return {
        'book': book,
        'print_types': PrintType.choices,
        'paper_types': PaperType.choices,
        'facets': _facets(book, slugify) if book else [],
        'all_genres': list(Genre.objects.filter(is_active=True)),
        'all_topics': list(Topic.objects.filter(is_active=True)),
        'selected_genre_ids': selected_genres,
        'selected_topic_ids': selected_topics,
        'identifiers': _book_identifiers(product),
    }


def _book_identifiers(product) -> dict[str, str]:
    """Current ISBN / OCLC / Open Library values for the edit form. ISBN-13
    lives in the 'identifiers' metafield namespace (the canonical store read by
    the storefront + Product JSON-LD); OCLC + Open Library work id live in
    'book' (reconciliation signals for the Book graph)."""
    from plugins.installed.metafields.models import Metafield  # noqa: PLC0415

    out = {'isbn13': '', 'oclc': '', 'openlibrary': ''}
    try:
        ident = Metafield.objects.for_obj(product, ns='identifiers') or {}
        out['isbn13'] = str(ident.get('identifiers.isbn13') or ident.get('isbn13') or '')
        book_ns = Metafield.objects.for_obj(product, ns='book') or {}
        out['oclc'] = str(book_ns.get('book.oclc') or book_ns.get('oclc') or '')
        out['openlibrary'] = str(
            book_ns.get('book.openlibrary') or book_ns.get('openlibrary') or ''
        )
    except Exception:  # noqa: BLE001, S110 — metafields optional; blank form is fine
        pass
    return out


def _save_book_identifiers(product, post) -> None:
    """Persist ISBN-13 / OCLC / Open Library work id from the book card.

    ISBN-13 → 'identifiers' (canonical, drives Product JSON-LD); OCLC + Open
    Library → 'book' (Book-graph reconciliation). Blank clears the value.
    """
    from plugins.installed.metafields.models import Metafield  # noqa: PLC0415

    for ns, key in (('identifiers', 'isbn13'), ('book', 'oclc'), ('book', 'openlibrary')):
        if key not in post:
            continue
        val = (post.get(key) or '').strip()
        if val:
            Metafield.objects.set(product, namespace=ns, key=key, value=val)
        else:
            Metafield.objects.delete_for(product, namespace=ns, key=key)


def _facets(book, slugify) -> list[dict]:
    """The category-style facet pages this book appears on (label, value, url)."""
    out: list[dict] = []
    for genre in book.genres.all():
        out.append({'label': 'Genre', 'value': genre.name, 'url': f'/genre/{genre.slug}/'})
    for topic in book.topics.all():
        out.append({'label': 'Topic', 'value': topic.name, 'url': f'/topic/{topic.slug}/'})
    if book.author:
        out.append(
            {'label': 'Author', 'value': book.author, 'url': f'/author/{slugify(book.author)}/'}
        )
    if book.publisher:
        out.append(
            {
                'label': 'Publisher',
                'value': book.publisher,
                'url': f'/publisher/{slugify(book.publisher)}/',
            }
        )
    if book.series:
        out.append(
            {'label': 'Series', 'value': book.series, 'url': f'/series/{slugify(book.series)}/'}
        )
    if book.imprint:
        out.append(
            {'label': 'Imprint', 'value': book.imprint, 'url': f'/imprint/{slugify(book.imprint)}/'}
        )
    if book.print_type:
        out.append(
            {
                'label': 'Format',
                'value': book.get_print_type_display(),
                'url': f'/format/{book.print_type}/',
            }
        )
    if book.language:
        out.append(
            {'label': 'Language', 'value': book.language, 'url': f'/language/{book.language}/'}
        )
    return out


def save_book_fields(product, post, files=None) -> None:
    """Upsert the BookProduct from the product form's book.* inputs.

    Only touches the DB when the book card was submitted (a `book_submitted`
    hidden marker) or a row already exists — so a plain product save never
    creates an empty BookProduct.
    """
    from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

    has_row = BookProduct.objects.filter(product=product).exists()
    if not has_row and not post.get('book_submitted'):
        return

    book, _ = BookProduct.objects.get_or_create(product=product)

    for field in _TEXT_FIELDS:
        if field in post:
            setattr(book, field, (post.get(field) or '').strip())

    for field in _INT_FIELDS:
        if field in post:
            raw = (post.get(field) or '').strip()
            setattr(book, field, int(raw) if raw.isdigit() else None)

    if 'publication_date' in post:
        raw = (post.get('publication_date') or '').strip()
        book.publication_date = _parse_date(raw)

    if files and files.get('cover_pdf'):
        book.cover_pdf = files['cover_pdf']

    book.save()

    if post.get('book_submitted'):
        _save_book_identifiers(product, post)

    # Curated taxonomies — only when the book card was submitted, so a plain
    # product save never clears them. An empty list = the merchant unchecked all.
    # `getlist` exists on a QueryDict (real request.POST); a plain dict (some
    # callers/tests) can't carry multi-value fields, so skip M2M for it.
    if post.get('book_submitted') and hasattr(post, 'getlist'):
        book.genres.set(post.getlist('genres'))
        book.topics.set(post.getlist('topics'))


def _parse_date(raw: str):
    if not raw:
        return None
    from datetime import datetime  # noqa: PLC0415

    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d.%m.%Y'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None
