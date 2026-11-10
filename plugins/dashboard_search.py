"""What the dashboard's search box asks every app, and the matching they share.

The search box (``admin_dashboard/views_split/palette.py``) fires
``DASHBOARD_SEARCH``; each app answers with the records it owns: a few rows its
database matches (``matching()``), each made into a hit with ``hit()``. The shell
lists the dashboard's pages, the apps, their settings fields and the emails
itself, and ranks every hit by ``score()``.

Text the store keeps in Python (page names, settings, guides) folds case and
accents and forgives one typo in a word of five letters or more. A database row
matches each word as typed, case aside, in any of the fields its app names: the
databases the stores run cannot fold accents without an extension.
"""

from __future__ import annotations

import re
import unicodedata

from django.db.models import Q

#: Rows one app lists per kind of record.
LIMIT = 5
#: A record the database matched ranks at least this well, whatever its label says.
RECORD_FLOOR = 30
_TOKEN = re.compile(r'\w+')


def fold(text) -> str:
    """Lower case without accents: ``Čokolada`` and ``cokolada`` are one word."""
    decomposed = unicodedata.normalize('NFKD', str(text or ''))
    plain = ''.join(c for c in decomposed if not unicodedata.combining(c))
    return plain.casefold().replace('đ', 'd')


def words(query: str) -> list[str]:
    return fold(query).split()


def _one_edit(a: str, b: str) -> bool:
    """``a`` and ``b`` differ by one letter added, dropped or changed, or by two
    neighbouring letters swapped."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diff = [i for i, (x, y) in enumerate(zip(a, b, strict=True)) if x != y]
        if len(diff) == 1:
            return True
        return (
            len(diff) == 2  # a swap is two letters
            and diff[1] == diff[0] + 1
            and (a[diff[0]], a[diff[1]]) == (b[diff[1]], b[diff[0]])
        )
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    i = 0
    while i < len(short) and short[i] == long_[i]:
        i += 1
    return short[i:] == long_[i + 1 :]


def _near(word: str, tokens: list[str]) -> bool:
    """``word`` is a typo of the start of one of ``tokens`` ("audiobok" of
    "audiobooks")."""
    n = len(word)
    if n < 5:
        return False
    for token in tokens:
        if len(token) < n - 1:
            continue
        if any(_one_edit(word, token[:k]) for k in (n - 1, n, n + 1)):
            return True
    return False


def score(query_words: list[str], label, *more) -> int:  # noqa: PLR0911 — one return per rank
    """How well ``label``, then the text in ``more``, answers the words: 100 for the
    label itself, down to 15 for a typo; 0 when a word is nowhere."""
    if not query_words:
        return 0
    head = fold(label)
    phrase = ' '.join(query_words)
    if head == phrase:
        return 100
    if head.startswith(phrase):
        return 85
    head_tokens = _TOKEN.findall(head)
    if all(any(t.startswith(w) for t in head_tokens) for w in query_words):
        return 70
    if all(w in head for w in query_words):
        return 55
    body = ' '.join([head, *(fold(m) for m in more if m)])
    if all(w in body for w in query_words):
        return 35
    tokens = _TOKEN.findall(body)
    if all(w in body or _near(w, tokens) for w in query_words):
        return 15
    return 0


def matching(query: str, fields) -> Q:
    """Rows where every word of ``query``, as typed, is in one of ``fields``; a
    leading ``#`` is dropped, so "#1042" finds order 1042."""
    condition = Q()
    for word in (w.lstrip('#') for w in query.split()):
        if not word:
            continue
        either = Q()
        for field in fields:
            either |= Q(**{f'{field}__icontains': word})
        condition &= either
    return condition


def add(
    value: list,
    rows,
    query: str,
    query_words: list[str] | None,
    *,
    fields,
    section: str,
    kind: str,
    label,
    url,
    hint=None,
    icon: str = 'circle',
    capability: str = '',
    limit: int = LIMIT,
) -> list:
    """Append to ``value`` the first ``limit`` of ``rows`` (a model or a queryset)
    where every word of ``query`` is in one of ``fields``. ``label``, ``url`` and
    ``hint`` take a row."""
    condition = matching(query, fields)
    if not condition:  # nothing but "#": no word to look for
        return value
    queryset = rows._default_manager.all() if isinstance(rows, type) else rows
    for row in queryset.filter(condition)[:limit]:
        value.append(
            hit(
                section=section,
                kind=kind,
                label=label(row),
                url=url(row),
                hint=hint(row) if hint else '',
                icon=icon,
                capability=capability,
                query_words=query_words,
            )
        )
    return value


def hit(
    *,
    section: str,
    kind: str,
    label,
    url: str,
    icon: str = 'circle',
    hint='',
    capability: str = '',
    query_words: list[str] | None = None,
    floor: int = RECORD_FLOOR,
) -> dict:
    """One search result. ``capability`` is what the page it opens needs, so a
    staff member who may not open it never sees it."""
    label, hint = str(label or '—'), str(hint or '')
    return {
        'section': section,
        'kind': kind,
        'label': label,
        'hint': hint,
        'url': url,
        'icon': icon,
        'capability': capability,
        'score': max(score(query_words or [], label, hint), floor),
    }
