"""Post-purchase journey models.

Two tables — a step ledger (one row per touchpoint per order) and an
NPS feedback collection table. The step ledger acts as both the audit
trail ("did we send the review-request email?") and the dedup key
(don't send it twice).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

STEP_CHOICES = (
    ('tracking_sent', 'Tracking email sent'),
    ('delivered_followup', 'Delivered-confirmation follow-up'),
    ('review_request', 'Review request'),
    ('nps_survey', 'NPS survey'),
)

STATUS_CHOICES = (
    ('queued', 'Queued'),
    ('sent', 'Sent'),
    ('skipped', 'Skipped'),
    ('failed', 'Failed'),
)


class JourneyStep(models.Model):
    """One row per (order, step) — audit trail + dedup key.

    The `due_at` timestamp gates when the scheduled task is allowed to
    fire. Until that time the row sits in `queued`; after that the task
    transitions it to `sent` (or `skipped`/`failed`).
    """

    order = models.ForeignKey(
        'orders.Order', on_delete=models.CASCADE, related_name='journey_steps'
    )
    step = models.CharField(max_length=32, choices=STEP_CHOICES, db_index=True)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default='queued', db_index=True
    )
    due_at = models.DateTimeField(db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'post_purchase_step'
        verbose_name = 'Journey step'
        constraints = [
            models.UniqueConstraint(
                fields=['order', 'step'], name='post_purchase_unique_order_step'
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'due_at'], name='pp_status_due_idx'),
        ]
        ordering = ['-due_at']

    def __str__(self) -> str:
        return f'{self.order_id}:{self.step}={self.status}'


class NPSResponse(models.Model):
    """NPS feedback collected via the public /nps/<token>/ page.

    Token is a short-lived signed URL emitted with the survey email;
    one response per order. We keep responses anonymous-by-default
    (customer FK is set only if they were logged in when responding).
    """

    order = models.ForeignKey(
        'orders.Order', on_delete=models.CASCADE, related_name='nps_responses'
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    score = models.SmallIntegerField(help_text='0-10')
    comment = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'post_purchase_nps'
        verbose_name = 'NPS response'
        constraints = [
            models.UniqueConstraint(fields=['order'], name='pp_nps_unique_order'),
            models.CheckConstraint(
                condition=models.Q(score__gte=0) & models.Q(score__lte=10),
                name='pp_nps_score_range',
            ),
        ]
        ordering = ['-submitted_at']

    def __str__(self) -> str:
        return f'NPS {self.score} on order {self.order_id}'

    @property
    def bucket(self) -> str:
        if self.score >= 9:
            return 'promoter'
        if self.score >= 7:
            return 'passive'
        return 'detractor'
