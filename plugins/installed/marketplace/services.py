"""
Marketplace services.

Splits a placed Order into per-vendor sub-orders, applies the vendor's
commission rate, and credits the vendor's payout account.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from djmoney.money import Money

logger = logging.getLogger('morpheus.marketplace')


def split_order(order) -> list[VendorOrder]:  # noqa: F821
    """Create VendorOrder rows for each vendor referenced by the order's items."""
    from plugins.installed.marketplace.models import VendorOrder

    by_vendor: dict[str, list] = defaultdict(list)
    for item in order.items.select_related('product', 'product__vendor').all():
        vendor = item.product.vendor if item.product else None
        if vendor is None:
            continue
        by_vendor[str(vendor.id)].append(item)

    out: list[VendorOrder] = []
    for items in by_vendor.values():
        vendor = items[0].product.vendor
        currency = str(items[0].unit_price.currency)
        gross = sum((item.total_price.amount for item in items), Decimal('0'))
        commission_pct = Decimal(vendor.commission_rate or 0) / Decimal('100')
        commission = (gross * commission_pct).quantize(Decimal('0.01'))
        net = (gross - commission).quantize(Decimal('0.01'))

        with transaction.atomic():
            vorder, created = VendorOrder.objects.get_or_create(
                parent_order=order,
                vendor=vendor,
                defaults={
                    'gross': Money(gross, currency),
                    'commission': Money(commission, currency),
                    'net': Money(net, currency),
                    'status': 'pending',
                    'items_snapshot': [
                        {
                            'sku': item.product.sku,
                            'name': item.product.name,
                            'quantity': item.quantity,
                            'unit_price': str(item.unit_price.amount),
                            'currency': currency,
                        }
                        for item in items
                    ],
                },
            )
            if created:
                _credit_vendor(vendor, Money(net, currency))
        out.append(vorder)

    return out


def _credit_vendor(vendor, amount: Money) -> None:
    from plugins.installed.marketplace.models import VendorPayoutAccount

    acct, _ = VendorPayoutAccount.objects.get_or_create(
        vendor=vendor,
        defaults={'method': 'unset'},
    )
    VendorPayoutAccount.objects.filter(pk=acct.pk).update(
        accrued_balance=acct.accrued_balance + amount,
    )


def request_vendor_payout(*, vendor, amount: Money, method: str = '') -> VendorPayout:  # noqa: F821
    from plugins.installed.marketplace.models import VendorPayout, VendorPayoutAccount

    if amount.amount <= 0:
        raise ValueError('Payout amount must be positive')
    acct = VendorPayoutAccount.objects.get(vendor=vendor)
    if amount.amount > acct.accrued_balance.amount:
        raise ValueError('Payout exceeds accrued balance')
    return VendorPayout.objects.create(
        vendor=vendor,
        amount=amount,
        method=method or acct.method,
        status='pending',
    )


def mark_vendor_payout_paid(payout, *, external_reference: str = '') -> None:
    from django.utils import timezone

    from plugins.installed.marketplace.models import VendorPayoutAccount

    if payout.status not in ('pending', 'processing'):
        raise ValueError(f'Cannot mark paid from state {payout.status}')
    with transaction.atomic():
        payout.status = 'paid'
        payout.external_reference = external_reference
        payout.paid_at = timezone.now()
        payout.save(update_fields=['status', 'external_reference', 'paid_at'])
        acct = VendorPayoutAccount.objects.get(vendor=payout.vendor)
        VendorPayoutAccount.objects.filter(pk=acct.pk).update(
            accrued_balance=acct.accrued_balance - payout.amount,
            lifetime_paid=acct.lifetime_paid + payout.amount,
        )
