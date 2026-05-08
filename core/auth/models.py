"""EmailOTP — a single-use 6-digit code bound to an email + expiry."""
from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone


class EmailOTP(models.Model):
    """One-time passcode issued to an email address.

    The plaintext `code` is never stored; only `code_hash` (SHA-256 hex
    over `code + email`). Verifying recomputes the hash and compares.

    Lifecycle:
      created  → expires_at      (10 min default; configurable)
      consumed → consumed_at     (set once; row stays for audit)

    A second `issue_otp(email)` call within the validity window
    invalidates the previous unconsumed code (sets `consumed_at` so
    nothing can verify against it). Keeps the inbox sane and the DB
    clear of stale rows.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    request_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', '-created_at']),
        ]

    def __str__(self) -> str:
        return f'OTP for {self.email} ({"used" if self.consumed_at else "live"})'

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at
