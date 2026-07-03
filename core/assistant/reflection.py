"""Post-run reflection — Linda's learning loop.

After a background Worker finishes (`spawn._execute_worker_run`), one cheap
no-tools LLM call judges the outcome and extracts durable lessons. The verdict
updates the outcome counters on every LearnedSkill the job used (giving
`uses/successes/failures` their first writer), lessons land in LindaMemory as
low-confidence 'inferred' facts, and observed tool gaps are stored under the
`tool_gap.` key prefix for the self-coding flywheel (Release 3 of
docs/plans/linda-self-learning-2026-07.md). A skill that keeps failing
disables itself and leaves a memory explaining why.

Fail-soft on every layer: reflection can never affect the run's result, and
it is skipped entirely when no real LLM provider is configured.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger('morpheus.assistant.reflection')

_MAX_LESSONS = 2
_SKIP_PROVIDERS = ('mock', 'unconfigured')

_REFLECTION_SYSTEM = (
    'You review one finished background-agent run on a commerce platform. '
    'Judge whether the run achieved its objective, and extract at most '
    f'{_MAX_LESSONS} durable lessons a future agent should remember — stable '
    'facts, preferences, or workflow insights, never a restatement of the '
    'task itself. Also note tool gaps: capabilities the agent clearly needed '
    'but did not have (usually none).\n'
    'Reply with ONLY this JSON, no prose:\n'
    '{"outcome": "success" | "failure" | "unclear",\n'
    ' "lessons": [{"key": "short_snake_case_id", "value": "one sentence"}],\n'
    ' "tool_gaps": ["short description of the missing tool"]}'
)


def _memory_key(raw: str, *, prefix: str = '') -> str:
    """Normalise an LLM-supplied key to a safe LindaMemory key."""
    from django.utils.text import slugify

    slug = slugify(str(raw))[:120].replace('-', '_') or 'unnamed'
    return f'{prefix}{slug}'[:160]


def _remember(key: str, value: str) -> None:
    """Write one inferred fact, embedding it like `memory.remember` does."""
    from core.assistant.models import LindaMemory
    from core.embeddings import embed

    value = (value or '').strip()[:5000]
    LindaMemory.objects.update_or_create(
        scope='merchant',
        key=key,
        defaults={
            'value': value,
            'source': 'inferred',
            'embedding': embed(f'{key}: {value}'),
        },
    )


def _record_tool_gap(gap: str) -> None:
    """Store a tool gap, keeping a `seen=N` counter in the value so the
    Release-3 flywheel can act on gaps observed more than once."""
    from core.assistant.models import LindaMemory
    from core.embeddings import embed

    gap = (gap or '').strip()[:400]
    if not gap:
        return
    key = _memory_key(gap, prefix='tool_gap.')
    obj, created = LindaMemory.objects.get_or_create(
        scope='merchant',
        key=key,
        defaults={
            'value': f'seen=1 · {gap}',
            'source': 'inferred',
            'embedding': embed(f'{key}: {gap}'),
        },
    )
    if not created:
        m = re.match(r'seen=(\d+)', obj.value or '')
        n = (int(m.group(1)) + 1) if m else 2
        obj.value = f'seen={n} · {gap}'
        obj.source = 'inferred'
        obj.save(update_fields=['value', 'source', 'updated_at'])


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
        _remember(
            _memory_key(name, prefix='skill_disabled.'),
            f'Learned skill "{row.label or name}" was auto-disabled: '
            f'{row.successes}/{row.uses} runs succeeded '
            f'({row.success_rate():.0%}). Tell the merchant if they ask '
            'why it stopped being used.',
        )
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

        lessons = 0
        for lesson in (parsed.get('lessons') or [])[:_MAX_LESSONS]:
            if not isinstance(lesson, dict):
                continue
            value = str(lesson.get('value') or '').strip()
            if not value:
                continue
            _remember(_memory_key(lesson.get('key') or value[:60]), value)
            lessons += 1

        gaps = 0
        for gap in parsed.get('tool_gaps') or []:
            _record_tool_gap(str(gap))
            gaps += 1

        summary = {
            'outcome': outcome,
            'lessons': lessons,
            'tool_gaps': gaps,
            'skills_updated': updated,
            'skills_disabled': disabled,
        }
        logger.info('reflection: run=%s %s', run.id, summary)
        return summary
    except Exception as e:  # noqa: BLE001 — reflection must never hurt the run
        logger.warning('reflection: skipped for run %s: %s', getattr(run, 'id', '?'), e)
        return {'skipped': str(e)[:200]}
