"""Celery tasks for the post-purchase journey.

The scheduled task `process_due_steps` runs every 15 minutes; it picks
up JourneyStep rows whose `due_at` has passed and dispatches the
appropriate email / action per step. Each step transitions exactly
once — the unique constraint on (order, step) is the dedup boundary,
and the row's status moves queued → sent | skipped | failed.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.core.signing import TimestampSigner
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger('morpheus.post_purchase.tasks')

BATCH_SIZE = 100


@shared_task(name='post_purchase.process_due_steps')
def process_due_steps() -> dict:
    """Pick up every JourneyStep where due_at <= now and dispatch."""
    from plugins.installed.post_purchase.handlers import _config  # noqa: PLC0415
    from plugins.installed.post_purchase.models import JourneyStep  # noqa: PLC0415
    from plugins.registry import app_registry  # noqa: PLC0415

    dispatched = {'sending': 0, 'skipped': 0, 'failed': 0}
    if not app_registry.is_active('post_purchase'):
        return dispatched  # the beat entry outlives a switch-off
    cfg = _config()
    now = timezone.now()
    _skip_in_bulk(cfg, now)
    _retry_stuck(now)
    qs = JourneyStep.objects.filter(status='queued', due_at__lte=now).order_by('due_at')[
        :BATCH_SIZE
    ]

    for pk in qs.values_list('pk', flat=True):
        # Claimed under a row lock, so two overlapping runs never send one step
        # twice; the email itself is enqueued when this commits.
        with transaction.atomic():
            step = (
                JourneyStep.objects.select_for_update(skip_locked=True, of=('self',))
                .select_related('order')
                .filter(pk=pk, status='queued')
                .first()
            )
            if step is None:
                continue
            try:
                with transaction.atomic():
                    outcome = _dispatch_step(step, cfg)
            except Exception as exc:  # noqa: BLE001 — never break the batch on one failure
                logger.exception('post_purchase: step dispatch raised for %s', step.pk)
                outcome = 'failed'
                step.error = str(exc)[:1024]
            if outcome != 'sending':  # a send saved its own row before enqueueing
                step.status = outcome
                step.save(update_fields=['status', 'error', 'updated_at'])
        dispatched[outcome] = dispatched.get(outcome, 0) + 1
    return dispatched


#: A step this far past its due time is skipped, never sent: switching a step on
#: must not mail every order the store queued while it was off (or before C1, when
#: nothing sent them at all).
MAX_LATE = timedelta(days=3)

#: The steps that are marketing: consent-gated, with a one-click unsubscribe.
MARKETING = frozenset({'review_request', 'nps_survey'})

_SETTING = {
    'delivered_followup': 'delivered_followup_enabled',
    'review_request': 'review_request_enabled',
    'nps_survey': 'nps_survey_enabled',
}


#: A step handed to the mail queue that has heard nothing back for this long was
#: lost (the broker refused it, or its retries ran out): it is queued once more,
#: then failed. The mail task retries for about 20 minutes.
STUCK_AFTER = timedelta(hours=1)
MAX_ATTEMPTS = 2


def _retry_stuck(now) -> None:
    from plugins.installed.post_purchase.models import JourneyStep  # noqa: PLC0415

    for step in JourneyStep.objects.filter(status='sending', updated_at__lt=now - STUCK_AFTER):
        if int((step.payload or {}).get('attempts', 0)) < MAX_ATTEMPTS:
            step.status = 'queued'
        else:
            step.status, step.error = 'failed', 'not delivered'
        step.save(update_fields=['status', 'error', 'updated_at'])


def on_email_delivered(tag='', reached_inbox=False, **kwargs) -> None:
    """EMAIL_DELIVERED: a step's email went out, so the step is ``sent``. On a store
    with no sending email it was printed to the log, which reached nobody."""
    from plugins.installed.post_purchase.models import JourneyStep  # noqa: PLC0415

    if not str(tag).startswith(_TAG):
        return
    rows = JourneyStep.objects.filter(pk=str(tag)[len(_TAG) :], status='sending')
    if reached_inbox:
        rows.update(status='sent', sent_at=timezone.now(), error='', updated_at=timezone.now())
    else:
        rows.update(status='failed', error='no sending email', updated_at=timezone.now())


_TAG = 'journey:'


def _skip_in_bulk(cfg: dict, now) -> None:
    """Skip, in two updates, every due step that could never be sent: too late,
    switched off, or not this app's to send. A store's old backlog (months of
    orders queued while nothing sent them) otherwise filled each batch, and a
    step coming due waited behind it until it was late too."""
    from plugins.installed.post_purchase.models import JourneyStep  # noqa: PLC0415

    due = JourneyStep.objects.filter(status='queued', due_at__lte=now)
    due.filter(due_at__lt=now - MAX_LATE).update(status='skipped', error='late', updated_at=now)
    sendable = [step for step, key in _SETTING.items() if cfg.get(key)]
    due.exclude(step__in=sendable).update(status='skipped', error='switched off', updated_at=now)


def _skip_reason(step, cfg: dict) -> str:
    """Why ``step`` is not sent, or '' when it may go."""
    order = step.order
    if step.step not in _SETTING:
        return 'not sent by this app'  # tracking: core's shipping email carries it
    if not cfg.get(_SETTING[step.step]):
        return 'switched off'
    if step.due_at < timezone.now() - MAX_LATE:
        return 'late'
    reason = _order_reason(order)
    if reason:
        return reason
    return _marketing_reason(step) if step.step in MARKETING else ''


def _order_reason(order) -> str:
    if order.status in ('cancelled', 'refunded') or order.payment_status == 'refunded':
        return 'order cancelled'
    if (order.metadata or {}).get('exchange_of'):
        return 'exchange order'  # the order it replaces had its own journey
    if not _recipient(order):
        return 'no email address'
    return ''


def _marketing_reason(step) -> str:
    """A marketing step goes only with the order's consent, and never to an
    address that unsubscribed."""
    from core.consent import allowed  # noqa: PLC0415
    from plugins.installed.post_purchase.unsubscribe import opted_out  # noqa: PLC0415

    if not allowed('marketing', order=step.order):
        return 'no consent'
    if opted_out(_recipient(step.order)):
        return 'opted out'
    return ''


def _dispatch_step(step, cfg: dict | None = None) -> str:
    """Hand ``step``'s email over: 'sending', or 'skipped' with the reason in ``step.error``."""
    from plugins.installed.post_purchase.handlers import _config  # noqa: PLC0415

    reason = _skip_reason(step, cfg if cfg is not None else _config())
    if reason:
        step.error = reason
        return 'skipped'
    # Recorded before the email is handed over: EMAIL_DELIVERED (inline in tests,
    # later on a worker) moves it to 'sent', and a lost one is retried.
    step.status, step.error = 'sending', ''
    step.payload = {
        **(step.payload or {}),
        'attempts': int((step.payload or {}).get('attempts', 0)) + 1,
    }
    step.save(update_fields=['status', 'error', 'payload', 'updated_at'])
    _SENDERS[step.step](step)
    return 'sending'


