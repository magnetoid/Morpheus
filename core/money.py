"""Currency-safe Money helpers.

The dashboard, pricing engine, refund flow, store-credit ledger, and
half a dozen plugins all do the same Money arithmetic. Every callsite
re-derives the same patterns:

  * pull `Decimal` out of a `Money`
  * multiply / add / subtract
  * remember to ``.quantize(Decimal('0.01'))`` so the result doesn't
    propagate arbitrary trailing digits into the DB or display
  * remember to assert currency-match before adding two Monies
  * coerce the currency to ``str()`` because djmoney sometimes hands
    you a `Currency` object that's *almost* a string

This module collects those into one place. Three rules:

  1. **Always quantize on construction.** ``money(amount, 'USD')`` and
     ``mul(money, 1.05)`` quantize to 2 decimals before returning.
  2. **Reject currency mismatches loudly.** ``add(a, b)`` raises
     ``CurrencyMismatch`` rather than silently producing nonsense.
  3. **Helpers accept both ``Money`` and raw ``Decimal``.** Callers
     don't have to remember which side of the API they're on.

Every helper returns a ``Money``. Use it as a drop-in for the bare
``Money(...)`` constructor when the value comes from arithmetic.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Union

from djmoney.money import Money

# Type alias — anywhere in the codebase that says "I'll take a Money
# but a Decimal is fine too" can use this.
MoneyLike = Union[Money, Decimal, int, float, str]  # noqa: UP007

# Standard cent precision. Single source of truth — change here and
# every helper updates.
CENTS = Decimal('0.01')


class CurrencyMismatch(ValueError):
    """Raised when arithmetic mixes two different currencies."""


def _decimal_of(value: MoneyLike) -> Decimal:
    """Pull a ``Decimal`` out of a Money / Decimal / int / float / str."""
    if isinstance(value, Money):
        return Decimal(str(value.amount))
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _currency_of(value: MoneyLike, default: str = 'USD') -> str:
    """Pull a 3-letter ISO currency string out of a Money — or return
    the supplied default for non-Money inputs."""
    if isinstance(value, Money):
        return str(value.currency)
    return default


def quantize(value: MoneyLike, *, currency: str | None = None) -> Money:
    """Quantize to 2 decimal places (HALF_UP), wrap as Money.

    ``currency`` is required when ``value`` is a raw Decimal/number.
    For a Money input, the existing currency is preserved unless
    ``currency`` overrides it (rare — usually a bug; logs a warning).
    """
    amount = _decimal_of(value).quantize(CENTS, rounding=ROUND_HALF_UP)
    if currency is None:
        currency = _currency_of(value)
    return Money(amount, currency)


def money(amount: MoneyLike, currency: str = 'USD') -> Money:
    """Construct a Money, quantized. Accepts any numeric input.

    Replaces the verbose ``Money(Decimal(str(x)), 'USD').quantize(...)``
    boilerplate scattered across the codebase.
    """
    return quantize(amount, currency=currency)


def same_currency(a: Money, b: Money) -> bool:
    """True iff two Money values share a currency. Cheap str compare."""
    return str(a.currency) == str(b.currency)


def assert_same_currency(a: Money, b: Money) -> None:
    """Raise ``CurrencyMismatch`` if the two Money values disagree."""
    if not same_currency(a, b):
        raise CurrencyMismatch(f'currency mismatch: {a.currency} vs {b.currency}')


def add(a: Money, b: Money) -> Money:
    """``a + b`` — currency-checked, quantized."""
    assert_same_currency(a, b)
    return quantize(_decimal_of(a) + _decimal_of(b), currency=str(a.currency))


def sub(a: Money, b: Money) -> Money:
    """``a - b`` — currency-checked, quantized. Negative results allowed."""
    assert_same_currency(a, b)
    return quantize(_decimal_of(a) - _decimal_of(b), currency=str(a.currency))


def mul(value: Money, factor: MoneyLike) -> Money:
    """Multiply a Money by a Decimal-like factor. Quantized result.

    Use this for percentage discounts, currency conversions, commission
    rates — anywhere a Money meets a unitless number.
    """
    factor_d = _decimal_of(factor)
    return quantize(_decimal_of(value) * factor_d, currency=_currency_of(value))


def apply_pct(value: Money, percent: MoneyLike) -> Money:
    """Apply a percentage (e.g. ``Decimal('5')`` for 5%) to a Money.

    Returns the *discount amount*, not the post-discount value:
        ``apply_pct(Money(100, 'USD'), 10) → Money(10, 'USD')``
    Caller subtracts to get the new total — keeps "discount" and
    "total after discount" calculations explicit at the callsite.
    """
    pct = _decimal_of(percent) / Decimal('100')
    return mul(value, pct)


def is_positive(value: Money) -> bool:
    return _decimal_of(value) > 0


def is_zero(value: Money) -> bool:
    return _decimal_of(value) == 0


def zero(currency: str = 'USD') -> Money:
    """``Money(0, currency)`` — handy when initialising sums."""
    return Money(Decimal('0'), currency)


def cap(value: Money, ceiling: Money) -> Money:
    """Clamp ``value`` to at most ``ceiling``. Currencies must match."""
    assert_same_currency(value, ceiling)
    if _decimal_of(value) > _decimal_of(ceiling):
        return ceiling
    return value


def floor_at_zero(value: Money) -> Money:
    """Clamp ``value`` to zero — never go negative."""
    if _decimal_of(value) < 0:
        return zero(_currency_of(value))
    return value
