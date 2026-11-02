"""Genres and authors in the storefront's search dropdown (`SEARCH_SUGGESTIONS`).

Rows whose every typed word starts a word of the name, and only those with an
active book on them, so a suggestion never opens an empty landing page.
"""

from __future__ import annotations

import re

from django.db.models import Count, Q
from django.utils.text import slugify
from django.utils.translation import gettext, ngettext

LIMIT = 4


def _starts_words(field: str, terms) -> Q:
    q = Q()
    for term in terms:
        q &= Q(**{f'{field}__iregex': r'(^|[^a-z0-9])' + re.escape(term)})
    return q


def _books(n: int) -> str:
    return ngettext('%(n)d book', '%(n)d books', n) % {'n': n}


def _first_word_first(name: str, terms) -> tuple:
    return (not name.lower().startswith(terms[0]), name.lower())


def answer(groups: list, terms: list[str]) -> list:
    from plugins.installed.book_product.models import BookProduct, Genre

    if not terms:
        return groups
    genres = (
        Genre.objects.filter(_starts_words('name', terms))
        .annotate(n=Count('books', filter=Q(books__product__status='active'), distinct=True))
        .filter(n__gt=0)
    )
    items = [
        {'name': g.name, 'url': f'/genre/{g.slug}/', 'meta': _books(g.n)}
        for g in sorted(genres[:12], key=lambda g: _first_word_first(g.name, terms))[:LIMIT]
    ]
    if items:
        groups = [*groups, {'key': 'genres', 'label': gettext('Genres'), 'items': items}]

    authors = (
        BookProduct.objects.filter(product__status='active')
        .filter(_starts_words('author', terms))
        .values('author')
        .annotate(n=Count('id'))
    )
    items = []
    for row in sorted(authors[:24], key=lambda r: _first_word_first(r['author'], terms)):
        slug = slugify(row['author'])
        if slug:
            items.append(
                {'name': row['author'], 'url': f'/author/{slug}/', 'meta': _books(row['n'])}
            )
        if len(items) == LIMIT:
            break
    if items:
        groups = [*groups, {'key': 'authors', 'label': gettext('Authors'), 'items': items}]
    return groups
