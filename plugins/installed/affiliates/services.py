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


def _resolve_attribution_link(*, affiliate_code: str, coupon_code: str):
    """Resolve the AffiliateLink for an order, returning ``(link, via)``.

    Path 1 (``via='click'``): exact match on an active link ``code`` from the
    ``morph_aff`` cookie / URL. Path 2 (``via='coupon'``): the coupon code
    redeemed at checkout matches an active link's ``coupon_code``. Returns
    ``(None, '')`` when neither resolves.
    """
    import contextlib

    from plugins.installed.affiliates.models import AffiliateLink

    if affiliate_code:
        with contextlib.suppress(AffiliateLink.DoesNotExist):
            return (
                AffiliateLink.objects.select_related('affiliate', 'affiliate__program').get(
                    code=affiliate_code,
                    is_active=True,
                ),
                'click',
            )

    if coupon_code:
        # coupon_code column may not exist on fresh installs mid-migration.
        with contextlib.suppress(Exception):
            link = (
                AffiliateLink.objects.select_related('affiliate', 'affiliate__program')
                .filter(coupon_code__iexact=coupon_code.strip(), is_active=True)
                .first()
            )
            if link is not None:
                return link, 'coupon'

    return None, ''


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

    link, via = _resolve_attribution_link(affiliate_code=affiliate_code, coupon_code=coupon_code)
    if link is None:
        return None

    affiliate = link.affiliate
    program = affiliate.program

    # Status gate. Approved affiliates always attribute. A *pending*
    # affiliate attributes ONLY when the program has an auto-approve
    # threshold (auto_approve_after > 0) — we record pending conversions so
    # the threshold can be reached, then promote them below. Suspended /
    # rejected affiliates never attribute. (When auto_approve_after == 0 —
    # the default — pending affiliates earn nothing, preserving prior
    # behaviour.)
    auto_approve_on = int(getattr(program, 'auto_approve_after', 0) or 0) > 0
    attributable = affiliate.status == 'approved' or (
        affiliate.status == 'pending' and auto_approve_on
    )
    if not attributable:
        return None

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

    commission = _calculate_commission(program=program, order=order, affiliate=affiliate)
    if commission.amount <= 0:
        return None

    with transaction.atomic():
        conv, created = AffiliateConversion.objects.get_or_create(
            order=order,
            defaults={
                'affiliate': affiliate,
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
    # Auto-approve a pending affiliate once this conversion pushes them over
    # the program threshold. Runs after commit of the conversion so the count
    # includes it. Fail-soft: never let promotion failure unwind attribution.
    if created and affiliate.status == 'pending':
        try:
            maybe_auto_approve(affiliate)
        except Exception:  # noqa: BLE001
            logger.warning('affiliates: auto-approve check failed', exc_info=True)
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


def effective_tier(program, approved_conversions: int) -> dict | None:
    """Highest commission tier the affiliate has reached, or None.

    A tier qualifies when ``approved_conversions >= tier['min_conversions']``.
    The winner is the qualifying tier with the largest ``min_conversions``.
    Malformed rows (missing keys, non-numeric) are skipped, never crash —
    ``tiers`` is operator-entered JSON.
    """
    tiers = getattr(program, 'tiers', None) or []
    if not isinstance(tiers, list):
        return None
    best = None
    for t in tiers:
        if not isinstance(t, dict):
            continue
        try:
            min_conv = int(t.get('min_conversions', 0))
            pct = Decimal(str(t.get('percent')))
        except (TypeError, ValueError, ArithmeticError):
            continue
        if approved_conversions >= min_conv and (best is None or min_conv > best[0]):
            best = (min_conv, {'name': str(t.get('name', '')), 'percent': pct})
    return best[1] if best else None


def _affiliate_flat_override_percent(affiliate) -> Decimal | None:
    """Per-affiliate flat % override stored as a Metafield by the dashboard
    (``namespace='affiliates'``, ``key='commission_percent_override'``).

    Returns None when unset or when the metafields plugin is disabled. This
    is the *highest-priority* commission signal — a hand-set rate on a single
    affiliate overrides program tiers and category overrides.
    """
    try:
        from django.contrib.contenttypes.models import ContentType

        from plugins.installed.affiliates.models import Affiliate
        from plugins.installed.metafields.models import Metafield

        ct = ContentType.objects.get_for_model(Affiliate)
        m = Metafield.objects.filter(
            content_type=ct,
            object_id=str(affiliate.pk),
            namespace='affiliates',
            key='commission_percent_override',
        ).first()
        if m and (m.value or '').strip():
            return Decimal(str(m.value).strip())
    except Exception:  # noqa: BLE001 — metafields optional / bad value → no override
        return None
    return None


def _base_percent(*, program, affiliate) -> Decimal:
    """The applicable base percent for an affiliate before per-category
    overrides: flat per-affiliate override > tier rate > program default."""
    flat = _affiliate_flat_override_percent(affiliate)
    if flat is not None:
        return flat
    approved = affiliate.conversions.filter(status='approved').count()
    tier = effective_tier(program, approved)
    if tier is not None:
        return tier['percent']
    return Decimal(str(program.commission_value or 0))


def _product_category_slugs(product) -> list[str]:
    """Lower-cased category slugs a product belongs to (primary first, then
    additional_categories). Empty list for a deleted product. Never raises —
    the m2m may be unavailable in odd migration states."""
    import contextlib

    if product is None:
        return []
    slugs: list[str] = []
    if product.category_id and product.category:
        slugs.append((product.category.slug or '').lower())
    with contextlib.suppress(Exception):
        slugs += [
            (s or '').lower() for s in product.additional_categories.values_list('slug', flat=True)
        ]
    return slugs


def _calculate_commission(*, program, order, affiliate=None) -> Money:
    """Commission for ``order`` under ``program`` for ``affiliate``.

    Percent type, in priority:
      1. Per-category overrides — each order line whose product is in an
         overridden category earns that category's percent on the line total;
         the remaining lines earn the base percent. Falls back to whole-order
         base percent when no overrides are configured (cheap path).
      2. Base percent = flat affiliate override > tier rate > program default.
    Fixed type: the flat program amount, regardless of tiers/overrides.
    """
    from core.money import apply_pct, money

    currency = str(order.total.currency)
    if program.commission_type == 'fixed':
        return money(program.commission_value, currency)

    # A hand-set per-affiliate flat override wins outright — it skips both
    # tiers AND category overrides (a negotiated rate isn't undercut by a
    # category rule). Whole-order, like the legacy flat path.
    flat = _affiliate_flat_override_percent(affiliate) if affiliate is not None else None
    if flat is not None:
        return apply_pct(order.total, flat)

    base_pct = (
        _base_percent(program=program, affiliate=affiliate)
        if affiliate is not None
        else Decimal(str(program.commission_value or 0))
    )

    overrides = getattr(program, 'category_commission_overrides', None) or {}
    if not isinstance(overrides, dict) or not overrides:
        return apply_pct(order.total, base_pct)

    # Per-category path: sum per-line commission. A product can sit in a
    # primary category + additional_categories; the FIRST matching override
    # wins (deterministic, operator picks the slug). Lines with no product
    # (deleted) or no matching override earn the base percent.
    norm = {str(k).strip().lower(): _safe_decimal(v) for k, v in overrides.items()}
    norm = {k: v for k, v in norm.items() if v is not None}
    total_commission = Decimal('0')
    matched_any = False
    for item in order.items.select_related('product', 'product__category').all():
        line_total = item.total_price.amount
        pct = base_pct
        for s in _product_category_slugs(item.product):
            if s in norm:
                pct = norm[s]
                matched_any = True
                break
        total_commission += line_total * pct / Decimal('100')
    if not matched_any:
        # No line actually matched — equivalent to whole-order base percent,
        # but order.total includes shipping/tax which per-line sums exclude.
        # Prefer the whole-order base for parity with the no-override path.
        return apply_pct(order.total, base_pct)
    return money(total_commission, currency)


def _safe_decimal(v) -> Decimal | None:
    try:
        return Decimal(str(v))
    except (TypeError, ValueError, ArithmeticError):
        return None


def maybe_auto_approve(affiliate) -> bool:
    """Auto-approve a *pending* affiliate once they hit the program's
    ``auto_approve_after`` conversion count. Returns True if it flipped.

    Counts ALL attributed conversions (pending + approved) — the signal is
    "this person can drive sales", and a fresh conversion is pending until a
    human/clawback-window approves it. No-op when threshold is 0 or the
    affiliate isn't pending.
    """
    from plugins.installed.affiliates.models import Affiliate

    program = affiliate.program
    threshold = int(getattr(program, 'auto_approve_after', 0) or 0)
    if threshold <= 0 or affiliate.status != 'pending':
        return False
    count = affiliate.conversions.count()
    if count < threshold:
        return False
    Affiliate.objects.filter(pk=affiliate.pk, status='pending').update(
        status='approved',
        approved_at=timezone.now(),
    )
    logger.info(
        'affiliates: auto-approved %s after %d conversions (threshold %d)',
        affiliate.handle,
        count,
        threshold,
    )
    return True


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


def _affiliate_coupon_taken(code: str) -> bool:
    """True if a coupon code is already an affiliate link's code, or — fail-soft —
    an existing store promotion coupon (so an affiliate can't claim a code that
    would attribute the store's own promo orders to them)."""
    from plugins.installed.affiliates.models import AffiliateLink

    if AffiliateLink.objects.filter(coupon_code__iexact=code).exists():
        return True
    try:
        from plugins.installed.promotions.models import Promotion

        if Promotion.objects.filter(requires_coupon__iexact=code).exists():
            return True
    except Exception:  # noqa: BLE001 — promotions may be disabled
        pass
    return False


def affiliate_coupon(affiliate, *, claim: bool = False) -> str:
    """The affiliate's personal coupon code, or '' if none yet.

    With ``claim=True``, mint one: a handle-DERIVED code (so the affiliate can't
    pick an arbitrary code and hijack the store's own coupons), made unique with
    a numeric suffix, stored on a dedicated AffiliateLink. The code attributes
    sales via the existing coupon path; the store pairs it with a discount
    Promotion (merchant-managed). Returns the code (or '' if not claimed)."""
    import re

    from plugins.installed.affiliates.models import AffiliateLink

    existing = (
        AffiliateLink.objects.filter(affiliate=affiliate)
        .exclude(coupon_code='')
        .order_by('created_at')
        .first()
    )
    if existing:
        return existing.coupon_code
    if not claim:
        return ''

    base = re.sub(r'[^A-Z0-9]', '', (affiliate.handle or '').upper())[:16] or 'AFF'
    candidate, n = base, 1
    while _affiliate_coupon_taken(candidate):
        n += 1
        candidate = f'{base}{n}'
        if n > 50:
            import secrets

            candidate = f'{base}{secrets.token_hex(2).upper()}'
            break

    AffiliateLink.objects.create(
        affiliate=affiliate,
        landing_url='/',
        label='Personal coupon',
        coupon_code=candidate,
    )
    return candidate
