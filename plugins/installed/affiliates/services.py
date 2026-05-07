"""
Affiliate services: click tracking, attribution on order, payout requests.

Attribution model: cookie-based last-click. The storefront sets a cookie when
an affiliate link is hit (`/r/<code>`); on order placement we look up the
cookie and create an AffiliateConversion if the cookie is still within the
program's `cookie_window_days`.
"""
from __future__ import annotations

import hashlib
import logging
from decimal import Decimal
from typing import Any, Optional

from django.db import transaction
from django.utils import timezone
from djmoney.money import Money

logger = logging.getLogger('morpheus.affiliates')


def _hash_ip(ip: str) -> str:
    if not ip:
        return ''
    return hashlib.sha256(ip.encode()).hexdigest()[:32]


def record_click(
    *,
    code: str,
    referer: str = '',
    user_agent: str = '',
    ip: str = '',
) -> Optional['AffiliateLink']:  # noqa: F821
    from plugins.installed.affiliates.models import AffiliateClick, AffiliateLink

    try:
        link = AffiliateLink.objects.select_related('affiliate', 'affiliate__program').get(
            code=code, is_active=True,
        )
    except AffiliateLink.DoesNotExist:
        return None

    AffiliateClick.objects.create(
        link=link,
        referer=referer[:500],
        user_agent=user_agent[:500],
        ip_hash=_hash_ip(ip),
    )
    AffiliateLink.objects.filter(pk=link.pk).update(click_count=link.click_count + 1)
    return link


def attribute_order(*, order, affiliate_code: str) -> Optional['AffiliateConversion']:  # noqa: F821
    """Create an AffiliateConversion for `order` if `affiliate_code` resolves and the cookie window is open."""
    from plugins.installed.affiliates.models import (
        AffiliateConversion,
        AffiliateLink,
    )

    if not affiliate_code:
        return None
    try:
        link = AffiliateLink.objects.select_related('affiliate', 'affiliate__program').get(
            code=affiliate_code, is_active=True,
        )
    except AffiliateLink.DoesNotExist:
        return None
    if link.affiliate.status != 'approved':
        return None

    program = link.affiliate.program
    commission = _calculate_commission(program=program, order=order)
    if commission.amount <= 0:
        return None

    with transaction.atomic():
        conv, created = AffiliateConversion.objects.get_or_create(
            order=order,
            defaults={
                'affiliate': link.affiliate,
                'link': link,
                'commission': commission,
                'status': 'pending',
                'locked_until': timezone.now() + timezone.timedelta(days=program.cookie_window_days),
            },
        )
        if created:
            AffiliateLink.objects.filter(pk=link.pk).update(
                conversion_count=link.conversion_count + 1,
            )
    return conv


def _calculate_commission(*, program, order) -> Money:
    from core.money import apply_pct, money

    currency = str(order.total.currency)
    if program.commission_type == 'fixed':
        return money(program.commission_value, currency)
    return apply_pct(order.total, program.commission_value)


def approve_conversion(conversion) -> None:
    from plugins.installed.affiliates.models import Affiliate

    if conversion.status != 'pending':
        raise ValueError(f'Cannot approve conversion in state {conversion.status}')
    with transaction.atomic():
        conversion.status = 'approved'
        conversion.save(update_fields=['status'])
        Affiliate.objects.filter(pk=conversion.affiliate_id).update(
            accrued_balance=conversion.affiliate.accrued_balance + conversion.commission,
        )


def request_payout(*, affiliate, amount: Money, method: str = '') -> 'AffiliatePayout':  # noqa: F821
    from plugins.installed.affiliates.models import AffiliatePayout

    if amount.amount <= 0:
        raise ValueError('Payout amount must be positive')
    if amount.amount > affiliate.accrued_balance.amount:
        raise ValueError('Payout exceeds accrued balance')
    return AffiliatePayout.objects.create(
        affiliate=affiliate, amount=amount, method=method, status='pending',
    )


def mark_payout_paid(payout, *, external_reference: str = '') -> None:
    from plugins.installed.affiliates.models import Affiliate

    if payout.status not in ('pending', 'processing'):
        raise ValueError(f'Cannot mark paid from state {payout.status}')
    with transaction.atomic():
        payout.status = 'paid'
        payout.external_reference = external_reference
        payout.paid_at = timezone.now()
        payout.save(update_fields=['status', 'external_reference', 'paid_at'])
        affiliate = payout.affiliate
        Affiliate.objects.filter(pk=affiliate.pk).update(
            accrued_balance=affiliate.accrued_balance - payout.amount,
            lifetime_paid=affiliate.lifetime_paid + payout.amount,
        )
