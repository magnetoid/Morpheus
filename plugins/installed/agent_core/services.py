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


def _run_with_timeout(
    *, runtime, user_message, history, context, run_id, timeout, usage=None, on_late=None
):
    """Execute `runtime.run(...)` on a worker thread; raise TimeoutError on cap.

    Python can't truly kill a stuck thread, so the worker thread keeps
    running after timeout — but the caller gets a clean error and the
    request returns. The runaway thread will end on its next yield, and then
    calls ``on_late`` (in that thread): the provider call that was in flight
    when the caller gave up was paid for, and ``usage`` holds it by then.

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
            usage=usage,
        )

    box: dict[str, Any] = {}
    # Guards the hand-over: either the caller takes the outcome, or the thread
    # learns it was given up on. Never both, never neither.
    handover = threading.Lock()
    # Stamp a cooperative deadline the runtime loop polls. join() below can't
    # KILL the worker thread when it times out — the thread is orphaned and,
    # without this, keeps driving the LLM and executing (writing) tools for
    # every remaining step. The deadline makes it stop at its next checkpoint
    # instead of running on as a zombie (deep-debug #6).
    context = {**(context or {}), 'deadline': time.monotonic() + timeout}

    def _wrap():
        try:
            outcome = (
                'result',
                runtime.run(
                    user_message=user_message,
                    history=history,
                    context=context,
                    run_id=run_id,
                    usage=usage,
                ),
            )
        except BaseException as e:  # noqa: BLE001 — capture for the main thread
            outcome = ('error', e)
        with handover:
            box[outcome[0]] = outcome[1]
            given_up = box.get('given_up', False)
        if given_up and on_late is not None:
            try:
                on_late()
            except Exception:  # noqa: BLE001 — nothing is waiting for this thread
                logger.warning('agent_core: late run %s not recorded', run_id, exc_info=True)

    t = threading.Thread(target=_wrap, daemon=True)
    t.start()
    t.join(timeout)
    with handover:
        if 'result' not in box and 'error' not in box:
            box['given_up'] = True
            raise TimeoutError(f'agent runtime exceeded {timeout}s')
    if 'error' in box:
        raise box['error']
    return box['result']


def _close_thread_connection() -> None:
    """Close the database connection of the thread a timeout left behind."""
    from django.db import connection

    connection.close()


from core.agents import (  # noqa: E402 — deliberate late import
    AgentRuntime,
    LLMMessage,
    MorpheusAgent,
    RunResult,
    get_llm_provider,
    run_store,
)
from core.agents.usage import RunUsage  # noqa: E402 — deliberate late import
from morpheus.core import agent_registry  # noqa: E402 — deliberate late import

logger = logging.getLogger('morpheus.agents.services')


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

    # Steps are saved as they happen; the end of the run, and what it spent,
    # are written by the same module (core/agents/run_store.py).
    mirror = run_store.StepMirror(run, on_step=on_step) if run is not None else None
    usage = RunUsage()

    provider = get_llm_provider(agent.provider, model=agent.model or None)
    runtime = AgentRuntime(
        agent,
        provider=provider,
        on_step=mirror or on_step,
    )

    # The request's thread and the thread a timeout leaves behind may both write
    # what the run spent. One at a time: each reads the meter and saves under the
    # lock, so the later write is never the older reading.
    writing = threading.Lock()
    counted: dict[str, tuple[int, int]] = {}

    def _count() -> None:
        # No row: what is new since the last count goes to the day's totals.
        counted.update(run_store.record_unstored(provider, usage, counted=counted))

    def _late() -> None:
        # Runs in the thread a timeout left behind, once it ends.
        try:
            with writing:
                if run is not None:
                    run_store.save_usage(run, provider, usage)
                else:
                    _count()
        finally:
            _close_thread_connection()

    def _close(error: str) -> None:
        duration = int((time.monotonic() - started) * 1000)
        with writing:
            if run is not None:
                run_store.fail(run, error, provider, usage, duration_ms=duration)
            else:
                _count()

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
            usage=usage,
            on_late=_late,
        )
    except TimeoutError as e:
        logger.warning('agent_core: runtime exceeded %ss: %s', timeout_seconds, e)
        _close(f'timeout after {timeout_seconds}s')
        raise
    except Exception as e:  # noqa: BLE001 — final safety net
        logger.error('agent_core: runtime crashed: %s', e, exc_info=True)
        _close(f'{type(e).__name__}: {e}')
        raise

    duration_ms = int((time.monotonic() - started) * 1000)

    if run is not None:
        run_store.finish(
            run,
            result,
            provider,
            usage,
            duration_ms=duration_ms,
            audit_incomplete=mirror.incomplete,
        )
    else:
        _count()

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


def invocation_denial(agent: MorpheusAgent, request: Any) -> str:
    """Why the caller behind `request` may NOT invoke `agent` ('' = allowed).

    ONE predicate for the REST views and the GraphQL `invokeAgent` mutation —
    two copies drift and the looser one wins. The runtime checks each tool
    against the AGENT's scopes, never the caller's, so invoking an agent hands
    the caller every scope that agent holds. Hence:

    - only a `storefront` agent is public;
    - `merchant` AND `any` need staff. `any` is the generic Worker, which holds
      every merchant scope (customers.search, orders.search, catalog writes…);
      treating it as public gave anonymous visitors a merchant agent;
    - a Bearer token resolves to a SHARED is_staff service user, so it must
      itself hold every scope the agent holds (or the wildcard — see
      agent_mcp/scopes.py), or a narrow token escalates through the agent.
    """
    if agent.audience == 'system':
        return 'System agents cannot be invoked via HTTP.'
    if agent.audience == 'storefront':
        return ''
    user = getattr(request, 'user', None) if request is not None else None
    if not (user and getattr(user, 'is_authenticated', False) and getattr(user, 'is_staff', False)):
        return 'Staff authentication required.'
    token_scopes = getattr(request, '_morph_token_scopes_graphql', None)
    if (
        token_scopes is not None
        and '*' not in token_scopes
        and not set(agent.scopes) <= set(token_scopes)
    ):
        return 'This token does not hold every scope the agent holds.'
    return ''


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
