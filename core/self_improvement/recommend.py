"""Recommendation pipeline — turn signals into ranked recommendations.

Stages (synchronous, called from a Celery task):
  1. project: one cluster per signal (``emit_signal`` already merged identical
     fingerprints and dropped suppressed ones).
  2. stand down: drop every cluster that already has its answer (an open
     recommendation, a rejected or snoozed one, a healer that keeps failing).
  3. score: severity × reach × age_decay, and keep the top N.
  4. plan: the model proposes a fix; without a model, a plain advisory.
  5. verify: a second call tries to refute. Refuted → downgrade.
  6. policy gate: confidence vs class threshold → kind.
  7. safety gate: assert_diff_safe on the proposed patch.
  8. write SiRecommendation rows + fire backlog.updated hook.

The model is asked only while it answers and the day's token budget holds: after
the first failed call the rest of the run writes plain advisories.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.agents.guardrails import AIPaused
from core.hooks import hook_registry
from core.llm_parsing import parse_llm_object
from core.safety import assert_diff_safe
from core.self_improvement.policy import decide_action, policy_for
from core.self_improvement.prompts import RECOMMEND_PROMPT_VERSION, recommend_v1
from core.self_improvement.verify import unavailable, verify_recommendation

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

    # Stand down BEFORE the top-N cut. Cut first and a store with 50 standing
    # gaps fills every slot with clusters that are then skipped, so nothing new
    # is ever proposed.
    answered = _standing_down({_rec_fingerprint(c) for c in clusters})
    fresh = [c for c in clusters if _rec_fingerprint(c) not in answered]
    fresh.sort(key=_score, reverse=True)

    model = _ModelUse()
    written = 0
    stopped = ''
    for cluster in fresh[:TOP_CLUSTERS_PER_RUN]:
        try:
            row = _process_cluster(cluster, model)
            if row is not None:
                written += 1
        except SoftTimeLimitExceeded:
            # Out of time: stop here and report what was written, rather than
            # run on into the hard kill with the hook unfired.
            logger.warning('analyzer: out of time after %s recommendation(s)', written)
            stopped = 'time_limit'
            break
        except Exception:  # noqa: BLE001 — never let one bad cluster kill the run
            logger.exception('analyzer: cluster failed: %s', cluster.fingerprint)

    hook_registry.fire(EVENT_BACKLOG_UPDATED, added_count=written)
    out = {'clusters': len(clusters), 'recommendations': written}
    if stopped:
        out['stopped'] = stopped
    return out


class _ModelUse:
    """Whether this run may still ask the model.

    It stops for the rest of the run after a failed call (a provider answering
    402 or timing out fails the same way for every cluster, at up to a minute
    each) and once the day's token budget is spent. ``budget=0`` is no budget.
    """

    def __init__(self, budget: int | None = None) -> None:
        self.down = False
        if budget is None:
            budget = (getattr(settings, 'SELF_IMPROVEMENT', None) or {}).get('daily_token_budget')
        self.budget = int(budget or 0)
        self.spent = self._spent_today() if self.budget else 0

    @staticmethod
    def _spent_today() -> int:
        from django.db.models import Sum  # noqa: PLC0415

        from core.self_improvement.models import SiRecommendation  # noqa: PLC0415

        since = timezone.now() - timedelta(hours=24)
        spent = SiRecommendation.objects.filter(created_at__gte=since).aggregate(
            t=Sum('tokens_used')
        )['t']
        return int(spent or 0)

    @property
    def allowed(self) -> bool:
        return not self.down and not (self.budget and self.spent >= self.budget)


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


def _rec_fingerprint(cluster: Cluster) -> str:
    """The recommendation's own fingerprint: stable across nights, unlike the
    signal's primary key, which rotates past the 24h dedup window."""
    from core.self_improvement.services import fingerprint_for  # noqa: PLC0415

    return fingerprint_for(cluster.class_name, cluster.fingerprint)


SNOOZE_DAYS = 30


