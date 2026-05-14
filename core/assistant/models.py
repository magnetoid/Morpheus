"""Assistant persistence models — DB-backed conversation history."""
from __future__ import annotations

import uuid

from django.db import models


class AssistantConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=120, unique=True, db_index=True)
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ['-updated_at']


class AssistantMessage(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
        ('tool', 'Tool'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        AssistantConversation, on_delete=models.CASCADE, related_name='messages',
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField(blank=True)
    tool_name = models.CharField(max_length=200, blank=True)
    tool_args = models.JSONField(default=dict, blank=True)
    tool_output = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['conversation', 'created_at']


class LindaMemory(models.Model):
    """Cross-session memory for Linda. One row per remembered fact.

    Linda reads up to ~50 entries at the top of every turn (injected as
    a compact list into the system context) and writes via the
    `memory.remember` tool. Free-text key + value, scoped to keep
    seasonal/audience-specific notes from leaking across contexts.
    """
    SCOPE_CHOICES = [
        ('merchant',         'Merchant preference'),
        ('customer-segment', 'Customer segment'),
        ('seasonal',         'Seasonal / time-bound'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scope = models.CharField(
        max_length=24, choices=SCOPE_CHOICES, default='merchant', db_index=True,
    )
    key = models.CharField(max_length=160, db_index=True)
    value = models.TextField()
    source = models.CharField(
        max_length=40, blank=True, default='',
        help_text="Free-text source tag — 'user-told' / 'inferred' / etc.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ['-updated_at']
        unique_together = [('scope', 'key')]
        indexes = [models.Index(fields=['scope', '-updated_at'])]

    def __str__(self) -> str:
        return f'LindaMemory[{self.scope}.{self.key}]'

    def relevance_score(self, *, half_life_days: float = 60.0) -> float:
        """Exponential temporal decay weighted by source confidence.

        Half-life of 60 days means a fact decays to half its initial
        relevance after two months — long enough that "user told me last
        month" stays sticky, short enough that "I inferred this Tuesday"
        loses weight by autumn.

        Confidence cheat-sheet (no migration needed; derived from
        ``source``):
          - 'user-told' / 'merchant-told'  → 1.0  (high signal)
          - 'inferred' / 'auto'            → 0.6  (model-derived)
          - anything else                  → 0.8  (neutral)
        """
        import math
        from django.utils import timezone
        src = (self.source or '').lower()
        if 'told' in src:
            confidence = 1.0
        elif src in ('inferred', 'auto', 'auto-inferred'):
            confidence = 0.6
        else:
            confidence = 0.8
        age_days = (timezone.now() - self.updated_at).total_seconds() / 86400.0
        return confidence * math.exp(-age_days / max(half_life_days, 1.0))
