"""Cart-abandonment scanner.

Runs on a celery beat schedule. For each cart that:

  * has items,
  * was last updated more than ``abandon_after_minutes`` ago,
  * has not yet been emitted (cart.metadata['abandoned_emitted'] is unset),
  * (optionally) has a reachable email,

we fire ``events.CART_ABANDONED`` and stamp the cart so subsequent runs
skip it. Email + remarketing plugins subscribe to the event.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger('morpheus.cart_abandonment')


_DEFAULTS = {
    'abandon_after_minutes': 60,
    'require_email': True,
    'recovery_enabled': True,
    'step_delays_minutes': [60, 1440, 4320],
    'require_marketing_consent': True,
}


def _config() -> dict:
    """Read plugin config with sensible defaults if the DB row is absent."""
    cfg = dict(_DEFAULTS)
    try:
        from plugins.registry import app_registry

        plugin = app_registry.get('cart_abandonment')
        if plugin is not None:
            raw = plugin.get_config()
            cfg['abandon_after_minutes'] = int(raw.get('abandon_after_minutes', 60))
            cfg['require_email'] = bool(raw.get('require_email', True))
            cfg['recovery_enabled'] = bool(raw.get('recovery_enabled', True))
            delays = raw.get('step_delays_minutes') or _DEFAULTS['step_delays_minutes']
            cfg['step_delays_minutes'] = [int(d) for d in delays]
            cfg['require_marketing_consent'] = bool(raw.get('require_marketing_consent', True))
    except Exception:  # noqa: BLE001, S110
        pass
    return cfg


def _cart_email(cart) -> str:
    """Best-effort reach: customer's email, else the email the shopper typed
    at checkout (stamped onto ``cart.metadata['checkout_email']`` by the
    storefront checkout views) — this is what makes GUEST carts, the majority
    of abandonment, recoverable at all."""
    customer = getattr(cart, 'customer', None)
    if customer is not None:
        em = getattr(customer, 'email', '')
        if em:
            return em
    return str((getattr(cart, 'metadata', {}) or {}).get('checkout_email') or '').strip()


@shared_task(bind=True, time_limit=120, soft_time_limit=90)
def scan_abandoned_carts(self) -> dict:
    """Emit ``events.CART_ABANDONED`` once per newly-stale cart."""
    cfg = _config()
    cutoff = timezone.now() - timedelta(minutes=cfg['abandon_after_minutes'])

    try:
        from morpheus.core import events, hooks
        from plugins.installed.orders.models import Cart
    except Exception as e:  # noqa: BLE001 — plugin missing
        logger.warning('cart_abandonment: imports unavailable: %s', e)
        return {'scanned': 0, 'fired': 0}

    qs = Cart.objects.filter(updated_at__lt=cutoff, items__isnull=False).distinct()

    fired = 0
    scanned = 0
    for cart in qs.iterator(chunk_size=200):
        scanned += 1
        meta = dict(getattr(cart, 'metadata', {}) or {})
        if meta.get('abandoned_emitted'):
            continue
        email = _cart_email(cart)
        if cfg['require_email'] and not email:
            continue
        try:
            hooks.fire(events.CART_ABANDONED, cart=cart, email=email or None)
            fired += 1
            meta['abandoned_emitted'] = timezone.now().isoformat()
            cart.metadata = meta
            # NB: drop 'updated_at' — it's auto_now, so including it would bump
            # last-activity to now and reset the recovery-drip clock. The drip
            # ages off the stable 'abandoned_emitted' stamp, not updated_at.
            cart.save(update_fields=['metadata'])
        except Exception as e:  # noqa: BLE001 — never fail the whole sweep on one cart
            logger.warning('cart_abandonment: cart %s failed: %s', cart.id, e)

    return {'scanned': scanned, 'fired': fired}


# ── Recovery drip ──────────────────────────────────────────────────────────────
#
# The single owner of recovery email. core/emails and marketing no longer
# send anything for cart.abandoned — this task is the only code path.

_RECOVERY_SUBJECTS = {
    0: 'You left items in your cart',
    1: 'Your cart is still waiting',
    2: "Last chance — your cart's about to expire",
}


def _has_marketing_consent(cart) -> bool:
    """True only when the cart owner's most recent consent log opts in to
    marketing. Customers are matched by account; GUESTS by the cart's
    session_key (the consent banner logs both). No consent row → False —
    we never email without a recorded yes.
    """
    customer = getattr(cart, 'customer', None)
    session_key = getattr(cart, 'session_key', '') or ''
    try:
        from plugins.installed.consent.models import ConsentLog

        if customer is not None:
            latest = ConsentLog.objects.filter(customer=customer).order_by('-created_at').first()
        elif session_key:
            latest = (
                ConsentLog.objects.filter(session_key=session_key).order_by('-created_at').first()
            )
        else:
            return False
    except Exception as e:  # noqa: BLE001 — consent plugin missing/migrating
        logger.warning('cart_abandonment: consent lookup failed: %s', e)
        return False
    return bool(latest and latest.marketing)


def _drip_anchor(cart, now):
    """The stable timestamp the drip ages off.

    Detection stamps ``metadata['abandoned_emitted']`` (ISO) when it fires
    CART_ABANDONED; that is the cart's true last-activity and never moves.
    We anchor the drip on it, falling back to ``updated_at`` only when the
    stamp is missing or unparseable. The returned datetime is always
    timezone-aware so ``now − anchor`` is safe.
    """
    raw = (getattr(cart, 'metadata', {}) or {}).get('abandoned_emitted')
    if raw:
        dt = parse_datetime(raw)
        if dt is not None:
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            return dt
    return cart.updated_at


@shared_task(bind=True, time_limit=120, soft_time_limit=90)
def send_cart_recovery_drip(self) -> dict:
    """Send each due, unsent recovery step for every still-open abandoned cart.

    A cart is in the drip when it still HAS items (conversion empties the
    cart, so items-present is the recovered-guard), has a customer with an
    email, and its age is past step 1's delay. Age is measured from the
    stable ``metadata['abandoned_emitted']`` stamp (falling back to
    ``updated_at`` only if that's missing) — NOT live ``updated_at``, which
    auto_now would otherwise reset on every save. The cheap queryset
    pre-filter still uses ``updated_at`` to avoid scanning fresh carts; the
    per-step DUE decision uses the anchor. For each such cart we send every
    step whose delay has elapsed and that hasn't been sent yet (idempotency
    tracked in ``cart.metadata['recovery_drip_sent']``). Consent is checked
    per send when required. Fail-soft per cart so one bad row never breaks
    the batch.
    """
    cfg = _config()
    if not cfg['recovery_enabled']:
        return {'scanned': 0, 'sent': 0}

    delays = cfg['step_delays_minutes']
    if not delays:
        return {'scanned': 0, 'sent': 0}

    try:
        from core.emails import send_templated_email
        from plugins.installed.orders.models import Cart
    except Exception as e:  # noqa: BLE001 — plugin/import missing
        logger.warning('cart_abandonment: drip imports unavailable: %s', e)
        return {'scanned': 0, 'sent': 0}

    now = timezone.now()
    # Only carts old enough for at least step 1, that still have items.
    # GUEST carts are included — they're reachable when checkout stamped the
    # shopper's email onto metadata (see _cart_email); consent still gates
    # every send. Guest carts made up the majority of abandonment and were
    # previously excluded outright.
    cutoff = now - timedelta(minutes=delays[0])
    qs = Cart.objects.filter(updated_at__lt=cutoff, items__isnull=False).distinct()

    scanned = 0
    sent = 0
    for cart in qs.iterator(chunk_size=200):
        scanned += 1
        try:
            sent += _drip_cart(cart, now, cfg, send_templated_email)
        except Exception as e:  # noqa: BLE001 — never fail the batch on one cart
            logger.warning('cart_abandonment: drip cart %s failed: %s', cart.id, e)

    return {'scanned': scanned, 'sent': sent}


def _drip_cart(cart, now, cfg, send_templated_email) -> int:
    """Send every due+unsent step for one cart. Returns how many were sent.

    Anchors step timing on the stable ``abandoned_emitted`` stamp (not the
    auto_now ``updated_at``), only treats steps that have a template
    (``_RECOVERY_SUBJECTS``), and does the send+stamp under a row lock so two
    overlapping drip runs can't double-send a step.
    """
    from plugins.installed.cart_abandonment.services import (
        is_suppressed,
        recovery_unsubscribe_url,
        unsubscribe_headers,
    )
    from plugins.installed.orders.models import Cart

    email = _cart_email(cart)
    if not email:
        return 0

    # Honour a one-click unsubscribe: this is consent-gated marketing, so a
    # shopper who opted out is never emailed again (RFC 8058 / CAN-SPAM).
    if is_suppressed(email):
        return 0
    unsubscribe_url = recovery_unsubscribe_url(email)
    headers = unsubscribe_headers(email)

    age_minutes = (now - _drip_anchor(cart, now)).total_seconds() / 60

    # Never iterate past the steps that actually have a template — a delay
    # with no matching cart_recovery_N template would send nothing yet still
    # get marked sent (send_templated_email is silent on a missing key).
    max_steps = min(len(cfg['step_delays_minutes']), len(_RECOVERY_SUBJECTS))

    from morpheus.core import site_base_url

    cart_url = f'{site_base_url().rstrip("/")}/cart/'

    consent_ok = None  # lazily resolved once per cart
    sent_now = 0
    with transaction.atomic():
        # Re-load under a row lock and re-read the sent-list inside it, so a
        # concurrent run's append is seen and we don't re-send its step.
        locked = Cart.objects.select_for_update(skip_locked=True).filter(pk=cart.pk).first()
        if locked is None:
            # Another run holds the lock; skip this cart this pass.
            return 0
        meta = dict(getattr(locked, 'metadata', {}) or {})
        already = list(meta.get('recovery_drip_sent', []))

        for i in range(max_steps):
            delay = cfg['step_delays_minutes'][i]
            if i in already:
                continue
            if age_minutes < delay:
                continue
            if cfg['require_marketing_consent']:
                if consent_ok is None:
                    consent_ok = _has_marketing_consent(locked)
                if not consent_ok:
                    continue
            subject = _RECOVERY_SUBJECTS[i]
            send_templated_email(
                key=f'cart_recovery_{i + 1}',
                to=email,
                subject=subject,
                ctx={'cart': locked, 'cart_url': cart_url, 'unsubscribe_url': unsubscribe_url},
                headers=headers,
            )
            already.append(i)
            sent_now += 1

        if sent_now:
            meta['recovery_drip_sent'] = already
            locked.metadata = meta
            locked.save(update_fields=['metadata'])

    return sent_now