def _standing_down(rec_fps) -> set[str]:
    """Which of these recommendation fingerprints already have their answer.

    - an OPEN recommendation covers it;
    - the merchant rejected it (for good), or snoozed it in the last 30 days.
      The reject also writes a suppression from the evidence signals, but those
      are pruned after 30 days, and a reject without them used to return the
      next night;
    - its healer failed FAILURE_BACKOFF_LIMIT times inside the window (a
      'failed' recommendation is not open, so it would otherwise be proposed
      again every night, hunt #18).
    """
    from django.db.models import Count, Q  # noqa: PLC0415

    from core.self_improvement.models import (  # noqa: PLC0415
        OPEN_RECOMMENDATION_STATUSES,
        SiRecommendation,
    )

    now = timezone.now()
    fps = list(rec_fps)
    out: set[str] = set()
    for start in range(0, len(fps), 500):  # sqlite caps the variables of one query
        rows = SiRecommendation.objects.filter(fingerprint__in=fps[start : start + 500])
        out.update(
            rows.filter(
                Q(status__in=(*OPEN_RECOMMENDATION_STATUSES, 'rejected'))
                | Q(status='suppressed', updated_at__gte=now - timedelta(days=SNOOZE_DAYS))
            ).values_list('fingerprint', flat=True)
        )
        out.update(
            rows.filter(status='failed', created_at__gte=now - timedelta(days=FAILURE_BACKOFF_DAYS))
            .values('fingerprint')
            .annotate(n=Count('id'))
            .filter(n__gte=FAILURE_BACKOFF_LIMIT)
            .values_list('fingerprint', flat=True)
        )
    return out


def _process_cluster(cluster: Cluster, model: _ModelUse | None = None):
    """Plan → Verify → Gate → Write one SiRecommendation. Returns the
    row or None if the cluster was suppressed at any stage."""
    from core.self_improvement.models import SiRecommendation  # noqa: PLC0415

    model = model or _ModelUse()
    pol = policy_for(cluster.class_name)
    if not pol.enabled:
        return None

    # Checked again here: the run filters before its cut, but a direct caller
    # and a second worker do not.
    rec_fp = _rec_fingerprint(cluster)
    if rec_fp in _standing_down([rec_fp]):
        return None

    plan = _plan(cluster, pol, model)
    if plan is None:
        return None

    verify = verify_recommendation(plan) if model.allowed else unavailable('model_unavailable')
    if verify.failed:
        model.down = True
    model.spent += verify.tokens_used
    plan['_tokens_used'] = int(plan.get('_tokens_used', 0)) + verify.tokens_used
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


def _plan(cluster: Cluster, pol, model: _ModelUse | None = None) -> dict | None:
    """Ask the model for a fix. Without a model (none configured, it failed
    earlier in this run, the day's budget is spent) the plain advisory."""
    model = model or _ModelUse(budget=0)
    if not model.allowed:
        return _heuristic_plan(cluster)
    try:
        from core.agents.llm import LLMMessage  # noqa: PLC0415
        from core.assistant.providers import get_default_provider  # noqa: PLC0415
        from core.safety import PROTECTED_PATHS  # noqa: PLC0415

        provider = get_default_provider()
        if provider is None:
            model.down = True
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
        tokens = int(getattr(response, 'prompt_tokens', 0) or 0) + int(
            getattr(response, 'completion_tokens', 0) or 0
        )
        model.spent += tokens
        text = (getattr(response, 'text', '') or '').strip()
        # An answer that cannot be read was still paid for: the recommendation
        # carries its tokens either way, since that is what tomorrow's budget reads.
        parsed = parse_llm_object(text) or _heuristic_plan(cluster)
        parsed['_tokens_used'] = tokens
        return parsed
    except SoftTimeLimitExceeded:
        raise
    except AIPaused as e:  # the merchant paused AI or hit today's cap: not a fault
        logger.info('analyzer: _plan skipped the model: %s', e)
        model.down = True
        return _heuristic_plan(cluster)
    except Exception:  # noqa: BLE001
        logger.exception('analyzer: _plan failed; the rest of this run skips the model')
        model.down = True
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
