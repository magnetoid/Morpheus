"""
Affiliate services: click tracking, attribution on order, payout requests.

Attribution model: cookie-based last-click. The storefront sets a cookie when
an affiliate link is hit (`/r/<code>`); on order placement we look up the
cookie and create an AffiliateConversion if the cookie is still within the
program's `cookie_window_days`.
"""
# ruff: noqa: PLC0415  — inline imports avoid plugin-load-order cycles (CLAUDE.md).
# ruff: noqa: S110     — best-effort audit log; silent on missing core.audit.

from __future__ import annotations

import hashlib
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from djmoney.money import Money

logger = logging.getLogger('morpheus.affiliates')


def _hash_ip(ip: str) -> str:
    if not ip:
        return ''
    return hashlib.sha256(ip.encode()).hexdigest()[:32]


class HandleUnavailable(ValueError):
    """Raised when generate_unique_handle gives up after the retry budget.

    Callers should surface this as a 400-class user-facing error
    ("please pick a different handle") rather than a 403/500.
    """


def generate_unique_handle(customer, *, suggested: str = '', max_tries: int = 50) -> str:
    """Pick a unique `Affiliate.handle` slug for `customer`.

    Tries the suggested value first (slugified), then numeric suffixes
    up to `max_tries`. Falls back to `aff-<8-char-pk-prefix>` if the
    customer's `.email` is missing — covers SSO / passwordless users
    where `.email` may be empty or None.

    Raises `HandleUnavailable` if every candidate collides within
    `max_tries`. The caller is responsible for turning that into a
    400 response with a friendly message.
    """
    from django.utils.text import slugify

    from plugins.installed.affiliates.models import Affiliate

    # Pick a seed slug from (in priority): explicit suggested value,
    # email local-part, or a customer-id-based fallback.
    email = (getattr(customer, 'email', '') or '').strip()
    local = email.split('@', 1)[0] if '@' in email else ''
    seed = slugify(suggested or '')[:80] or slugify(local)[:80]
    if not seed:
        # Last resort: never crash. UUID pk has 36 chars; take the first 8
        # of the hex form for a short, stable, unique-ish handle.
        seed = f'aff-{str(getattr(customer, "pk", "anon"))[:8]}'

    handle, base, idx = seed, seed, 2
    while Affiliate.objects.filter(handle=handle).exists():
        handle = f'{base[:74]}-{idx}'
        idx += 1
        if idx > max_tries:
            raise HandleUnavailable(seed)
    return handle


def record_click(
    *,
    code: str,
    referer: str = '',
    user_agent: str = '',
    ip: str = '',
) -> AffiliateLink | None:  # noqa: F821
    from plugins.installed.affiliates.models import AffiliateClick, AffiliateLink

    try:
        link = AffiliateLink.objects.select_related('affiliate', 'affiliate__program').get(
            code=code,
            is_active=True,
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


def attribute_order(
    *, order, affiliate_code: str = '', coupon_code: str = ''
) -> AffiliateConversion | None:  # noqa: F821
    """Create an AffiliateConversion for ``order``.

    Two attribution paths:
      1. Click-token referral: ``affiliate_code`` from the
         ``morph_aff`` cookie or URL parameter — the canonical path.
      2. Coupon-code attribution (A1.5): when a customer redeems a
         coupon that's tied to an affiliate via
         ``AffiliateLink.coupon_code``, attribute even without a
         click. Refersion + Tapfiliate both ship this — it's how
         influencer collaborations work in 2026.

    The cookie window is enforced HERE: we look up the most recent
    click for the link and refuse attribution if the click is older
    than ``program.cookie_window_days``. Previously the lock-window
    was stored on the conversion row but never re-checked.
    """
    from datetime import timedelta as _td

    from plugins.installed.affiliates.models import (
        AffiliateClick,
        AffiliateConversion,
        AffiliateLink,
    )

    link = None
    via = ''

    # Path 1 — referral code from cookie / URL.
    if affiliate_code:
        try:
            link = AffiliateLink.objects.select_related('affiliate', 'affiliate__program').get(
                code=affiliate_code,
                is_active=True,
            )
            via = 'click'
        except AffiliateLink.DoesNotExist:
            link = None

    # Path 2 — coupon-code attribution.
    if link is None and coupon_code:
        try:
            link = (
                AffiliateLink.objects.select_related('affiliate', 'affiliate__program')
                .filter(
                    coupon_code__iexact=coupon_code.strip(),
                    is_active=True,
                )
                .first()
            )
            if link is not None:
                via = 'coupon'
        except Exception:  # noqa: BLE001 — coupon_code column may not exist on fresh installs
            link = None

    if link is None:
        return None
    if link.affiliate.status != 'approved':
        return None

    program = link.affiliate.program

    # Enforce cookie window for click-referral path (coupon path is
    # not bound by click recency — the influencer's audience may
    # have heard the code months ago).
    if via == 'click':
        cutoff = timezone.now() - _td(days=program.cookie_window_days)
        recent_click = (
            AffiliateClick.objects.filter(link=link, occurred_at__gte=cutoff)
            .order_by('-occurred_at')
            .first()
        )
        if recent_click is None:
            logger.info(
                'affiliates: refused click attribution for order %s — '
                'no click within %d-day window',
                getattr(order, 'order_number', order.pk),
                program.cookie_window_days,
            )
            return None

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
                'locked_until': timezone.now()
                + timezone.timedelta(days=program.cookie_window_days),
            },
        )
        if created:
            AffiliateLink.objects.filter(pk=link.pk).update(
                conversion_count=link.conversion_count + 1,
            )
    return conv


