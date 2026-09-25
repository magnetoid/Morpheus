"""Recommendation pipeline — turn signal clusters into ranked recs.

Stages (synchronous, called from a Celery task):
  1. dedupe + suppression filter (services.emit_signal already does
     dedup; here we apply suppressions a second time at cluster level).
  2. cluster by (class, top-N entity) deterministically.
  3. score: impact × reach × evidence × age_decay.
  4. plan: LLM proposes a fix; we attach the customization summary +
     file excerpts.
  5. verify: second LLM tries to refute. Refuted → downgrade.
  6. policy gate: confidence vs class threshold → kind.
  7. safety gate: assert_diff_safe on the proposed patch.
  8. write SiRecommendation rows + fire backlog.updated hook.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.hooks import hook_registry
from core.safety import assert_diff_safe
from core.self_improvement.policy import decide_action, policy_for
from core.self_improvement.prompts import RECOMMEND_PROMPT_VERSION, recommend_v1
from core.self_improvement.verify import verify_recommendation

logger = logging.getLogger('morpheus.self_improvement.recommend')

TOP_CLUSTERS_PER_RUN = 50
EVENT_BACKLOG_UPDATED = 'self_improvement.backlog.updated'


@dataclass(slots=True)
class Cluster:
    class_name: str
    fingerprint: str
    severity: int
    seen_count: int
    age_hours: float
    signal_ids: list
    payload_samples: list


def run_analyzer(window_hours: int = 24) -> dict:
    """Pull signals from the last `window_hours`, cluster, rank, plan,
    verify, write recommendations. Returns counts for the Celery log.
    """
    from core.self_improvement.models import SiSignal  # noqa: PLC0415

    # Retention: drop signals well past the analysis window so the table can't
    # grow unbounded from long-tail collector traffic (esp. zero_search, which
    # fires on the public /products/?q= path). 30d >> the 24h analysis window,
    # so this never touches a signal the analyzer or a fresh recommendation
    # still needs.
    SiSignal.objects.filter(occurred_at__lt=timezone.now() - timedelta(days=30)).delete()

    since = timezone.now() - timedelta(hours=window_hours)
    clusters = _cluster(SiSignal.objects.filter(occurred_at__gte=since))
    if not clusters:
        return {'clusters': 0, 'recommendations': 0}

    clusters.sort(key=_score, reverse=True)
    top = clusters[:TOP_CLUSTERS_PER_RUN]

    written = 0
    for cluster in top:
        try:
            row = _process_cluster(cluster)
            if row is not None:
                written += 1
        except Exception:  # noqa: BLE001 — never let one bad cluster kill the run
            logger.exception('analyzer: cluster failed: %s', cluster.fingerprint)

    hook_registry.fire(EVENT_BACKLOG_UPDATED, added_count=written)
    return {'clusters': len(clusters), 'recommendations': written}


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------


def _cluster(qs) -> list[Cluster]:
    """Deterministic clustering — one cluster per (class, fingerprint).

    The class is derived from the signal source; the dedup at write-time
    already collapses identical fingerprints, so we mostly project here.
    """
    now = timezone.now()
    out: list[Cluster] = []
    for sig in qs.iterator(chunk_size=500):
        class_name = _class_for_source(sig.source)
        age_hours = max(0.0, (now - sig.occurred_at).total_seconds() / 3600)
        out.append(
            Cluster(
                class_name=class_name,
                fingerprint=sig.fingerprint,
                severity=int(sig.severity or 0),
                seen_count=int(sig.seen_count or 1),
                age_hours=age_hours,
                signal_ids=[sig.id],
                payload_samples=[sig.payload or {}],
            )
        )
    return out


def _score(c: Cluster) -> float:
    """impact_score = severity × reach × evidence × age_decay."""
    reach = min(1000, c.seen_count)
    age_decay = 1.0 / (1.0 + c.age_hours / 24.0)  # halves every 24h
    return float(c.severity) * reach * age_decay


# Backoff for a chronically-failing auto-heal. The OPEN-status dedup lets a
# 'failed' rec re-propose (failed ∉ OPEN_RECOMMENDATION_STATUSES), so without
# this a permanently-broken healer mints a fresh rec + action-log rows every
# nightly run forever, an unbounded backlog/audit leak (hunt #18). After this
# many failures for one fingerprint inside the window, the cluster stands down.
FAILURE_BACKOFF_LIMIT = 3
FAILURE_BACKOFF_DAYS = 7


def _process_cluster(cluster: Cluster):
    """Plan → Verify → Gate → Write one SiRecommendation. Returns the
    row or None if the cluster was suppressed at any stage."""
    from core.self_improvement.models import (  # noqa: PLC0415
        OPEN_RECOMMENDATION_STATUSES,
        SiRecommendation,
    )
    from core.self_improvement.services import fingerprint_for  # noqa: PLC0415

    pol = policy_for(cluster.class_name)
    if not pol.enabled:
        return None

    # Dedup: skip the whole (LLM-costing) pipeline when an OPEN recommendation
    # already covers this (class, cluster) — otherwise the same issue is
    # re-proposed every nightly run, flooding the backlog. A stable rec-level
    # fingerprint (not the signal PK, which rotates past the 24h dedup window)
    # is the guard.
    rec_fp = fingerprint_for(cluster.class_name, cluster.fingerprint)
    if SiRecommendation.objects.filter(
        fingerprint=rec_fp, status__in=OPEN_RECOMMENDATION_STATUSES
    ).exists():
        return None

    # Stand down a fingerprint that keeps failing to heal (hunt #18) — a 'failed'
    # rec is not OPEN, so the dedup above would otherwise re-propose it nightly.
    from datetime import timedelta  # noqa: PLC0415

    from django.utils import timezone  # noqa: PLC0415

    cooldown_start = timezone.now() - timedelta(days=FAILURE_BACKOFF_DAYS)
    if (
        SiRecommendation.objects.filter(
            fingerprint=rec_fp, status='failed', created_at__gte=cooldown_start
        ).count()
        >= FAILURE_BACKOFF_LIMIT
    ):
        return None

    plan = _plan(cluster, pol)
    if plan is None:
        return None

    verify = verify_recommendation(plan)
    if verify.refuted:
        plan['confidence'] = min(plan.get('confidence', 0.0), 0.49)
        plan['rationale'] = (
            f'{plan.get("rationale", "")} [verifier refuted: {"; ".join(verify.reasons[:2])}]'
        )[:1500]

    confidence = float(plan.get('confidence', 0.0))
    action = decide_action(
        class_name=cluster.class_name,
        confidence=confidence,
        is_customization_safe=bool(plan.get('is_customization_safe', True)),
    )
    if action == 'suppress':
        return None

    proposed_action = plan.get('proposed_action') or {'kind': 'advise'}
    # If the LLM proposed an actual patch, run it through the safety
    # boundary before we ever commit. Failure → downgrade to advise.
    patch = (proposed_action.get('patch') or '') if isinstance(proposed_action, dict) else ''
    files = (proposed_action.get('files') or []) if isinstance(proposed_action, dict) else []
    if patch:
        try:
            assert_diff_safe(patch, files)
        except Exception as safety_exc:  # noqa: BLE001
            logger.warning(
                'analyzer: safety gate downgraded %s: %s',
                cluster.fingerprint,
                safety_exc,
            )
            proposed_action = {'kind': 'advise', 'files': files, 'reason': 'safety_gate'}
            action = 'advise'

    with transaction.atomic():
        return SiRecommendation.objects.create(
            class_name=cluster.class_name,
            fingerprint=rec_fp,
            title=str(plan.get('title') or '')[:200] or _default_title(cluster),
            rationale=str(plan.get('rationale') or '')[:2000],
            confidence=Decimal(str(round(confidence, 3))),
            impact_score=int(plan.get('impact_score') or _score(cluster)),
            evidence_signal_ids=list(cluster.signal_ids),
            proposed_action=proposed_action,
            status='auto_applied' if action == 'auto_apply' else 'proposed',
            actor='worker',
            model_id=RECOMMEND_PROMPT_VERSION,
            tokens_used=int(plan.get('_tokens_used', 0)),
            is_customization_safe=bool(plan.get('is_customization_safe', True)),
        )


def _plan(cluster: Cluster, pol) -> dict | None:
    """Call the analyzer LLM with the recommend prompt. Returns the
    parsed JSON dict, or None on failure."""
    try:
        from core.agents.llm import LLMMessage  # noqa: PLC0415
        from core.assistant.providers import get_default_provider  # noqa: PLC0415
        from core.safety import PROTECTED_PATHS  # noqa: PLC0415

        provider = get_default_provider()
        if provider is None:
            return _heuristic_plan(cluster)

        prompt = recommend_v1(
            module=_module_for(cluster.class_name),
            recommendation_class=cluster.class_name,
            customization_summary='',
            signal_summary=_summarise(cluster),
            file_excerpts='',
            prior_fixes_summary='',
            reversibility=pol.reversible,
            auto_threshold=pol.auto_apply_threshold,
            protected_paths=list(PROTECTED_PATHS)[:25],
        )
        # Kernel providers expose `respond()` only — there is no `complete()`.
        response = provider.respond(
            messages=[
                LLMMessage(role='system', content='You output strict JSON. No prose.'),
                LLMMessage(role='user', content=prompt),
            ],
            max_tokens=1000,
            temperature=0.2,
        )
        text = (getattr(response, 'text', '') or '').strip()
        parsed = _parse_json(text)
        if parsed is None:
            return _heuristic_plan(cluster)
        parsed['_tokens_used'] = int(getattr(response, 'prompt_tokens', 0) or 0) + int(
            getattr(response, 'completion_tokens', 0) or 0
        )
        return parsed
    except Exception:  # noqa: BLE001
        logger.exception('analyzer: _plan failed')
        return _heuristic_plan(cluster)


def _heuristic_plan(cluster: Cluster) -> dict:
    """Fallback when no LLM is available — surface the cluster as a
    raw advise with deterministic title + rationale."""
    return {
        'title': _default_title(cluster),
        'rationale': f'Cluster of {len(cluster.signal_ids)} signals over the window.',
        'confidence': 0.5,
        'impact_score': int(_score(cluster)),
        'is_customization_safe': True,
        'proposed_action': {'kind': 'advise', 'files': [], 'patch': None},
        'uncertainty_flags': ['llm_unavailable'],
        'rollback_cost': 'trivial',
        '_tokens_used': 0,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_SOURCE_TO_CLASS = {
    'error_log': 'error_cluster',
    'csp': 'csp_drift',
    'slow_query': 'slow_query',
    'cart_abandon': 'cart_funnel_leak',
    'zero_search': 'zero_search',
    'seo_gap': 'seo_gap',
    'code_quality': 'style_fix',
    'upstream_drift': 'upstream_sync',
    'dep': 'dep_bump_patch',
    'cve': 'cve_patch',
    'lighthouse': 'lighthouse_regression',
    'dead_link': 'dead_link',
}


def _class_for_source(source: str) -> str:
    return _SOURCE_TO_CLASS.get(source, source)


def _module_for(class_name: str) -> str:
    return {
        'cve_patch': 'plugins',
        'dep_bump_patch': 'plugins',
        'upstream_sync': 'plugins+core',
    }.get(class_name, 'plugins')


def _default_title(cluster: Cluster) -> str:
    return f'{cluster.class_name}: {cluster.seen_count} occurrences in last 24h'


def _summarise(cluster: Cluster) -> str:
    sample = cluster.payload_samples[0] if cluster.payload_samples else {}
    return (
        f'fingerprint={cluster.fingerprint[:16]} '
        f'severity={cluster.severity} '
        f'seen={cluster.seen_count} '
        f'payload_sample={sample!s:.300}'
    )


def _parse_json(text: str):
    import json  # noqa: PLC0415

    try:
        return json.loads(text)
    except (ValueError, TypeError):
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except (ValueError, TypeError):
                return None
        return None
