"""Landing-page URLs for the enum-ish book fields (print type, language).

``/format/<value>/`` and ``/language/<value>/`` are matched by Django's ``slug``
converter and then filter books by the raw stored value, so a value can only be
served when it IS a slug. ``print_type`` has choices but, as a CharField, accepts
free text — one live book stored ``PDF report`` — and linking or sitemapping such
a value produced a URL that 404s. Every builder of these URLs goes through here.
"""

from __future__ import annotations

import re

_SLUG = re.compile(r'^[-a-zA-Z0-9_]+$')


def value_facet_url(prefix: str, value: str | None) -> str:
    """``/<prefix>/<value>/`` when the facet route can serve ``value``, else ``''``.

    A language is named by its code, whatever spelling the book carries — the
    page for `English` IS `/language/en/`.
    """
    value = (value or '').strip()
    if prefix == 'language':
        value = canonical_language(value)
    if not value or not _SLUG.match(value):
        return ''
    return f'/{prefix}/{value}/'


# Language names a catalogue import writes out in full, mapped to the ISO 639-1
# code the facet route serves. dotbooks stored 860 books as `en` and one as
# `English`, so `/language/English/` was a second landing page for one shelf.
_LANGUAGE_CODES = {
    'arabic': 'ar',
    'bosnian': 'bs',
    'chinese': 'zh',
    'croatian': 'hr',
    'czech': 'cs',
    'danish': 'da',
    'dutch': 'nl',
    'english': 'en',
    'finnish': 'fi',
    'french': 'fr',
    'german': 'de',
    'greek': 'el',
    'hebrew': 'he',
    'hindi': 'hi',
    'hungarian': 'hu',
    'italian': 'it',
    'japanese': 'ja',
    'korean': 'ko',
    'latin': 'la',
    'norwegian': 'no',
    'polish': 'pl',
    'portuguese': 'pt',
    'russian': 'ru',
    'serbian': 'sr',
    'spanish': 'es',
    'swedish': 'sv',
    'turkish': 'tr',
}


def canonical_language(value: str | None) -> str:
    """The code a stored language value means: `English` → `en`, `en-US` → `en`.

    Anything unrecognised comes back unchanged, so a value the map does not know
    keeps the page it always had rather than losing it.
    """
    raw = (value or '').strip()
    lowered = raw.lower().replace('_', '-')
    if lowered in _LANGUAGE_CODES:
        return _LANGUAGE_CODES[lowered]
    head, _, region = lowered.partition('-')
    if head.isalpha() and 2 <= len(head) <= 3 and (not region or region.isalnum()):
        return head
    return raw


def language_spellings(code: str) -> set[str]:
    """Every stored spelling that means `code` — the code and its English name."""
    return {code} | {name for name, c in _LANGUAGE_CODES.items() if c == code}
