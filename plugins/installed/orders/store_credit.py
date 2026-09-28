"""StoreCredit service — issue, redeem, balance lookup.

All writes go through here so the denormalised balance row stays in
sync with the immutable ``StoreCreditTxn`` ledger. Concurrency is
handled with ``select_for_update`` inside an atomic transaction.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from djmoney.money import Money

logger = logging.getLogger('morpheus.orders.store_credit')


def _balance_row(customer):
    from plugins.installed.orders.models import StoreCredit

    sc, _ = StoreCredit.objects.select_for_update().get_or_create(
        customer=customer,
        defaults={'balance': Money(Decimal('0'), 'USD')},
    )
    return sc


def issue(customer, *, amount: Money, reference: str = '', note: str = '', created_by=None):
    """Add credit to the customer's account. Returns the new balance."""
    from core.money import add, is_positive, money
    from plugins.installed.orders.models import StoreCreditTxn

    if not is_positive(amount):
        raise ValueError('store credit amount must be positive')
    with transaction.atomic():
        row = _balance_row(customer)
        # Currency mismatch: keep the existing balance currency authoritative
        # (a brand-new row created with Money(0, 'USD') is fine to overwrite).
        if str(row.balance.currency) != str(amount.currency) and row.balance.amount > 0:
            raise ValueError(
                f'currency mismatch: balance is {row.balance.currency}, '
                f'tried to issue in {amount.currency}'
            )
        if row.balance.amount == 0 and str(row.balance.currency) != str(amount.currency):
            row.balance = money(0, str(amount.currency))
        row.balance = add(row.balance, amount)
        row.save(update_fields=['balance', 'updated_at'])
        StoreCreditTxn.objects.create(
            customer=customer,
            kind='credit',
            amount=amount,
            reference=reference[:64],
            note=note[:300],
            created_by=created_by if (created_by and getattr(created_by, 'pk', None)) else None,
        )
    return row.balance


def redeem(customer, *, amount: Money, reference: str = '', note: str = ''):
    """Deduct from the customer's balance. Raises ValueError if insufficient."""
    from core.money import is_positive, sub
    from plugins.installed.orders.models import StoreCreditTxn

    if not is_positive(amount):
        raise ValueError('redeem amount must be positive')
    with transaction.atomic():
        row = _balance_row(customer)
        if row.balance.amount < amount.amount:
            raise ValueError('insufficient store credit')
        row.balance = sub(row.balance, amount)
        row.save(update_fields=['balance', 'updated_at'])
        StoreCreditTxn.objects.create(
            customer=customer,
            kind='debit',
            amount=amount,
            reference=reference[:64],
            note=note[:300],
        )
    return row.balance


def balance(customer) -> Money:
    """Read the current balance. Returns Money(0, USD) when no row exists yet."""
    from plugins.installed.orders.models import StoreCredit

    sc = StoreCredit.objects.filter(customer=customer).first()
    if sc is None:
        return Money(Decimal('0'), 'USD')
    return sc.balance


# ── Spending it: a checkout tender, re-credited on cancel and refund ─────────
#
# Store credit was issued by returns and shown on the account page, but no cart
# step could spend it. It now pays down the final total like a gift card
# (CART_CALCULATE_BREAKDOWN @46, folded into discount), is debited when the
# order is placed, and comes back — in full on cancel, pro rata on a refund —
# because a tender that isn't re-credited is kept by the merchant.


def available_for(customer, currency: str) -> Decimal:
    """Spendable balance in ``currency`` (0 when none, or held in another currency)."""
    from plugins.installed.orders.models import StoreCredit

    row = StoreCredit.objects.filter(customer=customer).first()
    if row is None or str(row.balance.currency) != currency:
        return Decimal('0')
    return max(Decimal(row.balance.amount), Decimal('0'))


def _used(order) -> Decimal:
    return Decimal(str((order.metadata or {}).get('store_credit_used') or '0'))


def _recredited(customer, reference: str) -> Decimal:
    from django.db.models import Q

    from plugins.installed.orders.models import StoreCreditTxn

    rows = StoreCreditTxn.objects.filter(customer=customer, kind='credit').filter(
        Q(reference=f'{reference}:cancel') | Q(reference__startswith=f'{reference}:r:')
    )
    return sum((Decimal(r.amount.amount) for r in rows), Decimal('0'))


def recredit_cancelled_order(order) -> None:
    """Return the store credit spent on a cancelled order — whatever refunds
    haven't already returned. Idempotent."""
    from core.money import money
    from plugins.installed.orders.models import StoreCreditTxn

    used = _used(order)
    if used <= 0 or not order.customer_id:
        return
    reference = f'{order.order_number}:cancel'
    with transaction.atomic():
        _balance_row(order.customer)  # lock: one re-credit per event, however delivered
        if StoreCreditTxn.objects.filter(customer=order.customer, reference=reference).exists():
            return
        remaining = used - _recredited(order.customer, order.order_number)
        if remaining > 0:
            issue(
                order.customer,
                amount=money(remaining, str(order.total.currency)),
                reference=reference,
                note='Order cancelled',
            )


def recredit_refund(order, refund) -> None:
    """Re-credit store credit in proportion to a refund: cash and credit are
    shares of the same returned goods (``refund.amount / order.total``).
    Idempotent per refund and capped at what was spent."""
    from core.money import money
    from plugins.installed.orders.models import StoreCreditTxn

    used = _used(order)
    if used <= 0 or not order.customer_id or refund is None:
        return
    reference = f'{order.order_number}:r:{refund.pk}'
    total = Decimal(order.total.amount)
    if total <= 0:
        logger.warning(
            'store credit: order %s was paid entirely in credit — refund %s needs a '
            'manual re-credit (nothing to prorate against)',
            order.order_number,
            refund.pk,
        )
        return
    fraction = min(Decimal('1'), max(Decimal('0'), Decimal(refund.amount.amount) / total))
    with transaction.atomic():
        _balance_row(order.customer)
        if StoreCreditTxn.objects.filter(customer=order.customer, reference=reference).exists():
            return
        credit = min(
            (used * fraction).quantize(Decimal('0.01')),
            used - _recredited(order.customer, order.order_number),
        )
        if credit > 0:
            issue(
                order.customer,
                amount=money(credit, str(order.total.currency)),
                reference=reference,
                note='Refund',
            )
