"""Cart-abandonment models.

The recovery drip is consent-gated *marketing* email, so it must honour an
unsubscribe. Cart-recovery recipients are reached by email (guests included),
not by a newsletter subscription, so the opt-out is keyed on the address here —
a small suppression list the drip checks before every send. See
``services.py`` for the signed one-click token that writes these rows.
"""

from __future__ import annotations

from django.db import models


class RecoverySuppression(models.Model):
    """An email address that opted out of cart-recovery email (RFC 8058)."""

    email = models.EmailField(unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'recovery suppression'
        verbose_name_plural = 'recovery suppressions'

    def __str__(self) -> str:
        return self.email
