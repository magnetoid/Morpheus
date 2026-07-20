"""
agent_core models — the plugin's product surface for the agent layer.

* `AgentMessage` is the rolling conversation log for chat-style agents.
  Distinct from `AgentStep`: messages span multiple runs, steps belong
  to one run.
* `AgentMemoryRecord` is the DB-backed semantic / episodic memory tier.
* `BackgroundAgent` is the autonomous-schedule registry.

The kernel *run-state* models — `AgentRun`, `AgentStep`,
`AgentApprovalRequest` — moved to ``core/agents/models.py`` (ADR 0034:
the runtime that persists them is permanently core per ADR 0029, and this
closed the last core→plugin import). Tables are unchanged
(``agent_core_*`` via explicit ``db_table``); they are re-exported below
so every existing ``plugins.installed.agent_core.models`` import keeps
working (plugin→core is the allowed direction).
"""

from __future__ import annotations

import uuid

from django.conf import settings

# Moved to core (ADR 0034) — re-exported for back-compat; plugin→core is the
# allowed import direction.
from core.agents.models import (  # noqa: F401
    AgentApprovalRequest,
    AgentRun,
    AgentStep,
)
from morpheus import models


class AgentConversation(models.Model):
    """A persistent chat thread between a user (or session) and an agent."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent_name = models.CharField(max_length=100, db_index=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agent_conversations',
    )
    session_key = models.CharField(max_length=64, blank=True, db_index=True)
    title = models.CharField(max_length=200, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ['-last_message_at']
        indexes = [
            models.Index(fields=['agent_name', '-last_message_at']),
            models.Index(fields=['customer', '-last_message_at']),
            models.Index(fields=['session_key', '-last_message_at']),
        ]


class AgentMessage(models.Model):
    """One message in a conversation thread."""

    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        AgentConversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    run = models.ForeignKey(
        AgentRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages',
    )
    role = models.CharField(max_length=12, choices=ROLE_CHOICES)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['conversation', 'created_at']


class AgentMemoryRecord(models.Model):
    """DB-backed memory tier (semantic + episodic)."""

    TIER_CHOICES = [
        ('episodic', 'Episodic'),
        ('semantic', 'Semantic'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, db_index=True)
    namespace = models.CharField(max_length=200, db_index=True)
    key = models.CharField(max_length=200)
    value = models.JSONField(default=dict)
    confidence = models.FloatField(default=1.0)
    source = models.CharField(max_length=50, default='agent')
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tier', 'namespace', 'key')
        indexes = [
            models.Index(fields=['tier', 'namespace']),
        ]


class BackgroundAgent(models.Model):
    """A registered agent that runs autonomously on a schedule.

    The scheduler tick (every minute) finds all active rows whose
    `next_run_at` <= now, dispatches a run, and computes the next slot.
    """

    STATE_ACTIVE = 'active'
    STATE_PAUSED = 'paused'
    STATE_ERROR = 'error'
    STATE_CHOICES = [
        (STATE_ACTIVE, 'Active'),
        (STATE_PAUSED, 'Paused'),
        (STATE_ERROR, 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, help_text='Human label for this background job.')
    agent_name = models.CharField(
        max_length=100, db_index=True, help_text='Slug of the registered agent to run.'
    )
    prompt = models.TextField(help_text='User-message text passed to the agent on each tick.')
    context_overrides = models.JSONField(default=dict, blank=True)

    interval_seconds = models.PositiveIntegerField(default=3600)
    state = models.CharField(
        max_length=12, choices=STATE_CHOICES, default=STATE_ACTIVE, db_index=True
    )

    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_run_id = models.CharField(max_length=64, blank=True)
    last_error = models.TextField(blank=True)

    consecutive_failures = models.PositiveIntegerField(default=0)
    max_failures_before_pause = models.PositiveIntegerField(default=5)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='background_agents',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['state', 'next_run_at']),
        ]

    def __str__(self) -> str:
        return f'{self.name} → {self.agent_name}'
