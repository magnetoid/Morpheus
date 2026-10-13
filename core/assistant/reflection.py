"""Post-run reflection — judges a Worker run and updates skill counters.

After a background Worker finishes (`spawn._execute_worker_run`), one cheap
no-tools LLM call judges the outcome. The verdict updates the outcome counters on
every LearnedSkill the job used (giving `uses/successes/failures` their first
writer), and a skill that keeps failing disables itself.

It writes nothing into the shop memory. Generic lessons and tool gaps were once
stored there; that was Janus's job (its own learning, core/assistant/janus_learning.py)
and it polluted the shop memory, which holds only facts about this store
(docs/plans/janus-core-brain-2026-10.md).

Fail-soft on every layer: reflection can never affect the run's result, and
it is skipped entirely when no real LLM provider is configured.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger('morpheus.assistant.reflection')

_SKIP_PROVIDERS = ('mock', 'unconfigured')

_REFLECTION_SYSTEM = (
    'You review one finished background-agent run on a commerce platform. '
    'Judge only whether the run achieved its objective.\n'
    'Reply with ONLY this JSON, no prose:\n'
    '{"outcome": "success" | "failure" | "unclear"}'
)


def _update_skills(run, outcome: str) -> tuple[list[str], list[str]]:
    """Record the run's verdict on every LearnedSkill the job used, via the
    existing ``record_skill_outcome`` (which owns the counters, auto-retire
    threshold, live-registry unregister, and self-improvement signal).
    'unclear' verdicts record nothing. Returns (updated_names, pruned_names)."""
    if outcome not in ('success', 'failure'):
        return [], []
    from core.assistant.tools.skills import record_skill_outcome

    names = [str(s) for s in (run.metadata or {}).get('skills') or []]
    updated: list[str] = []
    pruned_names: list[str] = []
    for name in names:
        res = record_skill_outcome(name, outcome == 'success')
        if res is None:  # not a LearnedSkill (e.g. a built-in bundle) — skip
            continue
        row, pruned = res
        updated.append(name)
        if not pruned:
            continue
        pruned_names.append(name)
        try:
            from core.audit.services import record_ai_decision

            record_ai_decision(
                agent='worker',
                tool='skills.auto_disable',
                run_id=str(run.id),
                args={'skill': name, 'uses': row.uses},
                output={'disabled': True, 'success_rate': round(row.success_rate(), 3)},
            )
        except Exception:  # noqa: BLE001 — audit is best-effort here
            logger.debug('reflection: audit of auto-disable skipped', exc_info=True)
    return updated, pruned_names


def reflect_on_worker_run(run, *, provider=None) -> dict[str, Any]:
    """Reflect on one finished AgentRun. Returns a small summary dict; never
    raises. `provider` is injectable for tests; defaults to the configured one."""
    try:
        if provider is None:
            from core.assistant.providers import get_default_provider

            provider = get_default_provider()
            # Only the RESOLVED default is checked — an explicitly injected
            # provider (tests, evals) is always used, even a mock.
            if getattr(provider, 'name', '') in _SKIP_PROVIDERS:
                return {'skipped': 'no provider configured'}

        from core.agents.llm import LLMMessage
        from core.llm_parsing import parse_llm_json

        user = (
            f'OBJECTIVE:\n{(run.user_message or "")[:2000]}\n\n'
            f'STATE: {run.state}\n'
            f'ERROR: {(run.error or "—")[:1000]}\n\n'
            f'FINAL OUTPUT:\n{(run.final_text or "")[:4000]}'
        )
        resp = provider.respond(
            messages=[
                LLMMessage(role='system', content=_REFLECTION_SYSTEM),
                LLMMessage(role='user', content=user),
            ],
            tools=None,
            temperature=0.0,
            max_tokens=400,
        )
        parsed = parse_llm_json(getattr(resp, 'text', '') or '')
        if not isinstance(parsed, dict):
            return {'skipped': 'unparseable reflection'}

        outcome = str(parsed.get('outcome') or 'unclear').lower()
        if outcome not in ('success', 'failure', 'unclear'):
            outcome = 'unclear'

        updated, disabled = _update_skills(run, outcome)

        summary = {
            'outcome': outcome,
            'skills_updated': updated,
            'skills_disabled': disabled,
        }
        logger.info('reflection: run=%s %s', run.id, summary)
        return summary
    except Exception as e:  # noqa: BLE001 — reflection must never hurt the run
        logger.warning('reflection: skipped for run %s: %s', getattr(run, 'id', '?'), e)
        return {'skipped': str(e)[:200]}
