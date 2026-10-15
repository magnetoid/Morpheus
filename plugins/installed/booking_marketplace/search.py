"""Search for the travel store: what a visitor types, best match first.

docs/superpowers/specs/2026-10-14-montenegro-search-design.md. Text is folded before it
is compared (case, accents, Serbian Cyrillic, `đ`), so `zabljak`, `ŽABLJAK` and `Жабљак`
are one word. A query word matches a listing's word when it is the same word, the start
of it, its singular or a Serbian synonym, or, when nothing matched as typed, one typo
away. Every word must match; when no listing has them all, listings with any of them come
back as close matches. Where a word matched decides the score: the name counts most, the
description least.

Pure Python over `Doc`s; the store's own index (its listings and places, cached per
process) is built at the end of this module.
"""

from __future__ import annotations

import bisect
import logging
import re
import time
import unicodedata
import uuid
from typing import NamedTuple

logger = logging.getLogger('morpheus.booking_marketplace')

EXACT, PREFIX, TYPO = 1.0, 0.8, 0.5
MAX_QUERY_CHARS = 200
MAX_TERMS = 8

STOPWORDS = frozenset(
    {
        # English
        'the',
        'a',
        'an',
        'in',
        'on',
        'at',
        'of',
        'and',
        'for',
        'with',
        'to',
        'from',
        'near',
        'tour',
        'tours',
        'trip',
        'trips',
        # Serbian
        'u',
        'na',
        'i',
        'za',
        'sa',
        'od',
        'do',
        'oko',
        'tura',
        'ture',
        'izlet',
        'izleti',
        # The whole store is Montenegro, and everything on it is an experience
        'montenegro',
        'crna',
        'gora',
        'crnoj',
        'gori',
        'experience',
        'experiences',
        'activity',
        'activities',
        'dozivljaj',
        'dozivljaji',
    }
)

# English–Serbian spellings of one meaning, written folded: any of them finds the others.
SYNONYM_GROUPS = (
    ('kayak', 'kajak'),
    ('boat', 'brod', 'camac'),
    ('wine', 'vino'),
    ('winery', 'vinarija'),
    ('beach', 'plaza'),
    ('canyon', 'kanjon'),
    ('hike', 'hiking', 'planinarenje', 'pjesacenje'),
    ('dive', 'diving', 'ronjenje'),
    ('horse', 'konj', 'jahanje'),
    ('yacht', 'jahta'),
    ('island', 'ostrvo'),
    ('lake', 'jezero'),
    ('monastery', 'manastir'),
    ('fortress', 'tvrdjava', 'tvrdava'),
    ('cooking', 'kuvanje', 'kuhanje'),
    ('sunset', 'zalazak'),
    ('fishing', 'ribolov', 'pecanje'),
    ('olive', 'maslina', 'maslinovo'),
    ('honey', 'med'),
    ('cheese', 'sir'),
    ('paragliding', 'paraglajding'),
    ('cave', 'pecina'),
    ('river', 'rijeka'),
    ('mountain', 'planina'),
    ('tasting', 'degustacija'),
    ('walk', 'walking', 'setnja'),
    ('bike', 'cycling', 'bicikl', 'biciklizam'),
    ('jeep', 'dzip'),
    ('adventure', 'avantura'),
    ('culture', 'kultura'),
    ('food', 'hrana'),
)
_SYNONYMS = {word: group for group in SYNONYM_GROUPS for word in group}

# Lowercase Serbian Cyrillic to Latin, accents kept (they are dropped with all the others).
_CYRILLIC = str.maketrans(
    {
        'а': 'a',
        'б': 'b',
        'в': 'v',
        'г': 'g',
        'д': 'd',
        'ђ': 'đ',
        'е': 'e',
        'ж': 'ž',
        'з': 'z',
        'и': 'i',
        'ј': 'j',
        'к': 'k',
        'л': 'l',
        'љ': 'lj',
        'м': 'm',
        'н': 'n',
        'њ': 'nj',
        'о': 'o',
        'п': 'p',
        'р': 'r',
        'с': 's',
        'т': 't',
        'ћ': 'ć',
        'у': 'u',
        'ф': 'f',
        'х': 'h',
        'ц': 'c',
        'ч': 'č',
        'џ': 'dž',
        'ш': 'š',
    }
)
_WORD = re.compile(r'[^\W_]+')


