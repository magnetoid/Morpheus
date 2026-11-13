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
from django.db import IntegrityError, transaction
from django.utils import timezone

logger = logging.getLogger('morpheus.markets')

ECB_URL = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml'
STALE_AFTER = timedelta(days=3)
_EIGHT = Decimal('0.00000001')
# ExchangeRate.rate is Decimal(18, 8).
MAX_RATE = Decimal(1_000_000_000)


def fetch_ecb() -> dict:  # noqa: PLR0912
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

    written, kept = 0, []
    now = timezone.now()
    for code, per in sorted(per_eur.items()):
        if code == store:
            continue
        rate = (per / eur_to_store).quantize(_EIGHT)
        # A manual row is never overwritten, even one saved while this ran.
        pair = ExchangeRate.objects.filter(base_currency=store, quote_currency=code)
        if pair.exclude(source='manual').update(rate=rate, source='ecb', fetched_at=now):
            written += 1
        elif pair.exists():
            kept.append(code)
        else:
            try:
                with transaction.atomic():
                    ExchangeRate.objects.create(
                        base_currency=store, quote_currency=code, rate=rate, source='ecb'
                    )
                written += 1
            except IntegrityError:  # someone saved this pair meanwhile
                if pair.filter(source='manual').exists():
                    kept.append(code)
    return {'written': written, 'kept_manual': kept, 'date': date}


def parse_decimal(raw) -> Decimal:
    """A number a merchant typed; a comma is a decimal separator ("0,92")."""
    return Decimal(str(raw).strip().replace(',', '.'))


def removed_rate_text(currency: str, outcome: str) -> str:
    """What the page and Linda say after removing a manual rate (see ``set_manual_rate``)."""
    from plugins.installed.markets.tasks import rate_source

    if outcome == 'none':
        return f'There was no rate of yours for {currency} to remove.'
    if outcome == 'cleared':
        return (
            f'Removed your rate for {currency}. No active market uses it, '
            'so there is no rate for it now.'
        )
    if rate_source() == 'manual':
        return f'Removed your rate for {currency}; another rate on file for it applies.'
    return f'Removed your rate for {currency}; the daily rate applies again.'


def set_manual_rate(currency: str, rate: Decimal | None) -> str:  # noqa: PLR0912
    """Fix the rate for ``store currency -> currency``; ``None`` removes the manual row.

    Returns what happened: ``'set'``; ``'none'`` (removal asked, but you had no
    rate of your own for it); ``'daily'`` (removed, and a rate still resolves,
    normally the ECB's); ``'cleared'`` (removed, and no active market needs one).
    There is one row per pair, so removing yours leaves nothing until the ECB's
    is fetched; if an active market needs the currency and no rate can be had,
    your rate is put back and the removal refused.
    """
    from babel.numbers import list_currencies

    from core.models import ExchangeRate
    from core.pricing import exchange_rate, store_currency
    from plugins.installed.markets.tasks import rate_source

    currency, store = (currency or '').upper(), store_currency()
    if len(currency) != 3 or currency == store:
        raise ValidationError(f'Enter a currency other than {store}.')
    if currency not in list_currencies():
        raise ValidationError(f'"{currency}" is not a currency code (use three letters, like EUR).')
    if rate is not None:
        try:
            rate = Decimal(str(rate))
        except InvalidOperation:
            raise ValidationError('The rate must be a number.') from None
        if not rate.is_finite():
            raise ValidationError('The rate must be a number.')
        # The bound comes first: quantizing a huge number raises InvalidOperation.
        if rate > MAX_RATE:
            raise ValidationError('The rate must be 1,000,000,000 or less.')
        if rate.quantize(_EIGHT) <= 0:
            raise ValidationError('The rate must be more than zero.')
        ExchangeRate.objects.update_or_create(
            base_currency=store,
            quote_currency=currency,
            defaults={'rate': rate.quantize(_EIGHT), 'source': 'manual'},
        )
        return 'set'

    manual = ExchangeRate.objects.filter(
        base_currency=store, quote_currency=currency, source='manual'
    ).first()
    if manual is None:
        return 'none'
    remembered = manual.rate
    manual.delete()
    if exchange_rate(store, currency) is not None:
        return 'daily'
    if currency not in foreign_currencies():
        return 'cleared'
    # An active market needs a rate and none resolves: try the ECB, outside any
    # transaction (the request can take 20 s and must not hold a row).
    if rate_source() == 'manual':
        why = 'rates are set by hand in this store'
    else:
        why = ''
        try:
            fetch_ecb()
        except Exception:  # noqa: BLE001 — told to the merchant below
            logger.warning('rate fetch after clearing %s failed', currency, exc_info=True)
            why = 'the daily rates could not be fetched just now'
    if exchange_rate(store, currency) is not None:
        return 'daily'
    ExchangeRate.objects.update_or_create(
        base_currency=store,
        quote_currency=currency,
        defaults={'rate': remembered, 'source': 'manual'},
    )
    why = why or f'the European Central Bank does not publish {currency}'
    raise ValidationError(
        f'Your rate stays: switch the {currency} market off first, or type another rate. '
        f'There is no daily rate for {currency} to fall back on ({why}).'
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
    if rate is None or row is None:
        stale, source, fetched = rate is None, '', None
    else:
        source, fetched = row.source, row.fetched_at
        stale = source != 'manual' and timezone.now() - fetched > STALE_AFTER
    return {'currency': code, 'rate': rate, 'source': source, 'fetched_at': fetched, 'stale': stale}


def rate_rows() -> list[dict]:
    """One row per currency an active market needs (see ``rate_row``)."""
    return [rate_row(code) for code in foreign_currencies()]
