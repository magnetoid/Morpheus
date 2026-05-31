"""Core services for the self-improvement engine.

The functions here are the only sanctioned way to write into the engine's
tables. Collectors call ``emit_signal()``; tasks call
``start_ingest_job()`` / ``finish_ingest_job()``. Everything else (the
analyzer, the healer, the dashboard views) reads from these tables but
does not write directly.

Why route everything through here:
  - Dedup is centralised — a flood of identical errors becomes one
    SiSignal row with an incremented seen_count, not N rows.
  - Suppression is enforced in one place — if a SiSuppression matches,
    the signal is dropped silently rather than producing noise.
  - Audit-friendly — every write path is observable and testable in
    isolation.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from core.self_improvement.models import (
    SiCustomization,
    SiIngestJob,
    SiSignal,
    SiSuppression,
)

logger = logging.getLogger('morpheus.self_improvement.services')

# Dedup window: identical (source, fingerprint) within this many hours
# bumps `seen_count` on the existing row instead of inserting.
DEDUP_WINDOW_HOURS = 24


# ---------------------------------------------------------------------------
# Signal emission
# ---------------------------------------------------------------------------


def emit_signal(
    *,
    source: str,
    fingerprint: str,
    severity: int = 50,
    payload: dict[str, Any] | None = None,
    occurred_at=None,
) -> SiSignal | None:
    """Record one signal, with dedup + suppression baked in.

    Returns:
      - The SiSignal row (existing if deduped, new otherwise).
      - ``None`` if a SiSuppression rule swallowed the signal.

    Inputs are trusted (collectors are internal). No length capping
    here — the model defines max_length on the columns.
    """
    if not source or not fingerprint:
        raise ValueError('source and fingerprint are required')

    payload = payload or {}
    occurred_at = occurred_at or timezone.now()
    severity = max(0, min(100, severity))

    # Suppression: a matching SiSuppression with no expiry (or unexpired)
    # silently drops the signal. We check class-name matches against the
    # recommendation classes that emit this source-of-truth fingerprint,
    # which is one-step removed but consistent with the rejection UI.
    cutoff = timezone.now()
    if (
        SiSuppression.objects.filter(
            match_class=source,
            match_fingerprint=fingerprint,
        )
        .filter(models_either_unexpired_or_after(cutoff))
        .exists()
    ):
        logger.debug('signal suppressed: %s/%s', source, fingerprint)
        return None

    # Dedup: same (source, fingerprint) within the dedup window?
    window_start = occurred_at - timedelta(hours=DEDUP_WINDOW_HOURS)
    existing = (
        SiSignal.objects.filter(
            source=source,
            fingerprint=fingerprint,
            occurred_at__gte=window_start,
        )
        .order_by('-occurred_at')
        .first()
    )
    if existing is not None:
        existing.seen_count = (existing.seen_count or 1) + 1
        existing.severity = max(existing.severity, severity)
        # Merge payload non-destructively — newer keys win for new info,
        # but existing keys are preserved so we can see history.
        if payload:
            merged = dict(existing.payload or {})
            merged.update(payload)
            existing.payload = merged
        existing.save(update_fields=['seen_count', 'severity', 'payload', 'updated_at'])
        return existing

    return SiSignal.objects.create(
        source=source,
        fingerprint=fingerprint,
        severity=severity,
        payload=payload,
        occurred_at=occurred_at,
    )


def models_either_unexpired_or_after(now):
    """Q-object factory: ``expires_at IS NULL`` OR ``expires_at > now``.

    Pulled out so the import of Django's Q stays local to this helper
    and emit_signal() reads cleanly.
    """
    from django.db.models import Q  # noqa: PLC0415 — local import keeps Q out of module top

    return Q(expires_at__isnull=True) | Q(expires_at__gt=now)


# ---------------------------------------------------------------------------
# Fingerprint helpers — deterministic, no LLM
# ---------------------------------------------------------------------------


def fingerprint_for(*parts: Any) -> str:
    """SHA-256 (first 32 hex chars) of the colon-joined parts.

    Use this from every collector so dedup behaves the same way for
    every source. Parts are stringified; ``None`` becomes ``''``.
    """
    joined = ':'.join('' if p is None else str(p) for p in parts)
    return hashlib.sha256(joined.encode('utf-8')).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Ingest job lifecycle — for observability of the collectors themselves
# ---------------------------------------------------------------------------


def start_ingest_job(collector: str) -> SiIngestJob:
    """Record the start of a collector run. Returns the open job row."""
    return SiIngestJob.objects.create(
        collector=collector,
        started_at=timezone.now(),
        status='ok',
    )


def finish_ingest_job(
    job: SiIngestJob,
    *,
    signals_emitted: int,
    status: str = 'ok',
    error: str = '',
) -> SiIngestJob:
    """Stamp finished_at + counts on an open job row.

    `status` is one of: 'ok', 'partial', 'failed' (see INGEST_STATUSES).
    On failure, callers should pass ``status='failed'`` and ``error=...``
    so the dashboard can surface unhealthy collectors.
    """
    job.finished_at = timezone.now()
    job.signals_emitted = signals_emitted
    job.status = status
    job.error = error[:4096]
    job.save(update_fields=['finished_at', 'signals_emitted', 'status', 'error', 'updated_at'])
    return job


# ---------------------------------------------------------------------------
# Customization lookup — used by upstream_drift + healer safety gate
# ---------------------------------------------------------------------------


def is_path_customized(path: str) -> bool:
    """Return True if `path` has a non-expired SiCustomization row with
    intent != 'experimental'. `intentional` and `vendor_specific` block
    upstream cherry-picks; `experimental` is allowed through (the human
    declared it as a probe, not a permanent fork).
    """
    return SiCustomization.objects.filter(path=path).exclude(intent='experimental').exists()
