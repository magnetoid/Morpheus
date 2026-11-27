"""Save one agent run: its steps as they happen, and how it ended.

The runtime (`core/agents/runtime.py`) knows nothing about the database. Every
caller that keeps an `AgentRun` row for a run saves it through this module:
agent_core's `run_agent` and the spawned Worker (`core/assistant/tools/spawn.py`).
There were two copies, and they had drifted.

What a run spent comes from its `RunUsage` meter, which the caller owns, so a
run that timed out or raised still writes its tokens and its model: the spend
cap prices a run by both (`guardrails.daily_spend_usd`), and a row closed with
neither counted as free.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from core.agents.trace import TraceStep
from core.agents.usage import USAGE_KEY, RunUsage

logger = logging.getLogger('morpheus.agents.run_store')

_JSON_TYPES = (dict, list, str, int, float, bool)


class StepMirror:
    """A trace subscriber: saves each step as an `AgentStep` of the run and
    records each tool result in the audit trail.

    `incomplete` turns True when a step could not be saved; pass it to
    `finish()` so the run says its record has a gap.
    """

    def __init__(
        self,
        run,
        *,
        agent_name: str = '',
        on_step: Callable[[TraceStep], None] | None = None,
    ) -> None:
        self.run = run
        self.agent_name = agent_name or getattr(run, 'agent_name', '') or ''
        self.incomplete = False
        self._on_step = on_step
        self._seq = 0

    def __call__(self, step: TraceStep) -> None:
        from django.db import DatabaseError

        self._seq += 1
        output = step.output
        if output is not None and not isinstance(output, _JSON_TYPES):
            output = str(output)
        try:
            self._save(step, output)
        except DatabaseError as e:
            self.incomplete = True
            logger.warning('run_store: step %s of run %s not saved: %s', self._seq, self.run.pk, e)
        # Outside the save: the audit trail must not depend on the step table
        # taking the row.
        if step.kind == 'tool_result':
            self._audit(step, output)
        if self._on_step is not None:
            try:  # noqa: SIM105
                self._on_step(step)
            except Exception:  # noqa: BLE001, S110 — a listener must not break the run
                pass

    def _save(self, step: TraceStep, output: Any) -> None:
        from core.agents.models import AgentStep

        AgentStep.objects.create(
            run=self.run,
            seq=self._seq,
            kind=step.kind,
            name=step.name,
            content=(step.content or '')[:20_000],
            arguments=step.arguments or {},
            output={'value': output}
            if output is not None and not isinstance(output, dict)
            else (output or {}),
            metadata=step.metadata or {},
        )

    def _audit(self, step: TraceStep, output: Any) -> None:
        """Audit the RESULT step, not the call step: a `tool_call` step is
        written before the tool runs, so it has no output. The arguments are on
        the AgentStep rows either way. `record_ai_decision` never raises."""
        from core.audit.services import record_ai_decision

        metadata = step.metadata or {}
        record_ai_decision(
            agent=self.agent_name,
            tool=step.name or '',
            run_id=str(self.run.pk),
            args=step.arguments or {},
            output=output,
            duration_ms=metadata.get('duration_ms'),
            model=metadata.get('model', ''),
            provider=metadata.get('provider', ''),
            actor=getattr(self.run, 'customer', None),
            target=f'agent_run/{self.run.pk}',
        )


def _spent(run, provider: Any, usage: RunUsage | None) -> list[str]:
    """Put what the run spent on its row; return the fields that changed."""
    fields: list[str] = []
    if provider is not None:
        run.provider = (getattr(provider, 'name', '') or '')[:50]
        run.model = (getattr(provider, 'model', '') or '')[:100]
        fields += ['provider', 'model']
    if usage is None:
        return fields
    by_model = usage.by_model()
    run.prompt_tokens = sum(pt for pt, _ct in by_model.values())
    run.completion_tokens = sum(ct for _pt, ct in by_model.values())
    fields += ['prompt_tokens', 'completion_tokens']
    # The row is priced by its own model. Keep the split only when another
    # model answered part of the run (the fallback router's secondary).
    if any(model != run.model for model in by_model):
        run.metadata = {
            **(run.metadata or {}),
            USAGE_KEY: {model: [pt, ct] for model, (pt, ct) in by_model.items()},
        }
        fields.append('metadata')
    return fields


def finish(
    run,
    result,
    provider: Any,
    usage: RunUsage | None,
    *,
    duration_ms: int,
    audit_incomplete: bool = False,
) -> None:
    """Write how a run ended. `result` is the runtime's `RunResult`."""
    from django.utils import timezone

    run.state = result.state
    run.final_text = (result.text or '')[:50_000]
    run.error = (result.error or '')[:5_000]
    run.tool_call_count = result.tool_calls
    run.duration_ms = duration_ms
    run.ended_at = timezone.now()
    fields = ['state', 'final_text', 'error', 'tool_call_count', 'duration_ms', 'ended_at']
    fields += _spent(run, provider, usage)
    if audit_incomplete:
        run.metadata = {**(run.metadata or {}), 'audit_incomplete': True}
        fields.append('metadata')
    run.save(update_fields=list(dict.fromkeys(fields)))


def fail(
    run,
    error: str,
    provider: Any = None,
    usage: RunUsage | None = None,
    *,
    duration_ms: int | None = None,
) -> None:
    """Close a run that never returned a result (a timeout, a crash, no agent),
    with whatever it had spent by then."""
    from django.utils import timezone

    run.state = 'failed'
    run.error = (error or '')[:5_000]
    run.ended_at = timezone.now()
    fields = ['state', 'error', 'ended_at']
    if duration_ms is not None:
        run.duration_ms = duration_ms
        fields.append('duration_ms')
    fields += _spent(run, provider, usage)
    run.save(update_fields=list(dict.fromkeys(fields)))


def save_usage(run, provider: Any, usage: RunUsage) -> None:
    """Write only what the run spent. For a run whose row is already closed: a
    timed-out run's thread finishes its last provider call after the caller gave
    up, and those tokens were paid for too."""
    fields = _spent(run, provider, usage)
    if fields:
        run.save(update_fields=list(dict.fromkeys(fields)))


def record_unstored(
    provider: Any,
    usage: RunUsage,
    *,
    counted: dict[str, tuple[int, int]] | None = None,
) -> dict[str, tuple[int, int]]:
    """Count a run that has no row (the daily briefing, or a run whose row could
    not be created) in the day's totals, so the spend cap still sees it. The
    runtime's own calls answer inside `run_scope()`, where the provider guard
    records nothing.

    Returns what the run has spent by now. Pass it back as ``counted`` to count
    the same run again later (a timed-out run's thread ends after its caller
    gave up): only what is new is added.
    """
    from core.agents.guardrails import record_model_usage

    own = getattr(provider, 'model', '') or ''
    spent = usage.by_model()
    for model, (pt, ct) in spent.items():
        done_pt, done_ct = (counted or {}).get(model, (0, 0))
        record_model_usage(model or own, pt - done_pt, ct - done_ct)
    return spent
