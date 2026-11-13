"""Exchange rates: the ECB's daily table, and rates the merchant types.

Rows live in core's ``ExchangeRate`` as ``store currency -> X``. A row with
``source='manual'`` is the merchant's word and the daily fetch never touches it.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET  # noqa: S405 — a fixed, trusted URL
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.utils import timezone

logger = logging.getLogger('morpheus.markets')

ECB_URL = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml'
STALE_AFTER = timedelta(days=3)
_EIGHT = Decimal('0.00000001')


def fetch_ecb() -> dict:
    """Read the ECB's daily table and store a rate per currency against the store's.

    Raises on an HTTP or parse failure. Returns
    ``{'written': n, 'kept_manual': [codes], 'date': 'YYYY-MM-DD'}``.
    """
    from core.models import ExchangeRate
    from core.net import outbound_request
    from core.pricing import store_currency

    response = outbound_request('GET', ECB_URL, timeout=20)
    response.raise_for_status()
    root = ET.fromstring(response.content)  # noqa: S314
    per_eur: dict[str, Decimal] = {'EUR': Decimal(1)}
    date = ''
    for node in root.iter():
        if not node.tag.endswith('Cube'):
            continue
        if node.get('time'):
            date = node.get('time')
        code, rate = node.get('currency'), node.get('rate')
        if code and rate:
            try:
                per_eur[code.upper()] = Decimal(rate)
            except InvalidOperation:
                continue
    if len(per_eur) < 2:
        raise ValueError('The ECB table had no rates.')

    store = store_currency()
    if store not in per_eur:
        raise ValueError(f'The ECB does not list {store}, the store currency.')
    eur_to_store = per_eur[store]

    manual = set(
        ExchangeRate.objects.filter(base_currency=store, source='manual').values_list(
            'quote_currency', flat=True
        )
    )
    written, kept = 0, []
    for code, per in sorted(per_eur.items()):
        if code == store:
            continue
        if code in manual:
            kept.append(code)
            continue
        ExchangeRate.objects.update_or_create(
            base_currency=store,
            quote_currency=code,
            defaults={'rate': (per / eur_to_store).quantize(_EIGHT), 'source': 'ecb'},
        )
        written += 1
    return {'written': written, 'kept_manual': kept, 'date': date}


def set_manual_rate(currency: str, rate: Decimal | None) -> None:
    """Fix the rate for ``store currency -> currency``; ``None`` removes the manual row."""
    from core.models import ExchangeRate
    from core.pricing import store_currency

    currency, store = (currency or '').upper(), store_currency()
    if len(currency) != 3 or currency == store:
        raise ValidationError(f'Enter a currency other than {store}.')
    if rate is None:
        ExchangeRate.objects.filter(
            base_currency=store, quote_currency=currency, source='manual'
        ).delete()
        return
    try:
        rate = Decimal(str(rate))
    except InvalidOperation:
        raise ValidationError('The rate must be a number.') from None
    if not rate.is_finite() or rate <= 0:
        raise ValidationError('The rate must be more than zero.')
    ExchangeRate.objects.update_or_create(
        base_currency=store,
        quote_currency=currency,
        defaults={'rate': rate.quantize(_EIGHT), 'source': 'manual'},
    )


def foreign_currencies() -> list[str]:
    """Currencies of the active markets that are not the store's."""
    from core.pricing import store_currency
    from plugins.installed.markets.models import Market

    store = store_currency()
    return sorted(
        {
            c.upper()
            for c in Market.objects.filter(is_active=True).values_list('currency', flat=True)
        }
        - {store}
    )


def rate_row(code: str) -> dict:
    """The rate for ``store currency -> code``: rate, source, age, stale.

    A rate is stale when the ECB's is older than three days, or when there is
    none. A manual rate never goes stale: it is the merchant's word.
    """
    from core.models import ExchangeRate
    from core.pricing import exchange_rate, store_currency

    store = store_currency()
    rate = exchange_rate(store, code)
    row = (
        ExchangeRate.objects.filter(base_currency=store, quote_currency=code).first()
        or ExchangeRate.objects.filter(base_currency=code, quote_currency=store).first()
    )
    if rate is None:
        stale, source, fetched = True, '', None
    elif row is None:
        stale, source, fetched = False, 'cross', None
    else:
        source, fetched = row.source, row.fetched_at
        stale = source != 'manual' and timezone.now() - fetched > STALE_AFTER
    return {'currency': code, 'rate': rate, 'source': source, 'fetched_at': fetched, 'stale': stale}


def rate_rows() -> list[dict]:
    """One row per currency an active market needs (see ``rate_row``)."""
    return [rate_row(code) for code in foreign_currencies()]
