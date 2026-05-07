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
            customer=customer, kind='credit',
            amount=amount, reference=reference[:64], note=note[:300],
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
            customer=customer, kind='debit',
            amount=amount, reference=reference[:64], note=note[:300],
        )
    return row.balance


def balance(customer) -> Money:
    """Read the current balance. Returns Money(0, USD) when no row exists yet."""
    from plugins.installed.orders.models import StoreCredit
    sc = StoreCredit.objects.filter(customer=customer).first()
    if sc is None:
        return Money(Decimal('0'), 'USD')
    return sc.balance
