"""Lightweight conversation log for the on-site AI stylist.

GDPR-friendly: stores a hash of the session + a 90-day rolling
window of messages. Merchants can wipe a session on request.
"""

from __future__ import annotations

import hashlib

from morpheus.plugin import models


def _hash_session(session_key: str) -> str:
    return hashlib.sha256((session_key or '').encode('utf-8')).hexdigest()


class StylistSession(models.Model):
    session_hash = models.CharField(max_length=64, unique=True, db_index=True)
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f'Stylist session {self.session_hash[:8]}'


class StylistTurn(models.Model):
    session = models.ForeignKey(
        StylistSession,
        on_delete=models.CASCADE,
        related_name='turns',
    )
    role = models.CharField(max_length=12)  # 'user' | 'assistant' | 'tool'
    content = models.TextField(blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['session', '-at'])]
