"""Assistant persistence models — DB-backed conversation history."""

# Pre-existing legacy models lack __str__ (DJ008); to_skill() uses lazy imports
# (PLC0415/I001) to avoid an agents↔assistant import cycle.
# ruff: noqa: DJ008, PLC0415, I001

from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models


class AssistantConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=120, unique=True, db_index=True)
    title = models.CharField(max_length=200, blank=True)
    # The staff member whose chat this is — every read and write of a chat is
    # checked against it. Rows from before chats (the one `user:<pk>` thread)
    # are backfilled by migration 0015; other keys stay unowned.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='linda_chats',
    )
    archived = models.BooleanField(default=False, db_index=True)
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


class JanusLearning(models.Model):
    """One file of what Janus, Linda's engine, has learned.

    Janus keeps what it learns as files in its home directory, and a home is a
    temp dir that every redeploy wipes. These rows are the durable copy, so the
    learning survives on any host without a disk volume. The sync logic lives in
    ``core/assistant/janus_learning.py``.
    """

    KIND_CHOICES = [
        ('memory', 'Memory notes'),
        ('journal', 'Memory journal'),
        ('skill', 'Skill file'),
        ('lesson', 'Lessons'),
    ]

    # '' is the whole store; 'user:<pk>' is one staff member (only USER.md, what
    # Janus knows about the person it is talking to).
    scope = models.CharField(max_length=64, blank=True, default='', db_index=True)
    # Relative to the Janus home, e.g. 'memories/MEMORY.md'.
    path = models.CharField(max_length=255)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, db_index=True)
    content = models.TextField()
    # The conversation whose turn last wrote this file.
    conversation_key = models.CharField(max_length=120, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'assistant'
        ordering = ['scope', 'path']
        constraints = [
            models.UniqueConstraint(
                fields=['scope', 'path'], name='assistant_janus_learning_scope_path'
            )
        ]

    def __str__(self) -> str:
        return f'JanusLearning({self.scope or "store"}:{self.path})'


class CodeProposal(models.Model):
    """RETIRED in v0.65.0 — nothing reads or writes this model any more.

    Linda's self-coding loop (draft → scan → consensus → apply to a branch) was
    removed when Janus replaced her in-process engine. The model stays only so its
    table and history survive: deleting it generates a migration that drops the
    table on the next deploy, which is a data-loss decision for the owner, not a
    side effect of a cleanup. Drop it deliberately in its own change.
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


class OpsProposal(models.Model):
    """A staged *business-level* change (price edit, SEO meta fill, …) awaiting
    merchant approval — the generic propose→preview→approve→apply artifact
    (staged-changes design 2026-07-05, generalizing ADR-0028's propose-only
    queue). Distinct from CodeProposal (self-written code) and
    SiRecommendation (code-quality findings): OpsProposal stages *data*
    changes, described field-by-field in ``changes`` and applied via
    ContentType resolution so core never imports plugin models.
    """

    STATUS_CHOICES = [
        ('proposed', 'Proposed'),
        ('approved', 'Approved'),
        ('applied', 'Applied'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(
        max_length=80, db_index=True
    )  # 'routine:<name>' | 'skill:<name>' | 'chat'
    # AgentRun lives in core since ADR 0034 (same table; string ref avoids an
    # import cycle at load).
    agent_run = models.ForeignKey(
        'core.AgentRun',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='ops_proposals',
    )
    kind = models.CharField(max_length=40, db_index=True)  # 'product.update' | 'seo.meta' | …
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)  # the agent's rationale
    # GenericFK to the object being changed (nullable for multi-object proposals).
    target_ct = models.ForeignKey(
        'contenttypes.ContentType',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    target_id = models.CharField(max_length=64, blank=True)  # str so UUID and int pks both fit
    target = GenericForeignKey('target_ct', 'target_id')
    changes = models.JSONField(
        default=list, blank=True
    )  # [{object: '<app>.<model>:<pk>', field, old, new}]
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='proposed', db_index=True
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_ops_proposals',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    apply_error = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)  # stale proposals auto-expire
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'assistant'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'OpsProposal({self.kind}/{self.status})'

    def approve(self, user) -> bool:
        """Staff approval — fail-closed (mirrors CodeProposal.approve, but staff
        suffices: ops proposals run through class-allowlisted data rails, they
        don't land code). Returns True on approve; False if the proposal had
        expired (status flips to 'expired'). Raises PermissionError for
        non-staff and ValueError for a non-'proposed' status.
        """
        from django.utils import timezone

        if user is None or not getattr(user, 'is_staff', False):
            raise PermissionError('only staff may approve an ops proposal')
        if self.status != 'proposed':
            raise ValueError(f'cannot approve an ops proposal in status {self.status!r}')
        now = timezone.now()
        if self.expires_at is not None and self.expires_at < now:
            self.status = 'expired'
            self.save(update_fields=['status', 'updated_at'])
            return False
        self.approved_by = user
        self.approved_at = now
        self.status = 'approved'
        self.save(update_fields=['approved_by', 'approved_at', 'status', 'updated_at'])
        return True

    def apply(self, user=None) -> dict:
        """Apply each staged change, fail-soft per change. Never raises.

        Per change: resolve ``object`` ('<app_label>.<model>:<pk>') via
        ContentType; skip + report rows whose live value drifted from ``old``;
        otherwise set the field, save, and record a core.audit entry. Status
        flips to 'applied' if ANYTHING applied (partial success), 'failed' if
        nothing did.

        Returns ``{'applied': N, 'skipped': [...], 'errors': [...]}``.
        """
        from django.contrib.contenttypes.models import ContentType
        from django.utils import timezone

        from core.audit.services import record

        if self.status not in ('proposed', 'approved'):
            return {
                'applied': 0,
                'skipped': [],
                'errors': [{'error': f'cannot apply an ops proposal in status {self.status!r}'}],
            }

        applied = 0
        skipped: list[dict] = []
        errors: list[dict] = []
        for change in self.changes or []:
            ref = str(change.get('object', ''))
            field = str(change.get('field', ''))
            try:
                label, _, pk = ref.partition(':')
                app_label, _, model_name = label.partition('.')
                if not (app_label and model_name and pk and field):
                    raise ValueError(f'malformed change {change!r}')
                ct = ContentType.objects.get(app_label=app_label, model=model_name.lower())
                model = ct.model_class()
                if model is None:
                    raise LookupError(f'model for {label!r} is not installed')
                obj = model.objects.get(pk=pk)
                live = getattr(obj, field)
                old = change.get('old')
                if live != old and str(live) != str(old):
                    skipped.append(
                        {'object': ref, 'field': field, 'reason': 'drifted', 'live': str(live)}
                    )
                    continue
                setattr(obj, field, change.get('new'))
                obj.save(update_fields=[field])
                applied += 1
                record(
                    event_type='assistant.ops_proposal.change_applied',
                    actor=user,
                    target=ref,
                    metadata={
                        'proposal': str(self.pk),
                        'kind': self.kind,
                        'source': self.source,
                        'field': field,
                        'old': change.get('old'),
                        'new': change.get('new'),
                    },
                )
            except Exception as exc:  # fail-soft per change — apply() never raises
                errors.append({'object': ref, 'field': field, 'error': str(exc)})

        if applied:
            self.status = 'applied'
            self.applied_at = timezone.now()
            self.apply_error = ''
        else:
            self.status = 'failed'
            problems = [e['error'] for e in errors] + [
                f'{s["object"]}: {s["reason"]}' for s in skipped
            ]
            self.apply_error = '; '.join(problems) or 'no changes to apply'
        self.save(update_fields=['status', 'applied_at', 'apply_error', 'updated_at'])
        return {'applied': applied, 'skipped': skipped, 'errors': errors}
