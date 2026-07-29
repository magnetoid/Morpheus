"""Subscription lifecycle emails — dunning + pre-renewal.

Two beat-driven drips, modelled on the cart_abandonment shape (consent-gated,
per-step stamping under a row lock, sent via the central email registry):

1. **Dunning** (``send_dunning_emails``, hourly): for every ``past_due``
   subscription, send ``subscription_payment_failed`` on a day schedule
   (config ``dunning_step_days``, default ``[0, 3, 7]``) anchored on when the
   subscription entered past_due, once per step. Stops the moment the
   subscription leaves ``past_due`` (the webhook clears the marker).

2. **Pre-renewal** (``send_renewal_reminders``, daily): for every ``active``
   subscription whose ``current_period_end`` falls within ``prerenewal_days``
   (config, default 3), send ``subscription_upcoming_renewal`` once per period.

Zero migrations: the per-step "sent" markers and the "reminded this period"
marker both live in ``Subscription.metadata`` (an existing ``JSONField``) — the
same no-column approach the webhook reconciler uses for the dunning anchor.

Configuration (per-plugin, in the dashboard or DB):
    prerenewal_days           — default 3. Renewal reminder lead time (days).
    dunning_step_days         — default [0, 3, 7]. Dunning step schedule (days
                                since the subscription entered past_due).
    require_marketing_consent — default True. Only email customers whose latest
                                consent log opts in to marketing.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger('morpheus.subscriptions.tasks')


_DEFAULTS = {
    'prerenewal_days': 3,
    'dunning_step_days': [0, 3, 7],
    'require_marketing_consent': True,
}

_DUNNING_SUBJECT = 'Your subscription payment failed — action needed'
_RENEWAL_SUBJECT = 'Your subscription renews soon'


def _config() -> dict:
    """Read plugin config with sensible defaults if the DB row is absent."""
    cfg = dict(_DEFAULTS)
    try:
        from plugins.registry import plugin_registry

        plugin = plugin_registry.get('subscriptions')
        if plugin is not None:
            raw = plugin.get_config()
            cfg['prerenewal_days'] = int(raw.get('prerenewal_days', 3))
            steps = raw.get('dunning_step_days') or _DEFAULTS['dunning_step_days']
            cfg['dunning_step_days'] = [int(d) for d in steps]
            cfg['require_marketing_consent'] = bool(raw.get('require_marketing_consent', True))
    except Exception:  # noqa: BLE001, S110 — config unavailable → defaults
        pass
    return cfg


def _manage_url() -> str:
    """Absolute URL of the storefront membership page (payment-update / cancel /
    pause CTAs all live there)."""
    from morpheus.core import site_base_url

    return f'{site_base_url().rstrip("/")}/membership/'


def _has_marketing_consent(customer) -> bool:
    """True only when the customer's most recent consent log opts in to
    marketing. No consent row (or no consent plugin) → False — we never email
    without a recorded yes, exactly like the cart-recovery drip.
    """
    if customer is None:
        return False
    try:
        from plugins.installed.consent.models import ConsentLog

        latest = ConsentLog.objects.filter(customer=customer).order_by('-created_at').first()
    except Exception as e:  # noqa: BLE001 — consent plugin missing/migrating
        logger.warning('subscriptions: consent lookup failed: %s', e)
        return False
    return bool(latest and latest.marketing)


# ── Dunning ──────────────────────────────────────────────────────────────────


@shared_task(bind=True, time_limit=120, soft_time_limit=90)
def send_dunning_emails(self) -> dict:
    """Send each due, unsent dunning step for every ``past_due`` subscription."""
    cfg = _config()
    steps = cfg['dunning_step_days']
    if not steps:
        return {'scanned': 0, 'sent': 0}

    try:
        from core.emails import send_templated_email
        from plugins.installed.subscriptions.models import Subscription
    except Exception as e:  # noqa: BLE001 — imports unavailable
        logger.warning('subscriptions: dunning imports unavailable: %s', e)
        return {'scanned': 0, 'sent': 0}

    now = timezone.now()
    qs = Subscription.objects.filter(state='past_due').select_related('plan', 'customer')

    scanned = 0
    sent = 0
    for sub in qs.iterator(chunk_size=200):
        scanned += 1
        try:
            sent += _dun_subscription(sub, now, cfg, send_templated_email)
        except Exception as e:  # noqa: BLE001 — never fail the batch on one row
            logger.warning('subscriptions: dunning sub %s failed: %s', sub.id, e)

    return {'scanned': scanned, 'sent': sent}


def _dun_subscription(sub, now, cfg, send_templated_email) -> int:
    """Send every due+unsent dunning step for one subscription (returns count).

    Anchors the step schedule on ``metadata['dunning']['anchor']`` (stamped by
    the webhook on entry into past_due), falling back to the latest open
    invoice's timestamp. Send+stamp run under a row lock so two overlapping
    runs can't double-send a step.
    """
    from plugins.installed.subscriptions.models import Subscription

    email = (getattr(sub.customer, 'email', '') or '').strip()
    if not email:
        return 0
    if cfg['require_marketing_consent'] and not _has_marketing_consent(sub.customer):
        return 0

    steps = cfg['dunning_step_days']
    manage_url = _manage_url()
    sent_now = 0
    with transaction.atomic():
        locked = Subscription.objects.select_for_update(skip_locked=True).filter(pk=sub.pk).first()
        if locked is None or locked.state != 'past_due':
            return 0

        meta = dict(getattr(locked, 'metadata', {}) or {})
        dunning = dict(meta.get('dunning') or {})
        anchor = _parse_dt(dunning.get('anchor')) or _anchor_from_invoice(locked) or now
        already = list(dunning.get('sent') or [])
        age_days = (now - anchor).total_seconds() / 86400

        for i, day in enumerate(steps):
            if i in already:
                continue
            if age_days < day:
                continue
            send_templated_email(
                key='subscription_payment_failed',
                to=email,
                subject=_DUNNING_SUBJECT,
                ctx={
                    'subscription': locked,
                    'plan': locked.plan,
                    'manage_url': manage_url,
                    'step': i + 1,
                },
            )
            already.append(i)
            sent_now += 1

        if sent_now:
            dunning['anchor'] = anchor.isoformat()
            dunning['sent'] = already
            meta['dunning'] = dunning
            locked.metadata = meta
            locked.save(update_fields=['metadata'])

    return sent_now


def _anchor_from_invoice(sub):
    """Fallback dunning anchor: the latest open invoice's ``created_at`` (or ``None``)."""
    inv = sub.invoices.filter(state='open').order_by('-created_at').first()
    return inv.created_at if inv is not None else None