class Doc(NamedTuple):
    """Something to find: its key (a pk), its kind and its (weight, text) fields."""

    key: object
    kind: str
    fields: tuple


class Term(NamedTuple):
    """A query word and the spellings that count as it (its singular, its synonyms)."""

    text: str
    variants: tuple


class Matches(NamedTuple):
    """Score per key. `close`: no key matched every word, and these match some."""

    scores: dict
    close: bool


def _latin(text: str) -> str:
    return (text or '').casefold().translate(_CYRILLIC)


def _words(text: str) -> list[str]:
    text = unicodedata.normalize('NFKD', text)
    return _WORD.findall(''.join(ch for ch in text if not unicodedata.combining(ch)))


def fold(text: str) -> str:
    """Lowercase Latin without accents, one space between words; `đ` becomes `d`."""
    return ' '.join(_words(_latin(text).replace('đ', 'd')))


def index_tokens(text: str) -> set[str]:
    """A document's words. A word with `đ` is kept both ways (`durdevica`, `djurdjevica`):
    a visitor without a Serbian keyboard types either."""
    raw = _latin(text)
    words = set(_words(raw.replace('đ', 'd')))
    if 'đ' in raw:
        words.update(_words(raw.replace('đ', 'dj')))
    return words


def one_edit(a: str, b: str) -> bool:
    """Whether `b` is `a` with one letter added, dropped or changed, or two neighbours swapped."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diff = [i for i, (x, y) in enumerate(zip(a, b, strict=True)) if x != y]
        if len(diff) == 1:
            return True
        i, j = diff[0], diff[-1]
        return len(diff) == 2 and j == i + 1 and a[i] == b[j] and a[j] == b[i]
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    i = 0
    while i < len(short) and short[i] == long_[i]:
        i += 1
    return short[i:] == long_[i + 1 :]


def _forms(word: str) -> set[str]:
    """The word and its singular: `boats` also looks for `boat`, `beaches` for `beach`."""
    forms = {word}
    if len(word) >= 4 and word.endswith('s') and not word.endswith('ss'):
        forms.add(word[:-1])
        if len(word) >= 5 and word.endswith('es'):
            forms.add(word[:-2])
    return forms


def parse_query(q: str) -> list[Term]:
    """The query's words, folded, without stopwords or repeats, each with its variants."""
    terms: list[Term] = []
    seen: set[str] = set()
    for word in fold((q or '')[:MAX_QUERY_CHARS]).split():
        if word in STOPWORDS or word in seen:
            continue
        seen.add(word)
        variants: set[str] = set()
        for form in _forms(word):
            variants.add(form)
            variants.update(_SYNONYMS.get(form, ()))
        variants.discard(word)
        terms.append(Term(word, tuple(sorted(variants))))
        if len(terms) == MAX_TERMS:
            break
    return terms


class Index:
    """Folded words → {key: the best field weight the word appears in}, over `Doc`s."""

    def __init__(self, docs) -> None:
        postings: dict[str, dict] = {}
        self._kinds: dict = {}
        for doc in docs:
            self._kinds[doc.key] = doc.kind
            for weight, text in doc.fields:
                for token in index_tokens(text):
                    row = postings.setdefault(token, {})
                    if weight > row.get(doc.key, 0):
                        row[doc.key] = weight
        self._postings = postings
        self._vocab = sorted(postings)
        self._by_len: dict[int, list[str]] = {}
        for token in self._vocab:
            self._by_len.setdefault(len(token), []).append(token)

    def _lookup(self, word: str, *, prefix: bool) -> list[tuple[str, float]]:
        hits = [(word, EXACT)] if word in self._postings else []
        if prefix:
            i = bisect.bisect_right(self._vocab, word)
            while i < len(self._vocab) and self._vocab[i].startswith(word):
                hits.append((self._vocab[i], PREFIX))
                i += 1
        return hits

    def _hits(self, term: Term) -> list[tuple[str, float]]:
        """The words `term` matches, and how well. A typo is tried only when nothing
        matched as typed: `hiking` must not bring the biking tours, nor `beach` "reach"."""
        hits = self._lookup(term.text, prefix=len(term.text) >= 2)
        for variant in term.variants:
            hits += self._lookup(variant, prefix=len(variant) >= 4)
        if hits or len(term.text) < 5:
            return hits
        size = len(term.text)
        return [
            (token, TYPO)
            for length in (size - 1, size, size + 1)
            for token in self._by_len.get(length, ())
            if one_edit(term.text, token)
        ]

    def _scores(self, term: Term, kind: str, within) -> dict:
        best: dict = {}
        for token, quality in self._hits(term):
            for key, weight in self._postings[token].items():
                if self._kinds[key] != kind or (within is not None and key not in within):
                    continue
                score = weight * quality
                if score > best.get(key, 0.0):
                    best[key] = score
        return best

    def find(self, terms, *, kind: str, within=None, fallback: bool = True) -> Matches | None:
        """Keys of `kind` (only those in `within`, when given) matching every term, scored.

        None when there is nothing to look for. When no key matches every term and
        `fallback` is on, the keys matching any term come back as close matches.
        """
        if not terms:
            return None
        per_term = [self._scores(term, kind, within) for term in terms]
        every = set(per_term[0]).intersection(*per_term[1:])
        if every:
            return Matches({key: sum(s[key] for s in per_term) for key in every}, close=False)
        if not fallback:
            return Matches({}, close=False)
        some = set().union(*per_term)
        return Matches(
            {key: sum(s.get(key, 0.0) for s in per_term) for key in some}, close=bool(some)
        )


