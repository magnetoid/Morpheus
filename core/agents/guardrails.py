"""Merchant-tunable agent guardrails — the single read seam.

The config lives on the ``agent_core`` plugin (one "Agent guardrails" settings
panel). It is read *here* so that every enforcement site imports its guard from
**core** — both agent runtimes (``core/agents/runtime.py`` kill switch + daily
caps, ``core/assistant/runtime.py`` Linda kill switch) and the money-tool seams
(``catalog`` price change, ``orders`` refund). Nothing reaches into another
plugin's config directly — enforcement is plugin→core, never plugin→plugin.

Reading plugin config from core is boundary-legal: the ratchet forbids
``plugins.installed.*`` imports only; ``plugins.registry`` is already imported by
~14 other core modules (``core/embeddings.py``, ``core/templatetags/morph.py``,
``core/assistant/tools/*`` …).

**Cross-process freshness matters.** A plugin's ``_config_cache`` is per-process
and is only invalidated by ``set_config`` on the *same* instance. A celery worker
running an agent would otherwise never see a kill switch a merchant just flipped
from the web dashboard — the switch would be dead. So every read invalidates the
cache first: one small indexed query, negligible next to a provider call, and it
is exactly what makes the mid-run halt real rather than theatre.

Everything is **off by default** (``agents_paused`` False, every cap ``0`` =
unlimited), so an unconfigured store behaves exactly as before.
"""

from __future__ import annotations

from datetime import datetime


def _read(key: str, default):
    """Read one agent_core config value, cross-process fresh. Fail-soft."""
    try:
        from plugins.registry import app_registry

        plugin = app_registry.get('agent_core')
        if plugin is None:
            return default
        plugin.invalidate_config_cache()
        return plugin.get_config_value(key, default)
    except Exception:  # noqa: BLE001 — a config glitch must never wedge agents on or off
        return default


def _num(key: str) -> float:
    """A numeric cap. Blank / unset / bad value / negative → 0.0 (= no cap)."""
    try:
        return max(0.0, float(_read(key, 0) or 0))
    except (TypeError, ValueError):
        return 0.0


# ── The knobs ──────────────────────────────────────────────────────────────


def agents_paused() -> bool:
    """The global kill switch. Fail-soft to NOT paused — a transient config
    error must never silently black out every agent."""
    return bool(_read('agents_paused', False))


def max_agent_runs_daily() -> int:
    """Hard ceiling on autonomous agent runs per calendar day. 0 = unlimited.
    Model-independent — the circuit breaker that fires even on unpriced models."""
    return int(_num('max_agent_runs_daily'))


def daily_spend_cap_usd() -> float:
    """Best-effort USD/day ceiling using estimated model pricing. 0 = off.
    Does NOT bound models with no known price (self-hosted / unpriced) — use the
    run cap for a hard limit there."""
    return _num('spend_cap_daily')


def max_price_change_pct() -> float:
    """Largest single price change (up or down) an agent may make, in percent.
    0 = no cap."""
    return _num('max_price_change_pct')


def max_refund_value() -> float:
    """Largest single refund an agent may issue, in store currency. 0 = no cap."""
    return _num('max_refund_value')


# ── Daily accumulators (over persisted AgentRun rows) ────────────────────────


def today_start() -> datetime:
    """Start of the current calendar day in the server's active timezone."""
    from django.utils import timezone

    return timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)


def _runs_today(exclude_id=None):
    from core.agents.models import AgentRun

    qs = AgentRun.objects.filter(started_at__gte=today_start())
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)
    return qs


def daily_run_count(exclude_id=None) -> int:
    return _runs_today(exclude_id).count()


def daily_spend_usd(exclude_id=None) -> float:
    """Summed estimated USD across today's runs. Priced per-model (price depends
    on a model-prefix match, so it can't be a plain SQL SUM)."""
    from django.db.models import Sum

    from core.agents.pricing import estimate_cost

    rows = (
        _runs_today(exclude_id)
        .values('model')
        .annotate(pt=Sum('prompt_tokens'), ct=Sum('completion_tokens'))
    )
    return sum(estimate_cost(r['model'] or '', r['pt'] or 0, r['ct'] or 0) for r in rows)


def run_start_block_reason(exclude_id=None) -> str | None:
    """Reason a NEW agent run must be refused at start, or None to allow.

    Checked once per run (not per step): the daily totals barely move within a
    single run, and the spend query is a group-by aggregate. ``exclude_id`` is
    the current run's own row, which is already ``running`` in the table.
    """
    cap_runs = max_agent_runs_daily()
    if cap_runs and daily_run_count(exclude_id) >= cap_runs:
        return 'run_cap_exceeded'
    cap_usd = daily_spend_cap_usd()
    if cap_usd and daily_spend_usd(exclude_id) >= cap_usd:
        return 'spend_cap_exceeded'
    return None
