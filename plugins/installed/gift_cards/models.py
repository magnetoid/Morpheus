"""Gift card models — issue, balance, redeem."""
from __future__ import annotations

import secrets
import uuid

from django.conf import settings
from morpheus import models
from djmoney.models.fields import MoneyField


def _gen_code() -> str:
    """16-char A-Z2-9 (no easily-confused chars). Cheap to type, hard to guess."""
    alphabet = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    return ''.join(secrets.choice(alphabet) for _ in range(16))


class GiftCard(models.Model):
    """A purchased gift-card balance redeemable at checkout."""

    STATE_CHOICES = [
        ('active', 'Active'),
        ('disabled', 'Disabled'),
        ('expired', 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=24, unique=True, db_index=True, default=_gen_code)
    initial_value = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    balance = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    state = models.CharField(max_length=12, choices=STATE_CHOICES, default='active', db_index=True)

    issued_to_email = models.EmailField(blank=True)
    issued_to_customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True, related_name='gift_cards',
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True, related_name='issued_gift_cards',
    )
    note = models.CharField(max_length=240, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['state', '-created_at']),
        ]

    def __str__(self) -> str:
        return f'GiftCard {self.code} ({self.balance})'


class GiftCardLedger(models.Model):
    """Append-only record of every balance change on a card."""

    KIND_CHOICES = [
        ('issue', 'Issued'),
        ('redeem', 'Redeem'),
        ('refund', 'Refund'),
        ('adjust', 'Manual adjust'),
        ('expire', 'Expire'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    card = models.ForeignKey(GiftCard, on_delete=models.CASCADE, related_name='ledger')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    amount_change = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    balance_after = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    reference = models.CharField(max_length=100, blank=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['card', '-created_at']),
        ]