# -- the store's index ---------------------------------------------------------
# Built once per process. `bump` (connected in app.py to every listing, place and category
# save or delete) writes a new version token to the shared cache, and a process holding an
# index built under another token rebuilds before its next search. An edit that skips
# save() — `QuerySet.update()` in the seed commands — is picked up once the index is
# MAX_AGE_S old. Callers filter by the database first and pass the survivors as `within`:
# the index ranks, it never decides what is live.
MAX_AGE_S = 600
_VERSION_KEY = 'booking_marketplace:search:version'
_STATE: dict = {}


def _flatten(value) -> str:
    """Highlights as text: strings, or the strings inside lists and dicts."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return ' '.join(_flatten(item) for item in value.values())
    if isinstance(value, list | tuple):
        return ' '.join(_flatten(item) for item in value)
    return ''


def _region_names() -> dict[str, str]:
    """Each region's label in English and in Serbian, so `boka` finds Kotor Bay."""
    from django.utils import translation

    from plugins.installed.booking_marketplace.models import REGIONS

    names = {}
    for key, label in REGIONS:
        spellings = []
        for language in ('en', 'sr'):
            with translation.override(language):
                spellings.append(str(label))
        names[key] = ' '.join(dict.fromkeys(spellings))
    return names


def documents() -> list[Doc]:
    """The active listings (both kinds) and places, as the index reads them."""
    from plugins.installed.booking_marketplace.models import BookableService, Place
    from plugins.installed.booking_marketplace.products import plain_text

    regions = _region_names()
    docs = [
        Doc(
            listing.pk,
            listing.listing_kind,
            (
                (10, listing.name),
                (6, listing.location),
                (6, regions.get(listing.region, '')),
                (5, listing.category.name if listing.category_id else ''),
                (3, _flatten(listing.highlights)),
                (2, plain_text(listing.short_description)),
                (1, plain_text(listing.description)),
            ),
        )
        for listing in BookableService.objects.filter(is_active=True).select_related('category')
    ]
    docs += [
        Doc(place.pk, 'place', ((10, place.name), (6, regions.get(place.region, ''))))
        for place in Place.objects.filter(is_active=True)
    ]
    return docs


def _version() -> str:
    from django.core.cache import cache

    try:
        current = cache.get(_VERSION_KEY)
        if current is None:
            cache.add(_VERSION_KEY, uuid.uuid4().hex, None)
            current = cache.get(_VERSION_KEY)
    except Exception:  # noqa: BLE001 — without the cache the index still ages out
        return ''
    return current or ''


def bump(**_kwargs) -> None:
    """post_save / post_delete: every process rebuilds its index before its next search."""
    from django.core.cache import cache

    try:
        cache.set(_VERSION_KEY, uuid.uuid4().hex, None)
    except Exception:  # noqa: BLE001 — a cache outage must never fail a listing save
        logger.warning('booking search: could not bump the index version', exc_info=True)


def listing_index() -> Index:
    """This process's index of the store, rebuilt first when it is stale."""
    version = _version()
    built = _STATE.get('built')
    if built is None or built[0] != version or time.monotonic() - built[1] > MAX_AGE_S:
        built = (version, time.monotonic(), Index(documents()))
        _STATE['built'] = built
    return built[2]
