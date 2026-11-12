"""What a shipping rate costs, as the merchant enters it.

One reader of a rate's form (the Shipping page) and of Linda's
``shipping.set_rate``: both hand the raw values to ``rate_values``, which checks
them against the rate's kind and prices them in the store's currency. Checkout
adds a rate's amount to a cart priced in that currency, so a rate in any other
would be charged as the wrong money.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from djmoney.money import Money

# Kinds a merchant enters amounts for; carrier kinds are quoted live.
PRICED_KINDS = ('flat', 'free_over', 'weight_tier', 'order_total_tier', 'pickup')
TIER_KINDS = ('weight_tier', 'order_total_tier')
MAX_TIERS = 10
# The money columns hold 14 digits, 2 after the point.
MAX_AMOUNT = Decimal('999999999999.99')


class RateError(ValueError):
    """A rate that cannot be saved; the message is fit for the merchant."""


def store_currency() -> str:
    from plugins.dropshipping.importer import store_currency as _store_currency  # noqa: PLC0415

    return _store_currency()


def _blank(raw) -> bool:
    """Nothing entered: None or an empty string (0 is a value)."""
    return raw is None or str(raw).strip() == ''


def _amount(raw, label: str, *, required: bool) -> Decimal | None:
    text = '' if raw is None else str(raw).strip()
    if not text:
        if required:
            raise RateError(f'{label} is required for this kind of rate.')
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise RateError(f'{label} must be a number.') from None
    if not value.is_finite():
        raise RateError(f'{label} must be a number.')
    if value < 0:
        raise RateError(f'{label} cannot be negative.')
    if value > MAX_AMOUNT:
        raise RateError(f'{label} is too large.')
    return value.quantize(Decimal('0.01'))


def _days(raw, label: str) -> int | None:
    text = '' if raw is None else str(raw).strip()
    if not text:
        return None
    try:
        value = int(text)
    except ValueError:
        raise RateError(f'{label} must be a whole number of days.') from None
    if value < 0 or value > 365:
        raise RateError(f'{label} must be between 0 and 365.')
    return value


def _tiers(rows, kind: str) -> list[dict]:
    """``rows`` as ``[(threshold, amount)]``; blank rows are dropped."""
    unit = 'Weight (kg)' if kind == 'weight_tier' else 'Order total'
    tiers = []
    for threshold, amount in rows or []:
        if _blank(threshold) and _blank(amount):
            continue
        t = _amount(threshold, f'{unit} of a tier', required=True)
        a = _amount(amount, 'The price of a tier', required=True)
        tiers.append({'threshold': str(t), 'amount': str(a)})
    if not tiers:
        raise RateError('Add at least one tier.')
    if len(tiers) > MAX_TIERS:
        raise RateError(f'A rate has at most {MAX_TIERS} tiers.')
    tiers.sort(key=lambda t: Decimal(t['threshold']))
    thresholds = [t['threshold'] for t in tiers]
    if len(set(thresholds)) != len(thresholds):
        raise RateError('Two tiers start at the same point.')
    if Decimal(thresholds[0]) != 0:
        raise RateError('Start the first tier at 0, or carts below it get no price.')
    return tiers


def priority(raw, default: int = 50) -> int:
    """A rate's display order (lower first)."""
    text = '' if raw is None else str(raw).strip()
    if not text:
        return default
    try:
        value = int(text)
    except ValueError:
        raise RateError('Priority must be a whole number.') from None
    if not 0 <= value <= 32767:
        raise RateError('Priority must be between 0 and 32767.')
    return value


def rate_values(  # noqa: PLR0913
    *,
    computation: str,
    flat_amount=None,
    free_threshold=None,
    tiers=None,
    estimated_days_min=None,
    estimated_days_max=None,
) -> dict:
    """The model fields for a rate of ``computation``, checked and priced.

    ``tiers`` is ``[(threshold, amount)]`` for the tiered kinds. Fields a kind
    does not use come back empty, so switching a rate's kind leaves nothing
    stale behind. Raises ``RateError``.
    """
    from plugins.installed.shipping.models import ShippingRate  # noqa: PLC0415

    kinds = {value for value, _label in ShippingRate.COMPUTATION_CHOICES}
    if computation not in kinds:
        raise RateError('Choose how this rate is priced.')
    currency = store_currency()
    values = {
        'computation': computation,
        'flat_amount': None,
        'free_threshold': None,
        'tiers': [],
        'estimated_days_min': _days(estimated_days_min, 'Fastest delivery'),
        'estimated_days_max': _days(estimated_days_max, 'Slowest delivery'),
    }
    lo, hi = values['estimated_days_min'], values['estimated_days_max']
    if lo is not None and hi is not None and lo > hi:
        raise RateError('The fastest delivery cannot be slower than the slowest.')
    if computation == 'flat':
        values['flat_amount'] = _amount(flat_amount, 'Price', required=True)
    elif computation == 'free_over':
        values['flat_amount'] = _amount(flat_amount, 'Price below the threshold', required=True)
        threshold = _amount(free_threshold, 'Free over', required=True)
        if not threshold:
            raise RateError('Free over must be more than 0; use a flat rate of 0 for free.')
        values['free_threshold'] = threshold
    elif computation in TIER_KINDS:
        values['tiers'] = _tiers(tiers, computation)
    elif computation == 'pickup':
        values['flat_amount'] = _amount(flat_amount, 'Price', required=False) or Decimal('0.00')
    for field in ('flat_amount', 'free_threshold'):
        if values[field] is not None:
            values[field] = Money(values[field], currency)
    return values


def describe(rate) -> str:
    """One line on what the rate charges, for the rates table."""

    def money(value) -> str:
        return f'{value.amount:.2f} {value.currency}'

    kind = rate.computation
    if kind.startswith('carrier_'):
        return 'Quoted by the carrier at checkout'
    if kind in TIER_KINDS:
        tiers = rate.tiers or []
        if not tiers:
            return 'No tiers'
        currency = rate.flat_amount.currency if rate.flat_amount else store_currency()
        cheapest = min(Decimal(str(t.get('amount', 0))) for t in tiers)
        unit = 'weight' if kind == 'weight_tier' else 'order total'
        return f'From {money(Money(cheapest, currency))} · {len(tiers)} tiers by {unit}'
    if kind == 'free_over':
        below = money(rate.flat_amount) if rate.flat_amount else 'no price'
        over = money(rate.free_threshold) if rate.free_threshold else '—'
        return f'{below} · free over {over}'
    if kind == 'pickup':
        return money(rate.flat_amount) if rate.flat_amount and rate.flat_amount.amount else 'Free'
    return money(rate.flat_amount) if rate.flat_amount else '—'
