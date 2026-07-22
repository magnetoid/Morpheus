"""EU AI Act evidence export — the shared report builder.

Assembles a dated report of automated AI decisions (``agents.decision`` audit
rows, art. 12/13 provenance), the human-approval trail (``AgentApprovalRequest``),
and the run summary, for a merchant to hand a regulator. Used by BOTH the
dashboard page (``compliance_views.ai_act_report_view``) and the
``export_ai_act_report`` management command, so the two never drift.

Read-only: it only queries existing audit/agent tables — no new storage.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _iso(dt) -> str:
    return dt.isoformat() if dt else ''


def build_ai_act_report(
    *, since: datetime | None = None, until: datetime | None = None
) -> dict[str, Any]:
    """Build the AI-Act evidence report for [since, until).

    Returns a dict with ``period``, ``decisions`` (flat rows), ``approvals``,
    ``summary`` (counts), and ``guardrails`` (the active guardrail config). All
    values are JSON/CSV-friendly primitives.
    """
    from collections import Counter

    from core.agents.models import AgentApprovalRequest
    from core.audit.models import AuditEvent

    events = AuditEvent.objects.filter(event_type='agents.decision')
    approvals = AgentApprovalRequest.objects.all()
    if since is not None:
        events = events.filter(created_at__gte=since)
        approvals = approvals.filter(created_at__gte=since)
    if until is not None:
        events = events.filter(created_at__lt=until)
        approvals = approvals.filter(created_at__lt=until)

    decisions: list[dict[str, Any]] = []
    by_tool: Counter = Counter()
    by_model: Counter = Counter()
    for e in events.order_by('created_at').iterator():
        meta = e.metadata or {}
        tool = str(meta.get('tool') or '')
        model = str(meta.get('model') or '')
        by_tool[tool] += 1
        if model:
            by_model[model] += 1
        decisions.append(
            {
                'timestamp': _iso(e.created_at),
                'agent': str(meta.get('agent') or ''),
                'tool': tool,
                'target': e.target or '',
                'model': model,
                'provider': str(meta.get('provider') or ''),
                'actor': e.actor_label or '',
                'run_id': str(meta.get('run_id') or ''),
            }
        )

    approval_rows: list[dict[str, Any]] = []
    by_state: Counter = Counter()
    for a in approvals.select_related('decided_by').order_by('created_at').iterator():
        by_state[a.state] += 1
        approval_rows.append(
            {
                'timestamp': _iso(a.created_at),
                'tool': a.tool_name,
                'state': a.state,
                'decided_by': getattr(a.decided_by, 'email', '') or '',
                'decided_at': _iso(a.decided_at),
                'note': a.note or '',
            }
        )

    return {
        'period': {'since': _iso(since), 'until': _iso(until)},
        'decisions': decisions,
        'approvals': approval_rows,
        'summary': {
            'total_decisions': len(decisions),
            'total_approvals': len(approval_rows),
            'decisions_by_tool': dict(by_tool.most_common()),
            'decisions_by_model': dict(by_model.most_common()),
            'approvals_by_state': dict(by_state),
        },
        'guardrails': _guardrail_config(),
    }


def _guardrail_config() -> dict[str, Any]:
    """The active agent guardrail knobs (populated as guardrails ship). Fail-soft
    to an empty dict so the report renders even if agent_core config is absent."""
    try:
        from plugins.registry import plugin_registry

        plugin = plugin_registry.get('agent_core')
        if plugin is None:
            return {}
        keys = (
            'agents_paused',
            'spend_cap_daily',
            'max_price_change_pct',
            'max_refund_value',
        )
        return {k: plugin.get_config_value(k, None) for k in keys}
    except Exception:  # noqa: BLE001 — config read must not break the report
        return {}
