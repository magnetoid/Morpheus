"""Execute queue — picks up approved/auto-applied recommendations
and dispatches to the registered Healer for the class.

Every phase of every run lands in SiActionLog so the dashboard can
show the audit trail. Failures never raise — we record an action_log
entry with outcome='failed' and move on.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from django.utils import timezone

from core.hooks import hook_registry
from core.safety import is_class_allowed

logger = logging.getLogger('morpheus.self_improvement.heal')

EVENT_HEALING_STARTED = 'self_improvement.healing.started'
EVENT_HEALING_FAILED = 'self_improvement.healing.failed'
EVENT_HEALING_APPLIED = 'self_improvement.recommendation.auto_applied'

BATCH_SIZE = 50


def execute_queue() -> dict:
    """Pick up status='approved' or 'auto_applied' rows and run them.

    'approved' = human clicked Approve on the dashboard.
    'auto_applied' = the analyzer pre-flagged for autonomous run.

    Returns counts keyed by outcome for the Celery task log.
    """
    from core.self_improvement.models import SiRecommendation  # noqa: PLC0415

    qs = SiRecommendation.objects.filter(status__in=('approved', 'auto_applied')).order_by(
        '-impact_score'
    )[:BATCH_SIZE]

    counts = {'ok': 0, 'blocked': 0, 'failed': 0}
    for rec in qs:
        outcome = run_one(rec)
        counts[outcome] = counts.get(outcome, 0) + 1
    return counts


def run_one(rec: Any) -> str:  # noqa: PLR0911 — one return per phase is the point
    """Walk the healing phases for one recommendation. Returns the
    final outcome ('ok' / 'blocked' / 'failed')."""
    from core.self_improvement.healers.base import resolve_healers  # noqa: PLC0415
    from core.self_improvement.models import SiRecommendation  # noqa: PLC0415

    run_id = uuid.uuid4()
    started = timezone.now()

    # Class blocklist (core/safety.py CLASS_BLOCKLIST).
    if not is_class_allowed(rec.class_name):
        _log(rec, 'gate', 'blocked', run_id, details={'reason': 'class_blocklist'})
        _mark_failed(rec, 'class_blocklist')
        return 'blocked'

    # Phase: gate — candidate arbitration. resolve_healers() bridges the
    # analyzer's problem taxonomy ('seo_gap', 'zero_search', …) to healer
    # capabilities ('alt_text', 'meta_description', …); the first candidate
    # whose safe_to_apply() accepts runs. A mixed-evidence recommendation
    # heals one slice per run — remaining gaps re-surface via the collectors.
    candidates = resolve_healers(rec.class_name)
    if not candidates:
        _log(rec, 'gate', 'blocked', run_id, details={'reason': 'no_healer'})
        _mark_failed(rec, 'no_healer')
        return 'blocked'

    healer = None
    gate_reasons: dict[str, str] = {}
    for cand in candidates:
        ok, why = cand.safe_to_apply(rec)
        if ok:
            healer = cand
            break
        gate_reasons[cand.class_name] = why
    if healer is None:
        why = '; '.join(f'{k}: {v}' for k, v in gate_reasons.items()) or 'gate_refused'
        _log(rec, 'gate', 'blocked', run_id, details={'reason': why, 'candidates': gate_reasons})
        _mark_failed(rec, f'gate:{why}'[:500])
        return 'blocked'

    hook_registry.fire(
        EVENT_HEALING_STARTED,
        action_log_id=None,
        recommendation_id=rec.pk,
        class_name=rec.class_name,
    )

    # Phase: execute
    try:
        result = healer.apply(rec)
    except Exception as exc:  # noqa: BLE001
        logger.exception('healer apply raised for %s', rec.pk)
        _log(rec, 'execute', 'failed', run_id, details={'error': str(exc)[:1000]})
        _mark_failed(rec, f'apply:{exc}')
        hook_registry.fire(EVENT_HEALING_FAILED, recommendation_id=rec.pk, error=str(exc))
        return 'failed'

    if not result.ok:
        _log(
            rec,
            'execute',
            'failed',
            run_id,
            details={'error': result.error or 'apply_returned_false'},
        )
        _mark_failed(rec, result.error or 'apply_returned_false')
        return 'failed'

    _log(rec, 'execute', 'ok', run_id, details=result.details, duration_ms=_ms(started))

    # Phase: verify
    verify_started = timezone.now()
    try:
        ver = healer.verify(rec)
    except Exception as exc:  # noqa: BLE001
        logger.exception('healer verify raised for %s', rec.pk)
        _log(rec, 'verify', 'failed', run_id, details={'error': str(exc)[:1000]})
        # Apply succeeded but verify failed → roll back.
        return _rollback(rec, healer, run_id)

    if not ver.ok:
        _log(rec, 'verify', 'failed', run_id, details=ver.details or {'error': ver.error})
        return _rollback(rec, healer, run_id)

    _log(rec, 'verify', 'ok', run_id, details=ver.details, duration_ms=_ms(verify_started))

    # Mark success.
    SiRecommendation.objects.filter(pk=rec.pk).update(
        status='auto_applied' if rec.status == 'auto_applied' else 'merged',
        updated_at=timezone.now(),
    )
    hook_registry.fire(EVENT_HEALING_APPLIED, recommendation_id=rec.pk)
    return 'ok'


# ---------------------------------------------------------------------------


def _rollback(rec, healer, run_id) -> str:
    started = timezone.now()
    try:
        r = healer.rollback(rec)
    except Exception as exc:  # noqa: BLE001
        _log(rec, 'rollback', 'failed', run_id, details={'error': str(exc)[:1000]})
        _mark_failed(rec, f'rollback:{exc}')
        return 'failed'
    _log(
        rec,
        'rollback',
        'ok' if r.ok else 'failed',
        run_id,
        details=r.details,
        duration_ms=_ms(started),
    )
    _mark_failed(rec, 'verify_failed')
    return 'failed'


def _log(rec, phase, outcome, run_id, *, details=None, duration_ms=0):
    from core.self_improvement.models import SiActionLog  # noqa: PLC0415

    SiActionLog.objects.create(
        recommendation=rec,
        phase=phase,
        outcome=outcome,
        details=details or {},
        sandbox_run_id=run_id,
        duration_ms=duration_ms,
    )


def _mark_failed(rec, reason: str):
    from core.self_improvement.models import SiRecommendation  # noqa: PLC0415

    SiRecommendation.objects.filter(pk=rec.pk).update(
        status='failed',
        rationale=f'{rec.rationale}\n[heal_failed: {reason}]'[:2000],
        updated_at=timezone.now(),
    )


def _ms(started) -> int:
    delta = timezone.now() - started
    return int(delta.total_seconds() * 1000)
