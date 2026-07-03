"""Assistant persistence models — DB-backed conversation history."""

# Pre-existing legacy models lack __str__ (DJ008); to_skill() uses lazy imports
# (PLC0415/I001) to avoid an agents↔assistant import cycle.
# ruff: noqa: DJ008, PLC0415, I001

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

    def cost_summary(self) -> dict:
        """Tokens + estimated USD cost for this conversation (dashboard display,
        not billing). Sums per-message tokens, priced by each message's model."""
        from django.db.models import Sum

        from core.agents.pricing import estimate_cost

        agg = self.messages.aggregate(p=Sum('prompt_tokens'), c=Sum('completion_tokens'))
        prompt = agg['p'] or 0
        completion = agg['c'] or 0
        cost = 0.0
        for row in (
            self.messages.exclude(model='')
            .values('model')
            .annotate(p=Sum('prompt_tokens'), c=Sum('completion_tokens'))
        ):
            cost += estimate_cost(row['model'], row['p'] or 0, row['c'] or 0)
        return {
            'prompt_tokens': prompt,
            'completion_tokens': completion,
            'total_tokens': prompt + completion,
            'cost_usd': round(cost, 4),
        }


class AssistantMessage(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
        ('tool', 'Tool'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        AssistantConversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField(blank=True)
    tool_name = models.CharField(max_length=200, blank=True)
    tool_args = models.JSONField(default=dict, blank=True)
    tool_output = models.JSONField(default=dict, blank=True)
    # Token accounting for cost display (set on the final assistant message).
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    model = models.CharField(max_length=100, blank=True)
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
        ('merchant', 'Merchant preference'),
        ('customer-segment', 'Customer segment'),
        ('seasonal', 'Seasonal / time-bound'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scope = models.CharField(
        max_length=24,
        choices=SCOPE_CHOICES,
        default='merchant',
        db_index=True,
    )
    key = models.CharField(max_length=160, db_index=True)
    value = models.TextField()
    source = models.CharField(
        max_length=40,
        blank=True,
        default='',
        help_text="Free-text source tag — 'user-told' / 'inferred' / etc.",
    )
    # Semantic vector of "key: value" (core.embeddings.embed). Enables
    # similarity recall beyond substring matching; empty until embedded
    # (write path + backfill_memory_embeddings). Recall falls back to keyword.
    embedding = models.JSONField(default=list, blank=True)
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


class LearnedSkill(models.Model):
    """A skill Linda authored from experience — a named bundle of EXISTING agent
    tools + a system-prompt prelude, persisted so it survives restarts and is
    registered into the ``skill_registry`` at boot. A skill grants NO new
    privilege: every tool still enforces its own scopes at call time. This is the
    self-learning loop's output (ADR 0011: one agent, grown via skills/tools).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.SlugField(max_length=120, unique=True, db_index=True)
    label = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    system_prompt_prelude = models.TextField(blank=True)
    tool_names = models.JSONField(default=list)  # names of registered tools it bundles
    examples = models.JSONField(default=list, blank=True)
    source = models.CharField(max_length=200, blank=True, default='distilled')
    enabled = models.BooleanField(default=True, db_index=True)
    version = models.PositiveIntegerField(default=1)
    # Outcome feedback (Phase 3 — skills self-improve / prune from use).
    uses = models.PositiveIntegerField(default=0)
    successes = models.PositiveIntegerField(default=0)
    failures = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        app_label = 'assistant'
        ordering = ['name']

    def __str__(self) -> str:
        return f'LearnedSkill({self.name})'

    def success_rate(self) -> float:
        return (self.successes / self.uses) if self.uses else 0.0

    def to_skill(self):
        """Build a runtime ``Skill`` from this row, resolving ``tool_names``
        against Linda's live tool catalog (unknown names are dropped — fail-soft)."""
        from core.agents.skills import Skill  # noqa: PLC0415
        from core.assistant.tools.skills import all_resolvable_tools  # noqa: PLC0415

        catalog = all_resolvable_tools()
        tools = tuple(catalog[n] for n in (self.tool_names or []) if n in catalog)
        return Skill(
            name=self.name,
            label=self.label,
            description=self.description,
            tools=tools,
            system_prompt_prelude=self.system_prompt_prelude,
        )


class AssistantBriefing(models.Model):
    """Linda's daily morning briefing — one row per day.

    Produced by ``core.assistant.briefing.run_daily_briefing`` (beat, 06:00
    UTC): a read-only Worker reviews the last 24h and returns a short
    narrative plus up to 3 delegable actions. Rendered on the dashboard home
    when Settings → General → *Linda's daily briefing* is on. Distinct from
    Linda's Pulse (rule-based alert cards in ai_assistant) — see
    docs/plans/linda-self-learning-2026-07.md.
    """

    STATUS_CHOICES = [
        ('ok', 'OK'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(unique=True, db_index=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='ok')
    body = models.TextField(blank=True)  # plain-text narrative (bullet lines)
    actions = models.JSONField(default=list, blank=True)  # [{label, prompt}]
    error = models.CharField(max_length=500, blank=True)
    provider = models.CharField(max_length=40, blank=True)
    model = models.CharField(max_length=100, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'assistant'
        ordering = ['-date']

    def __str__(self) -> str:
        return f'AssistantBriefing({self.date}/{self.status})'


class CodeProposal(models.Model):
    """A piece of code Linda DRAFTED for herself (uplift Phase 4 — self-written
    modules). It is statically scanned but NEVER executed and NEVER written to
    the repo by drafting — it sits as a proposal for human review. Turning a
    proposal into live code (file write + branch/PR) is a separate, gated,
    default-OFF step (requires MORPHEUS_SELF_UPDATE_ENABLED + a hard-gate).
    """

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('applied', 'Applied'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.SlugField(max_length=120, db_index=True)
    kind = models.CharField(max_length=20, default='tool')  # tool | skill | module
    rationale = models.TextField(blank=True)
    target_path = models.CharField(max_length=300, blank=True)  # informational only
    source = models.TextField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='draft', db_index=True)
    findings = models.JSONField(default=list, blank=True)  # static-scan results
    passed = models.BooleanField(default=False)  # no CRITICAL/HIGH findings
    consensus = models.JSONField(default=dict, blank=True)  # multi-model review (Phase 5)
    # Phase 4 apply (ADR 0014): owner approval is the binding human step; the
    # apply engine writes the source to a git branch (never main), gated.
    approver = models.CharField(max_length=200, blank=True)  # superuser email/username
    approved_at = models.DateTimeField(null=True, blank=True)
    applied_branch = models.CharField(max_length=200, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'assistant'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'CodeProposal({self.name}/{self.status})'

    def approve(self, user) -> None:
        """Owner approval — the binding human gate (ADR 0014). Only a superuser
        may approve; this records WHO and WHEN and flips status to 'approved'.
        Raises PermissionError otherwise (fail-closed)."""
        from django.utils import timezone

        if user is None or not getattr(user, 'is_superuser', False):
            raise PermissionError('only the owner (a superuser) may approve a code proposal')
        if self.status not in ('draft', 'approved'):
            raise ValueError(f'cannot approve a proposal in status {self.status!r}')
        self.approver = getattr(user, 'email', '') or getattr(user, 'username', '') or str(user.pk)
        self.approved_at = timezone.now()
        self.status = 'approved'
        self.save(update_fields=['approver', 'approved_at', 'status', 'updated_at'])

    def mark_applied(self, branch: str) -> None:
        from django.utils import timezone

        self.applied_branch = branch[:200]
        self.applied_at = timezone.now()
        self.status = 'applied'
        self.save(update_fields=['applied_branch', 'applied_at', 'status', 'updated_at'])
