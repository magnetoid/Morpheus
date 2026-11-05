"""One spelling for a country: the ISO 3166-1 alpha-2 code.

Shipping zones and tax regions compare codes literally. A shopper who typed
``UK`` (not a code — the UK is ``GB``) matched no zone and the checkout fell
back to free "Standard delivery"; a store whose own ``StoreSettings.country``
read ``UK`` prefilled the same mistake. Normalise at every entry point and
compare codes everywhere else.
"""

from __future__ import annotations

import functools

#: Common non-code spellings → the code. Keep this short: it is for what people
#: actually type into a country box, not a gazetteer.
_ALIASES = {
    'UK': 'GB',
    'U.K.': 'GB',
    'UNITED KINGDOM': 'GB',
    'GREAT BRITAIN': 'GB',
    'BRITAIN': 'GB',
    'ENGLAND': 'GB',
    'SCOTLAND': 'GB',
    'WALES': 'GB',
    'NORTHERN IRELAND': 'GB',
    'USA': 'US',
    'U.S.': 'US',
    'U.S.A.': 'US',
    'UNITED STATES': 'US',
    'UNITED STATES OF AMERICA': 'US',
    'DEUTSCHLAND': 'DE',
    'GERMANY': 'DE',
    'FRANCE': 'FR',
    'ITALY': 'IT',
    'ITALIA': 'IT',
    'SPAIN': 'ES',
    'ESPAÑA': 'ES',
    'NETHERLANDS': 'NL',
    'THE NETHERLANDS': 'NL',
    'IRELAND': 'IE',
    'SERBIA': 'RS',
    'SRBIJA': 'RS',
    'MONTENEGRO': 'ME',
    'CRNA GORA': 'ME',
}


def normalise_country(raw) -> str:
    """``'uk'`` → ``'GB'``, ``'United Kingdom'`` → ``'GB'``, ``'de'`` → ``'DE'``;
    anything that is not a two-letter code after that → ``''``."""
    value = ' '.join(str(raw or '').strip().upper().split())
    value = _ALIASES.get(value, value)
    return value if len(value) == 2 and value.isalpha() else ''


def store_country() -> str:
    """The store's own country as a code, or ``''`` when unset or unreadable."""
    try:
        from core.models import StoreSettings

        return normalise_country(StoreSettings.get('country') or '')
    except Exception:  # noqa: BLE001 — a settings hiccup must not break a checkout page
        return ''


#: Babel territories that are not places an order ships to: groupings, test codes
#: and parts of a country that carries its own code (Ascension → SH, Canaries → ES).
_NOT_COUNTRIES = frozenset(
    {'AC', 'CP', 'CQ', 'DG', 'EA', 'EU', 'EZ', 'IC', 'QO', 'TA', 'UN', 'XA', 'XB', 'ZZ'}
)


def _sort_key(name: str) -> str:
    import unicodedata

    plain = unicodedata.normalize('NFKD', name)
    return ''.join(c for c in plain if not unicodedata.combining(c)).casefold()


@functools.lru_cache(maxsize=16)
def _choices(locale_name: str) -> tuple[tuple[str, str], ...]:
    from babel import Locale, UnknownLocaleError

    try:
        territories = Locale.parse(locale_name).territories
    except (UnknownLocaleError, ValueError):
        territories = Locale.parse('en').territories
    pairs = [
        (code, name)
        for code, name in territories.items()
        if len(code) == 2 and code.isalpha() and code.isupper() and code not in _NOT_COUNTRIES
    ]
    return tuple(sorted(pairs, key=lambda pair: _sort_key(pair[1])))


def country_choices(language: str | None = None) -> tuple[tuple[str, str], ...]:
    """Every country as ``(code, name)``, named and sorted in ``language`` (the active
    language by default) — the options of a checkout's country list."""
    from django.utils.translation import get_language

    lang = (language or get_language() or 'en').replace('-', '_')
    # Django's Serbian is Cyrillic; the stores write Serbian in Latin script.
    if lang.split('_')[0].lower() == 'sr':
        lang = 'sr_Latn'
    return _choices(lang)
