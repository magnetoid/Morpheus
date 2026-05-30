"""Consent audit log.

GDPR Art. 7(1): the controller must be able to *demonstrate* that the
data subject has consented. A row per decision gives us the audit trail
required for that — including the IP hash + user agent for legal-hold
purposes, without storing the raw IP (data-minimization).
"""

from __future__ import annotations

import uuid

from django.db import models


class ConsentLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        'customers.Customer',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='consent_logs',
    )
    session_key = models.CharField(max_length=40, db_index=True)
    necessary = models.BooleanField(default=True)
    analytics = models.BooleanField(default=False)
    marketing = models.BooleanField(default=False)
    functional = models.BooleanField(default=False)
    # SHA-256 of the IP — keeps the proof-of-decision link without
    # storing PII at rest.
    ip_hash = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Consent log entry'
        verbose_name_plural = 'Consent log entries'
        ordering = ('-created_at',)

    def __str__(self) -> str:  # pragma: no cover — debug only
        flags = ''.join(
            [
                'N' if self.necessary else '-',
                'A' if self.analytics else '-',
                'M' if self.marketing else '-',
                'F' if self.functional else '-',
            ]
        )
        return f'ConsentLog<{flags} @ {self.created_at:%Y-%m-%d %H:%M}>'
