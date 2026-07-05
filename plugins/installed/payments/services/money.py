"""ISO-4217 minor-unit conversion for payment providers.

Stripe (and most processors) take amounts in the currency's *minor* unit:
cents for USD/EUR (exponent 2), whole yen for JPY (exponent 0), mils for
BHD/KWD (exponent 3). A blanket ``* 100`` overcharges zero-decimal
currencies 100x — always convert through :func:`amount_to_minor`.

Deliberately self-contained: ``agentic_checkout.serializers`` carries the
same exponent map for its own response shaping, but payments must not
import an optional consumer plugin (wrong-direction coupling).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

_ZERO_DECIMAL = {'JPY', 'KRW', 'VND', 'CLP', 'ISK', 'HUF'}
_THREE_DECIMAL = {'BHD', 'KWD', 'OMR', 'TND'}


def minor_unit_exponent(currency: str) -> int:
    """ISO-4217 minor-unit exponent for ``currency`` (default 2)."""
    code = (currency or 'USD').upper()
    if code in _ZERO_DECIMAL:
        return 0
    if code in _THREE_DECIMAL:
        return 3
    return 2


def amount_to_minor(amount: Decimal, currency: str) -> int:
    """Decimal major units -> integer minor units for ``currency``."""
    factor = Decimal(10) ** minor_unit_exponent(currency)
    return int((Decimal(amount) * factor).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
