"""Spawn tools — Linda fans out parallel Workers and collects their results.

Replaces the old single-shot `delegate.invoke_agent` pattern. Three tools:

  - ``delegate.spawn_workers(jobs=[{objective, context?}, …])``
      Pre-creates an AgentRun row per job, kicks off a daemon thread per
      job, and returns ``run_ids`` immediately so Linda can do other
      work while they churn.

  - ``delegate.poll_workers(run_ids=[…])``
      Non-blocking. Returns current ``state`` + ``final_text`` per run.

  - ``delegate.wait_for_workers(run_ids=[…], timeout_s=120)``
      Blocks until every run is in a terminal state or ``timeout_s``
      elapses, whichever comes first.

The threads run the same kernel runtime that powers Linda herself —
the only difference is each thread carries its own AgentRun row.
Tools the Worker can call are bounded by:

  1. The Worker's declared scopes (set on the class).
  2. (Future) the caller-token's scope set, passed through ``context``.

Compatibility: a thin ``delegate.invoke_agent(agent_name, objective)``
shim is exposed by ``core.assistant.tools.delegate`` — it calls
``spawn_workers`` + ``wait_for_workers`` so old code paths keep working.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any

from core.assistant.tools.filesystem import ToolError, ToolResult, tool

logger = logging.getLogger('morpheus.assistant.spawn')


def _reflect(run) -> None:
    """Post-run reflection (learning loop) — best-effort, after the terminal
    state is saved so pollers never wait on it. See core/assistant/reflection.py."""
    try:
        from core.assistant.reflection import reflect_on_worker_run

        reflect_on_worker_run(run)
    except Exception:  # noqa: BLE001 — reflection must never affect the run
        logger.debug('spawn: reflection skipped for %s', run.id, exc_info=True)


def _execute_worker_run(  # noqa: PLR0915
    *,
    run_id: str,
    objective: str,
    context: dict[str, Any],
    skills: tuple[str, ...] = (),
) -> None:
    """Run the Worker agent for a pre-created AgentRun row.

    Runs inline (no further threading) — caller is already on a worker
    thread. All exceptions are caught and persisted onto the run row so
    the caller (poll_workers) can surface them.

    If `skills` is non-empty, a fresh Worker instance is constructed with
    those skill names assigned to `uses_skills` — the system prompt then
    picks up the relevant skill preludes and the tool list narrows to
    the skill's tool set ∪ default tools.
    """
    from django.db import DatabaseError
    from django.utils import timezone

    from core.agents import (
        AgentRuntime,
        agent_registry,
        get_llm_provider,
    )
    from plugins.installed.agent_core.models import AgentRun, AgentStep

    try:
        run = AgentRun.objects.get(id=run_id)
    except AgentRun.DoesNotExist:
        logger.warning('spawn: AgentRun %s vanished before worker started', run_id)
        return

    agent = agent_registry.get_agent('worker')
    if agent is None:
        run.state = 'failed'
        run.error = 'worker agent not registered'
        run.ended_at = timezone.now()
        run.save(update_fields=['state', 'error', 'ended_at'])
        return

    # Per-job skill narrowing — instantiate a fresh Worker so the
    # `uses_skills` override doesn't leak across sibling threads.
    if skills:
        agent = type(agent)()
        agent.uses_skills = tuple(skills)

    seq = {'i': 0}

    def _mirror(step) -> None:
        seq['i'] += 1
        try:
            output = step.output
            if output is not None and not isinstance(output, (dict, list, str, int, float, bool)):
                output = str(output)
            AgentStep.objects.create(
                run=run,
                seq=seq['i'],
                kind=step.kind,
                name=step.name,
                content=(step.content or '')[:20_000],
                arguments=step.arguments or {},
                output={'value': output}
                if output is not None and not isinstance(output, dict)
                else (output or {}),
                metadata=step.metadata or {},
            )
        except DatabaseError as e:  # noqa: BLE001
            logger.warning('spawn: persist step failed: %s', e)

    provider = get_llm_provider(agent.provider, model=agent.model or None)
    runtime = AgentRuntime(agent, provider=provider, on_step=_mirror)

    started = time.monotonic()
    try:
        result = runtime.run(
            user_message=objective,
            history=[],
            context={**(context or {}), 'spawned_by': 'linda'},
            run_id=str(run.id),
        )
    except Exception as e:  # noqa: BLE001 — surface everything onto the row
        logger.error('spawn: worker run %s failed: %s', run_id, e, exc_info=True)
        run.state = 'failed'
        run.error = f'{type(e).__name__}: {e}'[:5_000]
        run.duration_ms = int((time.monotonic() - started) * 1000)
        run.ended_at = timezone.now()
        run.save(update_fields=['state', 'error', 'duration_ms', 'ended_at'])
        _reflect(run)
        return

    run.state = result.state
    run.final_text = (result.text or '')[:50_000]
    run.error = (result.error or '')[:5_000]
    run.tool_call_count = result.tool_calls
    run.prompt_tokens = result.trace.prompt_tokens
    run.completion_tokens = result.trace.completion_tokens
    run.duration_ms = int((time.monotonic() - started) * 1000)
    run.provider = provider.name
    run.model = provider.model or ''
    run.ended_at = timezone.now()
    run.save(
        update_fields=[
            'state',
            'final_text',
            'error',
            'tool_call_count',
            'prompt_tokens',
            'completion_tokens',
            'duration_ms',
            'provider',
            'model',
            'ended_at',
        ]
    )
    _reflect(run)


@tool(
    name='delegate.spawn_workers',
    description=(
        'Fan out N parallel background Workers. Each job carries one focused '
        'objective and optional `skills` list to opt the Worker into specific '
        'capability bundles (e.g. ["seo"], ["crm"], ["inventory"]). Returns '
        'run_ids immediately — use delegate.poll_workers or '
        'delegate.wait_for_workers to collect results.'
    ),
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {
            'jobs': {
                'type': 'array',
                'description': 'List of {objective, skills?, context?} dicts. Up to 6 per call.',
                'items': {
                    'type': 'object',
                    'properties': {
                        'objective': {'type': 'string'},
                        'skills': {
                            'type': 'array',
                            'items': {'type': 'string'},
                            'description': 'Skill names to opt into (e.g. ["seo"]). Narrows the system prompt + may narrow tools.',
                        },
                        'context': {'type': 'object'},
                    },
                    'required': ['objective'],
                },
                'minItems': 1,
                'maxItems': 6,
            },
        },
        'required': ['jobs'],
    },
)
def spawn_workers_tool(*, jobs: list[dict[str, Any]]) -> ToolResult:
    try:
        from plugins.installed.agent_core.models import AgentRun
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'agent_run model unavailable: {e}') from e

    if not jobs:
        raise ToolError('jobs must contain at least one objective')
    if len(jobs) > 6:
        raise ToolError(f'too many jobs ({len(jobs)}); max is 6 per call')

    run_ids: list[str] = []
    started: list[dict[str, str]] = []
    batch_id = str(uuid.uuid4())[:8]

    for i, job in enumerate(jobs):
        objective = (job.get('objective') or '').strip()
        if not objective:
            raise ToolError(f'job {i}: empty objective')
        ctx = job.get('context') or {}
        if not isinstance(ctx, dict):
            raise ToolError(f'job {i}: context must be an object')
        raw_skills = job.get('skills') or []
        if not isinstance(raw_skills, list):
            raise ToolError(f'job {i}: skills must be an array of strings')
        skills = tuple(str(s).strip() for s in raw_skills if str(s).strip())

        run = AgentRun.objects.create(
            agent_name='worker',
            audience='any',
            user_message=objective[:50_000],
            state='running',
            metadata={
                'batch_id': batch_id,
                'spawned_by': 'linda',
                'skills': list(skills),
            },
        )
        run_ids.append(str(run.id))
        started.append(
            {
                'run_id': str(run.id),
                'objective': objective[:120],
                'skills': list(skills),
            }
        )

        t = threading.Thread(
            target=_execute_worker_run,
            kwargs={
                'run_id': str(run.id),
                'objective': objective,
                'context': ctx,
                'skills': skills,
            },
            daemon=True,
            name=f'worker-{run.id}',
        )
        t.start()

    return ToolResult(
        output={'batch_id': batch_id, 'run_ids': run_ids, 'jobs': started},
        display=f'spawned {len(started)} worker(s) (batch {batch_id})',
    )


@tool(
    name='delegate.poll_workers',
    description=(
        'Check the status of background Workers without blocking. Returns a '
        'list of {run_id, state, final_text, error} — state is one of '
        'queued / running / completed / failed.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'run_ids': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'AgentRun IDs returned by delegate.spawn_workers.',
            },
        },
        'required': ['run_ids'],
    },
)
def poll_workers_tool(*, run_ids: list[str]) -> ToolResult:
    if not run_ids:
        return ToolResult(output={'runs': []}, display='no run_ids supplied')

    try:
        from plugins.installed.agent_core.models import AgentRun
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'agent_run model unavailable: {e}') from e

    rows = list(
        AgentRun.objects.filter(id__in=run_ids).values(
            'id',
            'state',
            'final_text',
            'error',
            'duration_ms',
            'tool_call_count',
        )
    )
    by_id = {str(r['id']): r for r in rows}
    out = []
    for rid in run_ids:
        r = by_id.get(rid)
        if r is None:
            out.append({'run_id': rid, 'state': 'unknown', 'final_text': '', 'error': 'not found'})
            continue
        out.append(
            {
                'run_id': str(r['id']),
                'state': r['state'],
                'final_text': r['final_text'] or '',
                'error': r['error'] or '',
                'duration_ms': r['duration_ms'],
                'tool_call_count': r['tool_call_count'],
            }
        )

    pending = sum(1 for r in out if r['state'] in ('queued', 'running'))
    done = len(out) - pending
    return ToolResult(
        output={'runs': out, 'pending': pending, 'done': done},
        display=f'{done}/{len(out)} done · {pending} pending',
    )


@tool(
    name='delegate.wait_for_workers',
    description=(
        'Block until every Worker reaches a terminal state (completed / '
        'failed) or `timeout_s` elapses. Polls every 500ms. Use this when '
        'you need the results before continuing.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'run_ids': {'type': 'array', 'items': {'type': 'string'}},
            'timeout_s': {
                'type': 'number',
                'description': 'Hard cap, default 120s, max 300s.',
            },
        },
        'required': ['run_ids'],
    },
)
def wait_for_workers_tool(*, run_ids: list[str], timeout_s: float = 120.0) -> ToolResult:
    if not run_ids:
        return ToolResult(output={'runs': []}, display='no run_ids supplied')

    timeout_s = max(1.0, min(float(timeout_s), 300.0))
    try:
        from plugins.installed.agent_core.models import AgentRun
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'agent_run model unavailable: {e}') from e

    terminal = {'completed', 'failed'}
    deadline = time.monotonic() + timeout_s
    while True:
        rows = list(
            AgentRun.objects.filter(id__in=run_ids).values(
                'id',
                'state',
                'final_text',
                'error',
                'duration_ms',
                'tool_call_count',
            )
        )
        states = {str(r['id']): r['state'] for r in rows}
        if all(states.get(rid) in terminal for rid in run_ids):
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(0.5)

    by_id = {str(r['id']): r for r in rows}
    out = []
    for rid in run_ids:
        r = by_id.get(rid)
        if r is None:
            out.append({'run_id': rid, 'state': 'unknown', 'final_text': '', 'error': 'not found'})
            continue
        out.append(
            {
                'run_id': str(r['id']),
                'state': r['state'],
                'final_text': r['final_text'] or '',
                'error': r['error'] or '',
                'duration_ms': r['duration_ms'],
                'tool_call_count': r['tool_call_count'],
            }
        )

    timed_out = sum(1 for r in out if r['state'] in ('queued', 'running'))
    return ToolResult(
        output={'runs': out, 'timed_out': timed_out, 'timeout_s': timeout_s},
        display=(
            f'all {len(out)} done in <={int(timeout_s)}s'
            if timed_out == 0
            else f'{len(out) - timed_out}/{len(out)} done · {timed_out} still running after {int(timeout_s)}s'
        ),
    )
