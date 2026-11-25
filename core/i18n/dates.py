"""Dates in the page's language, through Babel (CLDR).

Django's own Serbian catalog is Cyrillic and its formats are its own, so a date a
shopper reads is formatted here: Serbian in the Latin script, every other
language as Babel knows it. A store that wants a country's variant (Montenegro's
`sr_Latn_ME`) formats with its own locale.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.i18n')


def babel_locale(language: str = '') -> str:
    """The Babel locale for a language code: `sr` → `sr_Latn`, `en-gb` → `en_GB`."""
    from django.utils.translation import get_language

    code = (language or get_language() or 'en').replace('-', '_')
    base = code.split('_')[0].lower()
    if base == 'sr':
        return 'sr_Latn'
    try:
        from babel import Locale

        return str(Locale.parse(code))
    except Exception:  # noqa: BLE001 — an unknown code reads as English
        return 'en'


def format_day(day, format: str = 'long', language: str = '') -> str:  # noqa: A002 — Babel's word
    """'November 8, 2026' or '8. novembar 2026.'; '' without a date."""
    if day is None:
        return ''
    try:
        from babel.dates import format_date

        return format_date(day, format=format, locale=babel_locale(language))
    except Exception:  # noqa: BLE001 — a label never fails a page
        logger.debug('i18n: format_day failed', exc_info=True)
        return day.isoformat() if hasattr(day, 'isoformat') else str(day)
