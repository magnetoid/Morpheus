"""Async delivery for transactional emails.

Rendering (fast, no I/O) stays in the request; the SMTP round-trip — the slow,
failure-prone part — is deferred to this task, enqueued on transaction commit.
That keeps a slow/dead mail host from holding the order-placement transaction
(and the HTTP request) open, and gives the send real retries instead of the old
``fail_silently=True`` swallow. Under tests (``CELERY_TASK_ALWAYS_EAGER``) it runs
inline, so nothing about email behaviour changes there.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.core.mail import EmailMultiAlternatives

from core.log_formatters import redact_email

logger = logging.getLogger('morpheus.emails')


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
    acks_late=True,
)
def deliver_email(self, *, subject, text_body, html_body, from_email, to, headers=None, tag=''):
    """Send one pre-rendered email. Retries on transient SMTP failure.

    ``headers`` (optional dict) is passed straight to
    ``EmailMultiAlternatives`` — marketing sends use it for the RFC 8058
    one-click-unsubscribe pair (``List-Unsubscribe`` +
    ``List-Unsubscribe-Post``), which Gmail/Yahoo require of bulk senders.

    ``tag`` (optional): the sender's own name for this message. Once it is sent,
    EMAIL_DELIVERED fires with it, so a sender records a delivery only when one
    happened (returns_portal's withdrawal acknowledgement).
    """
    msg = EmailMultiAlternatives(subject, text_body, from_email, [to], headers=headers or None)
    if html_body:
        msg.attach_alternative(html_body, 'text/html')
    try:
        msg.send(fail_silently=False)
    except Exception as e:  # re-raised for autoretry after logging
        logger.warning(
            'emails: delivery for %s failed (attempt %s): %s',
            redact_email(to),
            self.request.retries,
            e,
        )
        raise
    if tag:
        _announce(tag)


def _announce(tag: str) -> None:
    """EMAIL_DELIVERED for a tagged message just sent. A subscriber's failure is
    logged, never raised: raising would retry the task and send the email again."""
    from core.email import real_transport  # noqa: PLC0415
    from core.hooks import MorpheusEvents, hook_registry  # noqa: PLC0415

    try:
        hook_registry.fire(MorpheusEvents.EMAIL_DELIVERED, tag=tag, reached_inbox=real_transport())
    except Exception as e:  # noqa: BLE001 — the email is sent; only the record is missing
        logger.error('emails: EMAIL_DELIVERED for %s failed: %s', tag, e)
