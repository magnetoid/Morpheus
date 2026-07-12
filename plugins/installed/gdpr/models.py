"""GDPR Data Subject Request (DSR) audit trail.

GDPR Art. 12(3) obliges the controller to act on access (Art. 15) and
erasure (Art. 17) requests and to be able to *demonstrate* it did so.
One ``DataRequest`` row per self-service export/erasure gives us that
proof — who asked, for what, when it completed — without duplicating
consent's ``ConsentLog`` (that records banner decisions; this records
rights exercised).

The actual export/erasure work is delegated to
``customers.services.gather_customer_data`` / ``anonymise_customer`` —
this model only records that it happened.
"""

from __future__ import annotations

import secrets
import uuid

from django.db import models


class DataRequest(models.Model):
    KIND_CHOICES = [
        ('export', 'Data export (Art. 15)'),
        ('erasure', 'Erasure / delete (Art. 17)'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, db_index=True)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True
    )
    # SET_NULL: an erasure anonymises + deactivates the Customer, but the
    # audit row must survive to prove the request was honoured.
    customer = models.ForeignKey(
        'customers.Customer',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='data_requests',
    )
    # Denormalised so the row is still meaningful after the customer FK
    # goes null (post-erasure) — stored lowercased.
    email = models.EmailField(blank=True)
    # Single-use token for a future guest (unauthenticated) confirmation
    # flow; unused by the logged-in self-service path.
    token = models.CharField(max_length=64, default='', blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Data subject request'
        verbose_name_plural = 'Data subject requests'
        ordering = ('-created_at',)

    def __str__(self) -> str:  # pragma: no cover — debug only
        return f'DataRequest<{self.kind} {self.status} {self.email or self.customer_id}>'

    @staticmethod
    def new_token() -> str:
        return secrets.token_urlsafe(32)
