"""Referral tracking + reward minting."""

from __future__ import annotations

import logging
import secrets
from decimal import Decimal

from django.utils import timezone

logger = logging.getLogger('morpheus.loyalty.referrals')

DEFAULT_REFERRER_REWARD = 500  # points
DEFAULT_REFEREE_REWARD = 250
MIN_QUALIFYING_ORDER_USD = Decimal('20')


def referral_code_for(customer) -> str:
    """Return (and persist) this customer's permanent referral code.

    Stored on the customer profile via metadata; we mint a fresh one
    only if the customer has none.
    """
    code = (getattr(customer, 'metadata', {}) or {}).get('referral_code')
    if code:
        return code
    code = secrets.token_urlsafe(6).replace('_', '').replace('-', '').upper()[:10]
    meta = dict(getattr(customer, 'metadata', {}) or {})
    meta['referral_code'] = code
    customer.metadata = meta
    try:
        customer.save(update_fields=['metadata'])
    except Exception:  # noqa: BLE001 — metadata field may not exist on all User subclasses
        logger.exception(
            'loyalty.referrals: could not persist referral_code on user %s', customer.pk
        )
    return code


def record_referral(*, referrer_code: str, referee) -> None:
    """Called at signup when referee provides a code. No-op if invalid."""
    if not referrer_code:
        return
    referrer = _find_referrer(referrer_code)
    if referrer is None or referrer.pk == referee.pk:
        return
    from plugins.installed.loyalty_points.models import Referral  # noqa: PLC0415

    Referral.objects.get_or_create(
        referrer=referrer,
        referee=referee,
        defaults={'code': referrer_code, 'status': 'pending'},
    )


def qualify_on_order(order) -> None:
    """Called from ORDER_PLACED — if this is the referee's first
    qualifying order, transition their Referral to `qualified` and
    mint the rewards on both sides.
    """
    customer_id = getattr(order, 'customer_id', None)
    if not customer_id:
        return
    from plugins.installed.loyalty_points.models import (  # noqa: PLC0415
        PointsTransaction,
        Referral,
    )

    referral = Referral.objects.filter(referee_id=customer_id, status='pending').first()
    if referral is None:
        return

    # Only orders above the qualifying threshold count.
    total = getattr(order, 'total', None)
    amount = Decimal(str(getattr(total, 'amount', total) or 0))
    if amount < MIN_QUALIFYING_ORDER_USD:
        return

    now = timezone.now()
    referrer_reward = referral.referrer_reward_points or DEFAULT_REFERRER_REWARD
    referee_reward = referral.referee_reward_points or DEFAULT_REFEREE_REWARD

    referral.status = 'rewarded'
    referral.qualifying_order_number = getattr(order, 'order_number', '')
    referral.qualified_at = now
    referral.rewarded_at = now
    referral.referrer_reward_points = referrer_reward
    referral.referee_reward_points = referee_reward
    referral.save(
        update_fields=[
            'status',
            'qualifying_order_number',
            'qualified_at',
            'rewarded_at',
            'referrer_reward_points',
            'referee_reward_points',
        ]
    )

    PointsTransaction.objects.create(
        customer_id=referral.referrer_id,
        points=referrer_reward,
        reason='adjust',
        note=f'Referral reward: {referral.referee_id} placed first qualifying order',
    )
    PointsTransaction.objects.create(
        customer_id=referral.referee_id,
        points=referee_reward,
        reason='adjust',
        note=f'Welcome bonus from referral code {referral.code}',
    )
    logger.info(
        'loyalty.referrals: rewarded referral %s (+%s to referrer, +%s to referee)',
        referral.pk,
        referrer_reward,
        referee_reward,
    )


# ---------------------------------------------------------------------------


def _find_referrer(code: str):
    """Look up a customer by their stored referral code."""
    from django.contrib.auth import get_user_model  # noqa: PLC0415

    User = get_user_model()
    code = code.strip().upper()
    if not code:
        return None
    # Stored on the customer's metadata JSONField.
    return User.objects.filter(metadata__referral_code=code).first()