def _recipient(order) -> str:
    return (getattr(order, 'email', '') or '').strip() or (
        getattr(getattr(order, 'customer', None), 'email', '') or ''
    ).strip()


def _tagged(url: str, step: str) -> str:
    """``url`` with the campaign tags the Attribution report counts visits and
    orders by (no open pixel: an open says nothing)."""
    sep = '&' if '?' in url else '?'
    return f'{url}{sep}utm_source=post_purchase&utm_medium=email&utm_campaign={step}'


def _send(step, key: str, subject: str, **extra) -> None:
    from core.emails.handlers import send_templated_email  # noqa: PLC0415
    from core.utils.site import site_base_url, store_name  # noqa: PLC0415

    order = step.order
    to = _recipient(order)
    ctx = {
        'order': order,
        'store_name': store_name(),
        'shop_url': _tagged(f'{site_base_url().rstrip("/")}/', step.step),
        **extra,
    }
    headers = None
    if step.step in MARKETING:
        from plugins.installed.post_purchase import unsubscribe  # noqa: PLC0415

        ctx['unsubscribe_url'] = unsubscribe.unsubscribe_url(to)
        headers = unsubscribe.headers(to)
    send_templated_email(
        key, to=to, subject=subject, ctx=ctx, headers=headers, tag=f'{_TAG}{step.pk}'
    )


def _send_delivered_followup(step) -> None:
    order = step.order
    _send(
        step,
        'post_purchase_delivered',
        f'Did order #{order.order_number} arrive safely?',
    )


def _review_lines(order) -> list[dict]:
    """``[{'name', 'url'}]``: each product's review form, tagged. Empty while the
    reviews app is off (its route is not mounted)."""
    from core.utils.site import site_base_url  # noqa: PLC0415

    base = site_base_url().rstrip('/')
    lines, seen = [], set()
    for item in order.items.select_related('product'):
        pid = getattr(item, 'product_id', None)
        if not pid or pid in seen:
            continue
        try:
            url = base + reverse('reviews:add', kwargs={'product_id': pid})
        except Exception:  # noqa: BLE001, S112 — reviews off: no route, no line
            continue
        seen.add(pid)
        name = item.product_name or getattr(item.product, 'name', '') or 'your item'
        lines.append({'name': name, 'url': _tagged(url, 'review_request')})
    return lines


def _review_links(order) -> str:
    """One 'name — url' line per product (the plain-text form of the links)."""
    return '\n'.join(f'• {line["name"]} — {line["url"]}' for line in _review_lines(order))


def _send_review_request(step) -> None:
    order = step.order
    _send(
        step,
        'post_purchase_review',
        f'How was order #{order.order_number}?',
        review_lines=_review_lines(order),
    )


def _send_nps_survey(step) -> None:
    from core.utils.site import site_base_url  # noqa: PLC0415

    order = step.order
    path = reverse('post_purchase:nps_form', kwargs={'token': _nps_token(order)})
    _send(
        step,
        'post_purchase_nps',
        'Quick 30-second survey?',
        nps_url=_tagged(f'{site_base_url().rstrip("/")}{path}', 'nps_survey'),
    )


_SENDERS = {
    'delivered_followup': _send_delivered_followup,
    'review_request': _send_review_request,
    'nps_survey': _send_nps_survey,
}


def _nps_token(order) -> str:
    return TimestampSigner(salt='post_purchase.nps').sign(str(order.pk))