def clawback_on_refund(*, order) -> AffiliateConversion | None:  # noqa: F821
    """Reverse an affiliate conversion when its order is refunded.

    Three outcomes, in order of severity:
      - status='pending' or 'approved'      → flip to 'rejected'; the
        commission never made it to the affiliate's accrued_balance so
        no debit needed unless we already approved it.
      - status='paid' → mark 'rejected' + log a clawback in the audit
        log. Money's already out the door; the merchant chases through
        the next payout cycle (Phase 4 will automate this).

    Returns the conversion row, or None when the order has no
    associated affiliate conversion.
    """
    from plugins.installed.affiliates.models import (
        Affiliate,
        AffiliateConversion,
    )

    try:
        conv = AffiliateConversion.objects.select_related('affiliate').get(order=order)
    except AffiliateConversion.DoesNotExist:
        return None
    if conv.status == 'rejected':
        return conv  # already reversed

    with transaction.atomic():
        if conv.status == 'approved':
            # Debit the affiliate's accrued balance (floor at 0).
            aff = conv.affiliate
            new_accrued = max(aff.accrued_balance.amount - conv.commission.amount, Decimal('0'))
            Affiliate.objects.filter(pk=aff.pk).update(
                accrued_balance=Money(new_accrued, str(conv.commission.currency)),
            )
        was = conv.status
        conv.status = 'rejected'
        conv.save(update_fields=['status'])
    logger.info(
        'affiliates: clawback on order %s — conversion %s was %s, now rejected',
        getattr(order, 'order_number', order.pk),
        conv.pk,
        was,
    )
    try:
        from core.audit.services import record as audit_record

        audit_record(
            event_type='affiliates.clawback',
            target=str(order.pk),
            metadata={
                'conversion_id': str(conv.pk),
                'previous_status': was,
                'commission_amount': str(conv.commission.amount),
                'commission_currency': str(conv.commission.currency),
            },
        )
    except Exception:  # noqa: BLE001
        pass
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


def request_payout(*, affiliate, amount: Money, method: str = '') -> AffiliatePayout:  # noqa: F821
    from plugins.installed.affiliates.models import AffiliatePayout

    if amount.amount <= 0:
        raise ValueError('Payout amount must be positive')
    if amount.amount > affiliate.accrued_balance.amount:
        raise ValueError('Payout exceeds accrued balance')
    return AffiliatePayout.objects.create(
        affiliate=affiliate,
        amount=amount,
        method=method,
        status='pending',
    )


def pending_payout_amount(affiliate) -> Money:
    """Sum of approved-but-unpaid conversion commissions for ``affiliate``.

    "Unpaid" = status='approved' AND payout IS NULL. Conversions already
    bundled into a pending payout don't count again.
    """
    from plugins.installed.affiliates.models import AffiliateConversion

    currency = str(affiliate.accrued_balance.currency)
    total = Decimal('0')
    qs = AffiliateConversion.objects.filter(
        affiliate=affiliate,
        status='approved',
        payout__isnull=True,
    )
    for row in qs.only('commission'):
        total += row.commission.amount
    return Money(total, currency)


def has_pending_payout(affiliate) -> bool:
    from plugins.installed.affiliates.models import AffiliatePayout

    return AffiliatePayout.objects.filter(
        affiliate=affiliate,
        status__in=('pending', 'processing'),
    ).exists()


def request_affiliate_payout(
    affiliate,
    amount: Money | None = None,
    method: str = '',
) -> AffiliatePayout:  # noqa: F821
    """Self-service payout: bundle unpaid approved conversions into one row.

    Differs from ``request_payout`` (admin-side, free-form amount):
      * Validates against ``pending_payout_amount``, not accrued_balance.
      * Refuses if a pending/processing payout already exists for this
        affiliate — affiliates don't get to stack requests.
      * Sets ``AffiliateConversion.payout`` on every conversion that
        contributed, so the audit trail survives.
    """
    from plugins.installed.affiliates.models import (
        AffiliateConversion,
        AffiliatePayout,
    )

    if has_pending_payout(affiliate):
        raise ValueError('A payout request is already pending.')

    pending = pending_payout_amount(affiliate)
    if pending.amount <= 0:
        raise ValueError('No approved earnings available to pay out.')
    amount = amount or pending
    if amount.amount > pending.amount:
        raise ValueError('Payout exceeds available approved earnings.')

    method = (method or affiliate.preferred_payout_method or 'paypal')[:40]

    with transaction.atomic():
        payout = AffiliatePayout.objects.create(
            affiliate=affiliate,
            amount=amount,
            method=method,
            status='pending',
        )
        AffiliateConversion.objects.filter(
            affiliate=affiliate,
            status='approved',
            payout__isnull=True,
        ).update(payout=payout)
    logger.info(
        'affiliates: payout %s requested by %s — %s via %s',
        payout.pk,
        affiliate.handle,
        amount,
        method,
    )
    return payout


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
