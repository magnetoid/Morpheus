"""How long an unpaid order waits for a payment link (A8, v0.171.0).

The unpaid-order sweep (``orders.tasks.expire_pending_orders``) cancels a
``pending`` order nobody paid within ``pending_order_expiry_minutes``, which is
right for an abandoned card checkout and wrong for an order the customer pays
later from a link: a draft converted by staff, a payment link they emailed, or
the link sent after a declined card. Such an order carries
``metadata['pay_by']``, and the sweep leaves it alone until then.

``pay_by`` is an ISO datetime, or ``None`` for no deadline (the setting
``payment_link_hours`` at 0). An order without the key is an ordinary checkout.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from django.utils import timezone

logger = logging.getLogger('morpheus.orders')

KEY = 'pay_by'

#: Three days to open the email and pay, the orders setting's default.
DEFAULT_HOURS = 72


def link_hours() -> int:
    """The orders setting ``payment_link_hours``, read fresh; 0 = no deadline."""
    try:
        from plugins.registry import app_registry  # noqa: PLC0415

        plugin = app_registry.get('orders')
        return max(0, int(plugin.get_config_value('payment_link_hours', DEFAULT_HOURS)))
    except Exception:  # noqa: BLE001 — a config problem keeps the default
        return DEFAULT_HOURS


def hold_for_payment(order, *, reason: str) -> datetime | None:
    """Keep ``order`` out of the unpaid-order sweep until its deadline, and
    return the deadline (``None`` = none). ``reason`` is ``'draft'``, ``'link'``
    or ``'failed'``; an app may set its own deadline through the
    ``PAYMENT_LINK_DEADLINE`` filter. A later deadline is never shortened."""
    from core.hooks import MorpheusEvents, hook_registry  # noqa: PLC0415

    hours = link_hours()
    deadline = timezone.now() + timedelta(hours=hours) if hours else None
    try:
        answer = hook_registry.filter(
            MorpheusEvents.PAYMENT_LINK_DEADLINE, deadline, order=order, reason=reason
        )
    except Exception:  # noqa: BLE001 — a bad subscriber keeps the setting's deadline
        logger.warning('orders: PAYMENT_LINK_DEADLINE failed', exc_info=True)
        answer = deadline
    if answer is None or isinstance(answer, datetime):
        deadline = answer

    md = dict(order.metadata) if isinstance(order.metadata, dict) else {}
    if KEY in md:
        if md[KEY] is None:
            return None  # already open-ended
        current = _parse(md[KEY])
        if deadline is not None and current is not None and current >= deadline:
            return current  # already later
    md[KEY] = deadline.isoformat() if deadline is not None else None
    order.metadata = md
    if getattr(order, 'pk', None) is not None:
        order.save(update_fields=['metadata'])
    return deadline


def waiting_for_payment(order, now: datetime | None = None) -> bool:
    """Whether ``order`` is held for a payment link: it has ``pay_by`` and that
    is open-ended or still ahead."""
    return held(getattr(order, 'metadata', None), now)


def held(metadata, now: datetime | None = None) -> bool:
    """``waiting_for_payment`` for an order's metadata alone."""
    md = metadata if isinstance(metadata, dict) else {}
    if KEY not in md:
        return False
    if md.get(KEY) is None:
        return True
    deadline = _parse(md.get(KEY))
    if deadline is None:
        return False  # unreadable: the ordinary window applies
    return deadline > (now or timezone.now())


def cancels_at(order) -> datetime | None:
    """When the unpaid-order sweep will cancel ``order`` for want of payment, or
    None when it will not (no deadline, the sweep is off, or the order is not one
    it cancels). The only deadline a customer is told about."""
    from plugins.installed.orders.tasks import OFFLINE_GATEWAYS, _expiry_minutes  # noqa: PLC0415

    deadline = deadline_of(order)
    if deadline is None or _expiry_minutes() <= 0:
        return None
    if order.status != 'pending' or (order.payment_gateway or '') in OFFLINE_GATEWAYS:
        return None
    return deadline


def deadline_of(order) -> datetime | None:
    """The order's ``pay_by`` as a datetime, or None (none, open-ended or unreadable)."""
    md = order.metadata if isinstance(getattr(order, 'metadata', None), dict) else {}
    return _parse(md.get(KEY))


def _parse(raw) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        value = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if timezone.is_naive(value):
        value = value.replace(tzinfo=UTC)
    return value