# ── Pre-renewal ──────────────────────────────────────────────────────────────


@shared_task(bind=True, time_limit=120, soft_time_limit=90)
def send_renewal_reminders(self) -> dict:
    """Remind every ``active`` subscription renewing within ``prerenewal_days``."""
    cfg = _config()
    days = cfg['prerenewal_days']

    try:
        from core.emails import send_templated_email
        from plugins.installed.subscriptions.models import Subscription
    except Exception as e:  # noqa: BLE001 — imports unavailable
        logger.warning('subscriptions: renewal imports unavailable: %s', e)
        return {'scanned': 0, 'sent': 0}

    now = timezone.now()
    horizon = now + timedelta(days=days)
    qs = Subscription.objects.filter(
        state='active',
        cancel_at_period_end=False,  # a cancelling sub isn't renewing — don't remind
        current_period_end__isnull=False,
        current_period_end__gte=now,
        current_period_end__lte=horizon,
    ).select_related('plan', 'customer')

    scanned = 0
    sent = 0
    for sub in qs.iterator(chunk_size=200):
        scanned += 1
        try:
            sent += _remind_subscription(sub, now, cfg, send_templated_email)
        except Exception as e:  # noqa: BLE001 — never fail the batch on one row
            logger.warning('subscriptions: renewal sub %s failed: %s', sub.id, e)

    return {'scanned': scanned, 'sent': sent}


def _remind_subscription(sub, now, cfg, send_templated_email) -> int:
    """Send the pre-renewal reminder once per period for one subscription.

    Idempotent within a period: ``metadata['renewal_notified']`` stores the
    ``current_period_end`` we last reminded for; a matching value skips. A new
    period has a new ``current_period_end``, so the next cycle reminds again.
    """
    from plugins.installed.subscriptions.models import Subscription

    email = (getattr(sub.customer, 'email', '') or '').strip()
    if not email:
        return 0
    if cfg['require_marketing_consent'] and not _has_marketing_consent(sub.customer):
        return 0

    period_end = sub.current_period_end
    if period_end is None:
        return 0
    marker = period_end.isoformat()
    manage_url = _manage_url()

    with transaction.atomic():
        locked = Subscription.objects.select_for_update(skip_locked=True).filter(pk=sub.pk).first()
        if locked is None or locked.state != 'active':
            return 0
        meta = dict(getattr(locked, 'metadata', {}) or {})
        if meta.get('renewal_notified') == marker:
            return 0  # already reminded for this period

        send_templated_email(
            key='subscription_upcoming_renewal',
            to=email,
            subject=_RENEWAL_SUBJECT,
            ctx={
                'subscription': locked,
                'plan': locked.plan,
                'manage_url': manage_url,
                'renews_on': period_end,
            },
        )
        meta['renewal_notified'] = marker
        locked.metadata = meta
        locked.save(update_fields=['metadata'])

    return 1


# ── Shared ───────────────────────────────────────────────────────────────────


def _parse_dt(raw):
    """Parse an ISO stamp into an aware datetime (``None`` if missing/unparseable)."""
    if not raw:
        return None
    dt = parse_datetime(raw)
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt
