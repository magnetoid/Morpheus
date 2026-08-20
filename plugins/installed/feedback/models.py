"""Staff feedback tickets — a bug report with the evidence already attached.

The point of this model is that a report arrives with the context a developer
would otherwise have to ask for: what page, what browser, what the screen looked
like, and which JavaScript errors had already fired. `core.errors.ErrorEvent`
already ingests client errors via `/api/errors/client/`, so the ticket snapshots
the recent ones rather than starting a second pipeline.

Every evidence field is optional and every one records WHY it is missing:
screen capture needs the browser's own permission prompt and can be declined,
and a ticket that silently lost its screenshot looks identical to one where the
reporter chose not to share their screen.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class FeedbackTicket(models.Model):
    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_IN_PROGRESS, 'In progress'),
        (STATUS_CLOSED, 'Closed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # The reporter is kept on delete so a ticket outlives a staff account, but
    # the account itself is not blocked from deletion by an old bug report.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='feedback_tickets',
    )
    reporter_label = models.CharField(
        max_length=200,
        blank=True,
        help_text='Name/email captured at submit time, so the ticket still says who reported it after the account is gone.',
    )
    message = models.TextField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True
    )

    screenshot = models.ImageField(upload_to='feedback/%Y/%m/', blank=True, null=True)
    screenshot_skipped_reason = models.CharField(
        max_length=200,
        blank=True,
        help_text='Why no image: declined, unsupported, too_large, failed. Distinguishes "chose not to" from "we lost it".',
    )

    page_url = models.URLField(max_length=1000, blank=True)
    page_title = models.CharField(max_length=300, blank=True)
    viewport = models.CharField(max_length=40, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)

    client_errors = models.JSONField(
        default=list,
        blank=True,
        help_text='Recent JS errors from the browser at report time.',
    )
    context = models.JSONField(
        default=dict,
        blank=True,
        help_text='Version, request id, and recent server-side ErrorEvent rows.',
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'feedback ticket'

    def __str__(self) -> str:
        return f'{self.get_status_display()} — {self.message[:60]}'

    @property
    def summary(self) -> str:
        """First line of the message, for the list column."""
        first = (self.message or '').strip().splitlines()
        return first[0][:120] if first else '(no message)'
