"""Database tables for the self-improvement engine.

Six tables (all prefixed `si_` in the DB via `db_table` override):
  - SiSignal       — raw ingested events, append-only, weekly partition by date
  - SiRecommendation — the prioritised backlog the dashboard renders
  - SiActionLog    — every healing attempt (audit trail)
  - SiIngestJob    — per-collector health
  - SiSuppression  — "rejected once, never again" rules
  - SiCustomization — per-file declarations of intentional drift from upstream

Naming: model classes carry the `Si` prefix to keep code readable; the
underlying tables are `si_*` (without the `morph_self_improvement_*` Django
default) for portability of external tooling that grep the DB.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

# ---------------------------------------------------------------------------
# Status / source / phase enumerations — module-level for reuse + introspection
# ---------------------------------------------------------------------------

SIGNAL_SOURCES = (
    ('error_log', 'Error log'),
    ('csp', 'CSP violation'),
    ('slow_query', 'Slow query'),
    ('web_vital', 'Web vital'),
    ('cart_abandon', 'Cart abandon'),
    ('zero_search', 'Zero-result search'),
    ('cve', 'CVE advisory'),
    ('dep', 'Dependency advisory'),
    ('lighthouse', 'Lighthouse regression'),
    ('dead_link', 'Dead link'),
    ('seo_gap', 'SEO gap'),
    ('code_quality', 'Code-quality finding'),
    ('upstream_drift', 'Upstream drift'),
)

RECOMMENDATION_STATUS = (
    ('proposed', 'Proposed'),
    ('approved', 'Approved'),
    ('auto_applied', 'Auto-applied'),
    ('in_pr', 'In PR'),
    ('merged', 'Merged'),
    ('rejected', 'Rejected'),
    ('suppressed', 'Suppressed'),
    ('failed', 'Failed'),
)

ACTION_PHASES = (
    ('detect', 'Detect'),
    ('propose', 'Propose'),
    ('gate', 'Safety gate'),
    ('execute', 'Execute'),
    ('verify', 'Verify'),
    ('rollback', 'Rollback'),
)

ACTION_OUTCOMES = (
    ('ok', 'OK'),
    ('blocked', 'Blocked by safety boundary'),
    ('failed', 'Failed'),
    ('timeout', 'Timeout'),
)

INGEST_STATUSES = (
    ('ok', 'OK'),
    ('partial', 'Partial'),
    ('failed', 'Failed'),
)

CUSTOMIZATION_INTENTS = (
    ('intentional', 'Intentional'),
    ('experimental', 'Experimental'),
    ('vendor_specific', 'Vendor-specific'),
)


# ---------------------------------------------------------------------------
# 1. SiSignal — raw ingested events
# ---------------------------------------------------------------------------


class SiSignal(models.Model):
    """One row per emitted signal (error, CSP violation, code finding, etc.).

    Append-only: deduplication happens via the `fingerprint` column +
    `seen_count` increment in a 24h window, so a flood of identical errors
    becomes one row with count=N rather than N rows.
    """

    source = models.CharField(max_length=64, choices=SIGNAL_SOURCES, db_index=True)
    fingerprint = models.CharField(max_length=128, db_index=True)
    severity = models.SmallIntegerField(default=50, help_text='0-100')
    payload = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(db_index=True)
    seen_count = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'si_signal'
        verbose_name = 'SI signal'
        verbose_name_plural = 'SI signals'
        indexes = [
            models.Index(fields=['source', '-occurred_at'], name='si_sig_src_occur_idx'),
            models.Index(fields=['fingerprint', '-occurred_at'], name='si_sig_fp_occur_idx'),
        ]
        ordering = ['-occurred_at']

    def __str__(self) -> str:
        return f'{self.source}:{self.fingerprint[:16]} (sev={self.severity})'


# ---------------------------------------------------------------------------
# 2. SiRecommendation — the prioritised backlog
# ---------------------------------------------------------------------------


class SiRecommendation(models.Model):
    """One row per AI-generated recommendation that the dashboard renders.

    Multiple SiSignal rows can feed one SiRecommendation (1-N via
    evidence_signal_ids); the engine deduplicates clusters before
    generating recommendations.
    """

    class_name = models.CharField(
        max_length=64,
        db_index=True,
        db_column='class',
        help_text='one of the 16 issue classes (seo_gap, dep_bump, …)',
    )
    title = models.CharField(max_length=200, help_text='imperative, ≤ 80 chars')
    rationale = models.TextField(blank=True, help_text='LLM-written, cites signal_ids')
    confidence = models.DecimalField(max_digits=4, decimal_places=3, help_text='0.000–1.000')
    impact_score = models.IntegerField(default=0, help_text='impact × feasibility × evidence')
    evidence_signal_ids = models.JSONField(
        default=list, blank=True, help_text='list[int] — FK to SiSignal'
    )
    proposed_action = models.JSONField(
        default=dict, blank=True, help_text='{kind, files, patch, test_command}'
    )
    status = models.CharField(
        max_length=16,
        choices=RECOMMENDATION_STATUS,
        default='proposed',
        db_index=True,
    )
    pr_url = models.CharField(max_length=300, blank=True)
    actor = models.CharField(max_length=64, blank=True)
    suppressed_by = models.ForeignKey(
        'SiSuppression',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='recommendations',
    )
    model_id = models.CharField(max_length=64, blank=True, help_text='LLM model + version')
    tokens_used = models.IntegerField(default=0)
    is_customization_safe = models.BooleanField(
        default=True,
        help_text='False blocks auto-apply when the file is customised',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'si_recommendation'
        verbose_name = 'SI recommendation'
        verbose_name_plural = 'SI recommendations'
        indexes = [
            models.Index(fields=['status', '-impact_score'], name='si_rec_status_score_idx'),
            models.Index(fields=['class_name', 'status'], name='si_rec_class_status_idx'),
        ]
        ordering = ['-impact_score', '-created_at']

    def __str__(self) -> str:
        return f'[{self.class_name}] {self.title}'


# ---------------------------------------------------------------------------
# 3. SiActionLog — audit trail for every healing attempt
# ---------------------------------------------------------------------------


class SiActionLog(models.Model):
    """One row per healing-pipeline phase outcome.

    Six rows per recommendation in the happy path
    (detect → propose → gate → execute → verify → rollback?). Used by
    the Healing log tab and by the monthly eval task.
    """

    recommendation = models.ForeignKey(
        SiRecommendation, on_delete=models.CASCADE, related_name='actions'
    )
    phase = models.CharField(max_length=16, choices=ACTION_PHASES)
    outcome = models.CharField(max_length=16, choices=ACTION_OUTCOMES, db_index=True)
    details = models.JSONField(default=dict, blank=True)
    sandbox_run_id = models.UUIDField(null=True, blank=True, db_index=True)
    duration_ms = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'si_action_log'
        verbose_name = 'SI action log entry'
        verbose_name_plural = 'SI action log'
        indexes = [
            models.Index(fields=['recommendation', 'phase'], name='si_act_rec_phase_idx'),
            models.Index(fields=['outcome', '-created_at'], name='si_act_outcome_idx'),
        ]
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.recommendation_id}:{self.phase}={self.outcome}'


# ---------------------------------------------------------------------------
# 4. SiIngestJob — collector health
# ---------------------------------------------------------------------------


class SiIngestJob(models.Model):
    """Per-run health record for each collector."""

    collector = models.CharField(max_length=64, db_index=True)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    signals_emitted = models.IntegerField(default=0)
    status = models.CharField(max_length=16, choices=INGEST_STATUSES, default='ok')
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'si_ingest_job'
        verbose_name = 'SI ingest job'
        verbose_name_plural = 'SI ingest jobs'
        indexes = [
            models.Index(fields=['collector', '-started_at'], name='si_job_coll_start_idx'),
        ]
        ordering = ['-started_at']

    def __str__(self) -> str:
        return f'{self.collector} {self.status} @ {self.started_at:%Y-%m-%d %H:%M}'


# ---------------------------------------------------------------------------
# 5. SiSuppression — "rejected once, never again" rules
# ---------------------------------------------------------------------------


class SiSuppression(models.Model):
    """When a human rejects a recommendation, this row prevents the same
    issue from coming back. Either suppresses one specific fingerprint
    (`match_fingerprint != NULL`) or an entire class.
    """

    match_class = models.CharField(max_length=64, db_index=True)
    match_fingerprint = models.CharField(max_length=128, blank=True, default='', db_index=True)
    reason = models.TextField(help_text='required from rejector')
    expires_at = models.DateTimeField(null=True, blank=True, help_text='NULL = forever')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'si_suppression'
        verbose_name = 'SI suppression rule'
        verbose_name_plural = 'SI suppression rules'
        constraints = [
            models.UniqueConstraint(
                fields=['match_class', 'match_fingerprint'],
                condition=models.Q(expires_at__isnull=True),
                name='si_supp_unique_active',
            ),
        ]
        ordering = ['-created_at']

    def __str__(self) -> str:
        scope = self.match_fingerprint[:16] if self.match_fingerprint else '(all)'
        return f'{self.match_class}/{scope}'


# ---------------------------------------------------------------------------
# 6. SiCustomization — declared drift from canonical Morpheus
# ---------------------------------------------------------------------------


class SiCustomization(models.Model):
    """Vibecoding-platform differentiator: per-file declarations of
    intentional drift from canonical Morpheus.

    The upstream-drift collector reads this table to classify each
    detected diff as intentional / drift / orphan. Files flagged
    `intentional` are off-limits to every healer except `upstream_sync`.
    """

    path = models.CharField(max_length=500, unique=True)
    intent = models.CharField(max_length=32, choices=CUSTOMIZATION_INTENTS, default='intentional')
    why = models.TextField(help_text='human-written rationale')
    owner = models.CharField(max_length=64, blank=True)
    locked_until = models.DateTimeField(
        null=True, blank=True, help_text='NULL = forever; auto-revisit after'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'si_customization'
        verbose_name = 'SI customization'
        verbose_name_plural = 'SI customizations'
        ordering = ['path']

    def __str__(self) -> str:
        return f'{self.path} ({self.intent})'
