"""Celery tasks for the post-purchase journey.

The scheduled task `process_due_steps` runs every 15 minutes; it picks
up JourneyStep rows whose `due_at` has passed and dispatches the
appropriate email / action per step. Each step transitions exactly
once — the unique constraint on (order, step) is the dedup boundary,
and the row's status moves queued → sent | skipped | failed.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.core.signing import TimestampSigner
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger('morpheus.post_purchase.tasks')

BATCH_SIZE = 100


@shared_task(name='post_purchase.process_due_steps')
def process_due_steps() -> dict:
    """Pick up every JourneyStep where due_at <= now and dispatch."""
    from plugins.installed.post_purchase.models import JourneyStep  # noqa: PLC0415

    now = timezone.now()
    qs = JourneyStep.objects.filter(status='queued', due_at__lte=now).select_related('order')[
        :BATCH_SIZE
    ]

    dispatched = {'sent': 0, 'skipped': 0, 'failed': 0}
    for step in qs:
        try:
            outcome = _dispatch_step(step)
        except Exception as exc:  # noqa: BLE001 — never break the batch on one failure
            logger.exception('post_purchase: step dispatch raised for %s', step.pk)
            step.status = 'failed'
            step.error = str(exc)[:1024]
            step.save(update_fields=['status', 'error', 'updated_at'])
            dispatched['failed'] += 1
            continue
        step.status = outcome
        if outcome == 'sent':
            step.sent_at = timezone.now()
        step.save(update_fields=['status', 'sent_at', 'updated_at'])
        dispatched[outcome] = dispatched.get(outcome, 0) + 1
    return dispatched


def _dispatch_step(step) -> str:
    """Return 'sent' | 'skipped' on success, raise on failure."""
    if step.step == 'tracking_sent':
        return _send_tracking(step)
    if step.step == 'delivered_followup':
        return _send_delivered_followup(step)
    if step.step == 'review_request':
        return _send_review_request(step)
    if step.step == 'nps_survey':
        return _send_nps_survey(step)
    return 'skipped'


# ---------------------------------------------------------------------------
# Per-step senders. Phase 1 wires the audit + queue layer; the actual
# email templates live in the existing notifications plugin and reuse
# the order-confirmation transport.
# ---------------------------------------------------------------------------


def _send_tracking(step) -> str:
    order = step.order
    tracking_number = (
        (order.metadata or {}).get('tracking_number') if hasattr(order, 'metadata') else None
    )
    if not tracking_number:
        # Skip until tracking number is available; a later run will catch it.
        return 'skipped'
    _send_email(
        order=order,
        subject=f'Your order #{order.order_number} is on its way',
        body=(
            f'Hi,\n\nYour order #{order.order_number} has shipped. '
            f'Tracking number: {tracking_number}.\n'
        ),
        kind='tracking_sent',
    )
    return 'sent'


def _send_delivered_followup(step) -> str:
    order = step.order
    _send_email(
        order=order,
        subject=f'Did order #{order.order_number} arrive safely?',
        body=(
            f'Hi,\n\nWe hope order #{order.order_number} arrived as expected. '
            f"If anything is off, just reply to this email and we'll make it right.\n"
        ),
        kind='delivered_followup',
    )
    return 'sent'


def _send_review_request(step) -> str:
    order = step.order
    _send_email(
        order=order,
        subject=f'How was order #{order.order_number}?',
        body=(
            f"Hi,\n\nWe'd love your honest review of order #{order.order_number}. "
            f'A few words help future customers make better choices.\n'
        ),
        kind='review_request',
    )
    return 'sent'


def _send_nps_survey(step) -> str:
    order = step.order
    token = _nps_token(order)
    nps_path = reverse('post_purchase:nps_form', kwargs={'token': token})
    nps_url = f'{_site_url()}{nps_path}'
    _send_email(
        order=order,
        subject='Quick 30-second survey?',
        body=(
            f'Hi,\n\nOn a scale of 0-10, how likely are you to recommend our shop '
            f'to a friend or colleague?\n\n{nps_url}\n\nOne click. No login required.\n'
        ),
        kind='nps_survey',
    )
    return 'sent'


# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------


def _send_email(*, order, subject: str, body: str, kind: str) -> None:
    """Thin shim over Django's send_mail. The notifications plugin can
    later override `post_purchase.notify` via a hook if shops want
    branded HTML templates.
    """
    from django.core.mail import send_mail  # noqa: PLC0415

    recipient = getattr(order, 'customer_email', None) or getattr(
        getattr(order, 'customer', None), 'email', None
    )
    if not recipient:
        logger.warning('post_purchase: no recipient on order %s; skipping %s', order.pk, kind)
        return
    send_mail(
        subject=subject,
        message=body,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'shop@localhost'),
        recipient_list=[recipient],
        fail_silently=False,
    )


def _nps_token(order) -> str:
    return TimestampSigner(salt='post_purchase.nps').sign(str(order.pk))


def _site_url() -> str:
    base = getattr(settings, 'SITE_URL', '')
    if base:
        return base.rstrip('/')
    hosts = getattr(settings, 'ALLOWED_HOSTS', ['localhost']) or ['localhost']
    return f'https://{hosts[0].lstrip(".")}'
