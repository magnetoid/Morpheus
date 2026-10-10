"""One spelling for a country: the ISO 3166-1 alpha-2 code.

Shipping zones and tax regions compare codes literally. A shopper who typed
``UK`` (not a code — the UK is ``GB``) matched no zone and the checkout fell
back to free "Standard delivery"; a store whose own ``StoreSettings.country``
read ``UK`` prefilled the same mistake. Normalise at every entry point and
compare codes everywhere else.
"""

from __future__ import annotations

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
