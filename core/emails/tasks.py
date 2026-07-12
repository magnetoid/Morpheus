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
def deliver_email(self, *, subject, text_body, html_body, from_email, to):
    """Send one pre-rendered transactional email. Retries on transient SMTP failure."""
    msg = EmailMultiAlternatives(subject, text_body, from_email, [to])
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
