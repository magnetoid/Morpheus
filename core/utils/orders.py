"""Small order helpers shared across plugins."""

from __future__ import annotations


def order_email(order) -> str:
    """The best contact email for an order.

    An Order's own ``email`` is set for BOTH guest and account orders, so it's
    the canonical source; fall back to the linked customer's email. Single
    source of truth so callers don't re-derive it by hand and re-introduce the
    ``customer_email`` (a field that never existed on Order) bug that shipped in
    fraud_rules/bookvault. Always returns a stripped string ('' when unknown).
    """
    direct = (getattr(order, 'email', '') or '').strip()
    if direct:
        return direct
    cust = getattr(order, 'customer', None)
    return (getattr(cust, 'email', '') or '').strip() if cust else ''
