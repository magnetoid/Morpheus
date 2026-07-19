"""
agent_core models — persistent state for the kernel agent layer.

Three concerns:
* `AgentRun` records every invocation: which agent, who asked, what
  was requested, what came back, how long, what it cost.
* `AgentStep` is the audit-grade step log (system / user / tool_call /
  tool_result / final / error) — one row per `TraceStep` from the kernel.
* `AgentMessage` is the rolling conversation log for chat-style agents
  (Concierge, Merchant Ops). Distinct from `AgentStep`: messages span
  multiple runs, steps belong to one run.
* `AgentMemoryRecord` is the DB-backed semantic / episodic memory tier.
"""

from __future__ import annotations

import uuid

from django.conf import settings

from morpheus import models


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
        ordering = ['run', 'seq']
        indexes = [models.Index(fields=['run', 'seq'])]


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
        ordering = ['-created_at']
