"""
agent_core services — bridge between the kernel runtime and persistence.

The kernel `AgentRuntime` doesn't know about Django models. This module
wraps a run with two responsibilities:

1. Mirror every TraceStep into AgentStep rows (lossless audit).
2. Update the AgentRun row with final state, tokens, duration.

It also provides helpers for the chat surface: persisting conversations,
loading message history, dispatching runs to Celery for proactive agents.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterable
from typing import Any

from django.db import DatabaseError, transaction
from django.utils import timezone


def _run_with_timeout(*, runtime, user_message, history, context, run_id, timeout):
    """Execute `runtime.run(...)` on a worker thread; raise TimeoutError on cap.

    Python can't truly kill a stuck thread, so the worker thread keeps
    running after timeout — but the caller gets a clean error and the
    request returns. The runaway thread will end on its next yield.

    In tests we run inline — SQLite test transactions don't share across
    threads and we don't need real wall-clock enforcement.
    """
    import sys as _sys

    if 'test' in _sys.argv or _sys.argv[0].endswith('pytest'):
        return runtime.run(
            user_message=user_message,
            history=history,
            context=context,
            run_id=run_id,
        )

    box: dict[str, Any] = {}
    # Stamp a cooperative deadline the runtime loop polls. join() below can't
    # KILL the worker thread when it times out — the thread is orphaned and,
    # without this, keeps driving the LLM and executing (writing) tools for
    # every remaining step. The deadline makes it stop at its next checkpoint
    # instead of running on as a zombie (deep-debug #6).
    context = {**(context or {}), 'deadline': time.monotonic() + timeout}

    def _wrap():
        try:
            box['result'] = runtime.run(
                user_message=user_message,
                history=history,
                context=context,
                run_id=run_id,
            )
        except BaseException as e:  # noqa: BLE001 — capture for the main thread
            box['error'] = e

    t = threading.Thread(target=_wrap, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise TimeoutError(f'agent runtime exceeded {timeout}s')
    if 'error' in box:
        raise box['error']
    return box['result']


from core.agents import (  # noqa: E402 — deliberate late import
    AgentRuntime,
    LLMMessage,
    MorpheusAgent,
    RunResult,
    TraceStep,
    agent_registry,
    get_llm_provider,
)

logger = logging.getLogger('morpheus.agents.services')


def _persist_step(*, run, seq: int, step: TraceStep) -> None:
    from plugins.installed.agent_core.models import AgentStep

    output = step.output
    if output is not None and not isinstance(output, (dict, list, str, int, float, bool)):
        output = str(output)
    AgentStep.objects.create(
        run=run,
        seq=seq,
        kind=step.kind,
        name=step.name,
        content=step.content[:20_000] if step.content else '',
        arguments=step.arguments or {},
        output={'value': output}
        if output is not None and not isinstance(output, dict)
        else (output or {}),
        metadata=step.metadata or {},
    )

    # Audit on the RESULT step, not the call step: a `tool_call` TraceStep is
    # pre-invocation, so its output is always None — every agents.decision
    # row used to carry an empty `output`. The tool_result step has the real
    # outcome (args live on the AgentStep rows either way).
    if step.kind == 'tool_result':
        from core.audit.services import record_ai_decision

        record_ai_decision(
            agent=getattr(run, 'agent_name', '') or '',
            tool=step.name or '',
            run_id=str(run.pk),
            args=step.arguments or {},
            output=output
            if isinstance(output, (dict, list, str, int, float, bool))
            else str(output),
            duration_ms=(step.metadata or {}).get('duration_ms'),
            model=(step.metadata or {}).get('model', ''),
            provider=(step.metadata or {}).get('provider', ''),
            actor=getattr(run, 'customer', None),
            target=f'agent_run/{run.pk}',
        )


def run_agent(  # noqa: PLR0915
    *,
    agent_name: str,
    user_message: str,
    customer: Any | None = None,
    session_key: str = '',
    history: Iterable[LLMMessage] | None = None,
    context: dict[str, Any] | None = None,
    conversation_id: str | None = None,
    on_step: Any = None,
) -> RunResult:
    """Run a registered agent and persist the trace.

    Returns the in-memory `RunResult` so callers can stream the final
    text + steps; the database mirror is updated as the run progresses.
    """
    agent: MorpheusAgent | None = agent_registry.get_agent(agent_name)
    if agent is None:
        raise LookupError(f'Unknown agent: {agent_name}')

    from plugins.installed.agent_core.models import (
        AgentConversation,
        AgentMessage,
        AgentRun,
    )

    customer_obj = (
        customer
        if (customer is not None and getattr(customer, 'is_authenticated', False))
        else None
    )

    try:
        run = AgentRun.objects.create(
            agent_name=agent.name,
            audience=agent.audience,
            customer=customer_obj,
            session_key=session_key[:64],
            user_message=user_message[:50_000],
            state='running',
            metadata=context.get('metadata', {}) if context else {},
        )
    except DatabaseError as e:
        logger.warning('agent_core: AgentRun create failed, running in-memory: %s', e)
        run = None

    # Subscriber → mirror into DB live.
    seq_counter = {'i': 0}
    audit_incomplete = {'value': False}
    db_subscriber = None
    if run is not None:

        def _mirror(step: TraceStep) -> None:
            seq_counter['i'] += 1
            try:
                _persist_step(run=run, seq=seq_counter['i'], step=step)
            except DatabaseError as e:  # noqa: BLE001
                audit_incomplete['value'] = True
                logger.warning('agent_core: persist step failed: %s', e)
            if on_step is not None:
                try:  # noqa: SIM105
                    on_step(step)
                except Exception:  # noqa: BLE001, S110
                    pass

        db_subscriber = _mirror

    provider = get_llm_provider(agent.provider, model=agent.model or None)
    runtime = AgentRuntime(
        agent,
        provider=provider,
        on_step=db_subscriber or on_step,
    )

    started = time.monotonic()
    timeout_seconds = float((context or {}).get('timeout_seconds') or 45.0)
    try:
        result = _run_with_timeout(
            runtime=runtime,
            user_message=user_message,
            history=list(history or []),
            # `agent_run` gives staged writes their provenance — OpsProposal
            # rows record the run that proposed them (staged-changes design
            # §1/§5). None when the AgentRun row couldn't be created.
            context={**(context or {}), 'customer': customer_obj, 'agent_run': run},
            run_id=str(run.id) if run else None,
            timeout=timeout_seconds,
        )
    except TimeoutError as e:
        logger.warning('agent_core: runtime exceeded %ss: %s', timeout_seconds, e)
        if run is not None:
            run.state = 'failed'
            run.error = f'timeout after {timeout_seconds}s'
            run.ended_at = timezone.now()
            run.save(update_fields=['state', 'error', 'ended_at'])
        raise
    except Exception as e:  # noqa: BLE001 — final safety net
        logger.error('agent_core: runtime crashed: %s', e, exc_info=True)
        if run is not None:
            run.state = 'failed'
            run.error = f'{type(e).__name__}: {e}'
            run.ended_at = timezone.now()
            run.save(update_fields=['state', 'error', 'ended_at'])
        raise

    duration_ms = int((time.monotonic() - started) * 1000)

    if run is not None:
        run.state = result.state
        run.final_text = (result.text or '')[:50_000]
        run.error = (result.error or '')[:5_000]
        run.tool_call_count = result.tool_calls
        run.prompt_tokens = result.trace.prompt_tokens
        run.completion_tokens = result.trace.completion_tokens
        run.duration_ms = duration_ms
        run.provider = provider.name
        run.model = provider.model or ''
        run.ended_at = timezone.now()
        if audit_incomplete['value']:
            md = dict(run.metadata or {})
            md['audit_incomplete'] = True
            run.metadata = md
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
                'metadata',
            ]
        )

    if conversation_id and run is not None:
        try:
            with transaction.atomic():
                conv = AgentConversation.objects.get(id=conversation_id)
                AgentMessage.objects.create(
                    conversation=conv,
                    run=run,
                    role='user',
                    content=user_message[:20_000],
                )
                if result.text:
                    AgentMessage.objects.create(
                        conversation=conv,
                        run=run,
                        role='assistant',
                        content=result.text[:20_000],
                    )
                conv.last_message_at = timezone.now()
                conv.save(update_fields=['last_message_at'])
        except (AgentConversation.DoesNotExist, DatabaseError) as e:
            logger.warning('agent_core: conversation persist failed: %s', e)

    return result


from core.utils.safe_db import safe_db  # noqa: E402 — deliberate late import


@safe_db(default=[])
def history_for_conversation(conversation_id: str, *, limit: int = 20) -> list[LLMMessage]:
    """Load the recent messages of a conversation as `LLMMessage` history."""
    from plugins.installed.agent_core.models import AgentMessage

    rows = list(
        AgentMessage.objects.filter(conversation_id=conversation_id).order_by('-created_at')[:limit]
    )
    rows.reverse()
    return [LLMMessage(role=r.role, content=r.content) for r in rows]
