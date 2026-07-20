"""Agent run-state models — owned by the kernel (ADR 0034).

``AgentRun`` / ``AgentStep`` / ``AgentApprovalRequest`` moved here from
``plugins.installed.agent_core.models``: the runtime that creates and
persists this state (``core/agents/runtime.py``, ``core/assistant/tools/
spawn.py``) is permanently core per ADR 0029, so its state belongs to core
too — this closes the last core→plugin import in the boundary ratchet.

The DB tables are UNCHANGED (explicit ``db_table`` pins the original
``agent_core_*`` names); the move was state-only migrations on both sides
(``SeparateDatabaseAndState``, zero SQL). agent_core re-exports these
classes from its ``models.py`` for back-compat, and keeps its
conversation/memory/scheduler models (`AgentConversation`, `AgentMessage`,
`AgentMemoryRecord`, `BackgroundAgent`) — those are the *product surface*
of the plugin, not kernel run-state.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class AgentRun(models.Model):
    """One invocation of an agent."""

    STATE_CHOICES = [
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('awaiting_approval', 'Awaiting approval'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    AUDIENCE_CHOICES = [
        ('storefront', 'Storefront'),
        ('merchant', 'Merchant'),
        ('system', 'System'),
        ('any', 'Any'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent_name = models.CharField(max_length=100, db_index=True)
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default='merchant')

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agent_runs',
    )
    session_key = models.CharField(max_length=64, blank=True, db_index=True)

    user_message = models.TextField()
    final_text = models.TextField(blank=True)
    state = models.CharField(max_length=24, choices=STATE_CHOICES, default='queued', db_index=True)
    error = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    provider = models.CharField(max_length=50, blank=True)
    model = models.CharField(max_length=100, blank=True)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    tool_call_count = models.PositiveIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(default=0)

    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'core'
        # Original table — the move to core was state-only (ADR 0034).
        db_table = 'agent_core_agentrun'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['agent_name', '-started_at']),
            models.Index(fields=['customer', '-started_at']),
        ]

    def __str__(self) -> str:
        return f'AgentRun({self.agent_name}, {self.state})'

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def estimated_cost_usd(self) -> float:
        """Approximate USD cost of this run (dashboard display, not billing)."""
        from core.agents.pricing import estimate_cost

        return estimate_cost(self.model, self.prompt_tokens, self.completion_tokens)


class AgentStep(models.Model):
    """One step in a run's trace — mirror of `core.agents.trace.TraceStep`."""

    KIND_CHOICES = [
        ('system', 'System'),
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('tool_call', 'Tool call'),
        ('tool_result', 'Tool result'),
        ('final', 'Final answer'),
        ('error', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(AgentRun, on_delete=models.CASCADE, related_name='steps')
    seq = models.PositiveIntegerField()
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, db_index=True)
    name = models.CharField(max_length=200, blank=True, help_text='Tool name, when applicable')
    content = models.TextField(blank=True)
    arguments = models.JSONField(default=dict, blank=True)
    output = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        db_table = 'agent_core_agentstep'
        ordering = ['run', 'seq']
        indexes = [models.Index(fields=['run', 'seq'])]

    def __str__(self) -> str:
        return f'AgentStep({self.run_id}, #{self.seq}, {self.kind})'


class AgentApprovalRequest(models.Model):
    """Pending approval gate for a tool that requires human sign-off."""

    STATE_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(AgentRun, on_delete=models.CASCADE, related_name='approvals')
    tool_name = models.CharField(max_length=200)
    arguments = models.JSONField(default=dict)
    # Binds an approval to exactly one tool invocation (sha256 of name+args). A
    # grant approved for a benign call can't be spent on a different one.
    args_fingerprint = models.CharField(max_length=64, blank=True, db_index=True)
    # Single-use: set when the kernel spends this approval to run the tool.
    consumed_at = models.DateTimeField(null=True, blank=True)
    state = models.CharField(max_length=12, choices=STATE_CHOICES, default='pending', db_index=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'core'
        db_table = 'agent_core_agentapprovalrequest'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'AgentApprovalRequest({self.tool_name}, {self.state})'
