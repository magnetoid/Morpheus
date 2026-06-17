"""
AgentRuntime — the tool-use loop.

This is the single piece of code that takes a user message, drives an
LLM, dispatches tool calls, and either returns a final answer or hands
back partial state to a UI.

Loop sketch::

    msgs = [system, user]
    for step in range(max_steps):
        response = provider.respond(messages=msgs, tools=tools)
        if response.tool_calls:
            for tc in response.tool_calls:
                check_scope(tc, agent.scopes)
                fire('agent.tool.calling', ...) → may transform args
                result = tool.invoke(tc.arguments, agent=agent, context=context)
                fire('agent.tool.called', ...)
                msgs.append(LLMMessage(role='tool', tool_call_id=tc.id, content=...))
            continue
        return response.text
    raise RuntimeError('max_steps exceeded')

Failure isolation: a single tool error becomes a tool result the LLM can
recover from. Only fatal infra errors (LLM provider down, OOB cancel,
budget exceeded) abort the run.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from core.agents.base import MorpheusAgent
from core.agents.compaction import compact
from core.agents.events import AgentEvents
from core.agents.llm import LLMMessage, LLMProvider, LLMToolCall, get_llm_provider
from core.agents.policies import BudgetExceeded, ScopeDenied, enforce_budget, enforce_policy
from core.agents.tools import Tool, ToolError, ToolResult
from core.agents.trace import AgentTrace, TraceStep
from core.hooks import hook_registry

logger = logging.getLogger('morpheus.agents.runtime')


@dataclass(slots=True)
class RunResult:
    run_id: str
    text: str
    state: str  # 'completed' | 'failed' | 'cancelled' | 'awaiting_approval'
    trace: AgentTrace
    tool_calls: int = 0
    error: str = ''
    metadata: dict[str, Any] = field(default_factory=dict)


def _to_json_for_llm(value: Any) -> str:
    """Serialise a tool's output so the LLM can read it back."""
    try:
        return json.dumps(value, default=str, ensure_ascii=False)[:8000]
    except (TypeError, ValueError):
        return str(value)[:8000]


class AgentRuntime:
    """Runs one agent against one user message.

    Construct with the agent and (optionally) a provider override; reuse
    across runs is fine, runtime holds no per-run state of its own.
    """

    def __init__(
        self,
        agent: MorpheusAgent,
        *,
        provider: LLMProvider | None = None,
        on_step: Callable[[TraceStep], None] | None = None,
        approval_check: Callable[[Tool, dict[str, Any]], bool] | None = None,
    ) -> None:
        self.agent = agent
        self.provider = provider or get_llm_provider(agent.provider, model=agent.model or None)
        self._on_step = on_step
        self._approval_check = approval_check

    # ── Public entry point ─────────────────────────────────────────────────────

    def run(
        self,
        *,
        user_message: str,
        history: list[LLMMessage] | None = None,
        context: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> RunResult:
        """Run the agent against `user_message`. Returns when the loop completes."""
        context = dict(context or {})
        run_id = run_id or str(uuid.uuid4())
        trace = AgentTrace(run_id=run_id, subscriber=self._on_step)

        try:
            self.agent.on_run_start(run=run_id, context=context)
        except Exception as e:  # noqa: BLE001 — agent hooks must not break the run
            logger.warning('agent %s: on_run_start failed: %s', self.agent.name, e)

        hook_registry.fire(
            AgentEvents.RUN_STARTED,
            agent=self.agent.name,
            run_id=run_id,
            context=context,
            user_message=user_message,
        )

        tools = self.agent.get_tools()
        tools_by_name = {t.name: t for t in tools}

        messages: list[LLMMessage] = []
        system_text = self.agent.get_system_prompt(context=context)
        if system_text:
            messages.append(LLMMessage(role='system', content=system_text))
            trace.push(TraceStep(kind='system', content=system_text))
        for prior in history or []:
            messages.append(prior)
        messages.append(LLMMessage(role='user', content=user_message))
        trace.push(TraceStep(kind='user', content=user_message))

        tool_call_count = 0

        for _step in range(max(1, self.agent.max_steps)):
            # Context compaction — keep `messages` under a soft token budget by
            # summarizing the oldest turns. No-op for short conversations.
            messages = compact(messages, summarizer=self._summarize_history)

            # Token-budget guard — abort before the provider call that would
            # cross the agent's cap (0 = unlimited). Tokens accumulate on the
            # trace as the run proceeds.
            try:
                enforce_budget(
                    spent=trace.total_tokens(),
                    cap=self.agent.token_budget or None,
                )
            except BudgetExceeded:
                return self._fail(trace, run_id, context, 'budget_exceeded')

            try:
                response = self.provider.respond(
                    messages=messages,
                    tools=tools,
                    temperature=self.agent.temperature,
                    max_tokens=self.agent.max_tokens,
                )
            except Exception as e:  # noqa: BLE001 — provider failure aborts the run
                return self._fail(trace, run_id, context, _humanise_provider_error(e))

            trace.prompt_tokens += response.prompt_tokens
            trace.completion_tokens += response.completion_tokens

            if not response.tool_calls:
                # Final answer.
                final_text = response.text or ''
                trace.push(TraceStep(kind='final', content=final_text))
                trace.ended_at = trace.steps[-1].at
                hook_registry.fire(
                    AgentEvents.RUN_COMPLETED,
                    agent=self.agent.name,
                    run_id=run_id,
                    text=final_text,
                    tokens=trace.total_tokens(),
                )
                result = RunResult(
                    run_id=run_id,
                    text=final_text,
                    state='completed',
                    trace=trace,
                    tool_calls=tool_call_count,
                )
                self._on_end(run_id, context, result)
                return result

            # Append the assistant turn (tool-calling), then dispatch each tool.
            messages.append(
                LLMMessage(
                    role='assistant',
                    content=response.text or '',
                    tool_calls=response.tool_calls,
                )
            )
            trace.push(
                TraceStep(
                    kind='assistant',
                    content=response.text or '',
                    metadata={'tool_calls': len(response.tool_calls)},
                )
            )

            for tc in response.tool_calls:
                tool_call_count += 1
                self._dispatch_tool(
                    tc=tc,
                    tools_by_name=tools_by_name,
                    trace=trace,
                    messages=messages,
                    context=context,
                    run_id=run_id,
                )

        return self._fail(trace, run_id, context, 'max_steps_exceeded')

    # ── Internals ──────────────────────────────────────────────────────────────

    def _dispatch_tool(  # noqa: PLR0911 — flat tool-dispatch guard chain
        self,
        *,
        tc: LLMToolCall,
        tools_by_name: dict[str, Tool],
        trace: AgentTrace,
        messages: list[LLMMessage],
        context: dict[str, Any],
        run_id: str,
    ) -> None:
        if tc.parse_error:
            self._tool_back(trace, messages, tc, error=tc.parse_error)
            return

        tool = tools_by_name.get(tc.name)
        if tool is None:
            self._tool_back(trace, messages, tc, error=f'Unknown tool: {tc.name}')
            return

        try:
            enforce_policy(scopes=self.agent.scopes, required=tool.scopes)
        except ScopeDenied as e:
            self._tool_back(trace, messages, tc, error=str(e))
            return

        # Filter hook — handlers can transform arguments or veto by raising.
        try:
            args = hook_registry.filter(
                AgentEvents.TOOL_CALLING,
                value=dict(tc.arguments or {}),
                agent=self.agent.name,
                tool=tc.name,
                run_id=run_id,
            )
        except Exception as e:  # noqa: BLE001
            self._tool_back(trace, messages, tc, error=f'tool_call_vetoed: {e}')
            return

        # Approval gate.
        if (tool.requires_approval or self.agent.requires_approval) and self._approval_check:
            try:
                approved = bool(self._approval_check(tool, args))
            except Exception as e:  # noqa: BLE001
                self._tool_back(trace, messages, tc, error=f'approval_check_failed: {e}')
                return
            if not approved:
                trace.push(
                    TraceStep(
                        kind='tool_call',
                        name=tc.name,
                        arguments=args,
                        metadata={'rejected': True},
                    )
                )
                self._tool_back(trace, messages, tc, error='not_approved_by_user')
                hook_registry.fire(
                    AgentEvents.STEP_REJECTED,
                    agent=self.agent.name,
                    tool=tc.name,
                    run_id=run_id,
                    arguments=args,
                )
                return

        trace.push(TraceStep(kind='tool_call', name=tc.name, arguments=args))

        try:
            result: ToolResult = tool.invoke(
                args,
                agent=self.agent,
                context=context,
                request=context.get('request'),
                customer=context.get('customer'),
            )
        except ToolError as e:
            self._tool_back(trace, messages, tc, error=str(e))
            hook_registry.fire(
                AgentEvents.TOOL_FAILED,
                agent=self.agent.name,
                tool=tc.name,
                run_id=run_id,
                error=str(e),
            )
            return

        payload = _to_json_for_llm(result.output)
        messages.append(
            LLMMessage(
                role='tool',
                tool_call_id=tc.id,
                name=tc.name,
                content=payload,
            )
        )
        trace.push(
            TraceStep(
                kind='tool_result',
                name=tc.name,
                output=result.output,
                content=result.display,
                metadata=result.metadata,
            )
        )
        hook_registry.fire(
            AgentEvents.TOOL_CALLED,
            agent=self.agent.name,
            tool=tc.name,
            run_id=run_id,
            arguments=args,
            output=result.output,
        )

    def _tool_back(
        self,
        trace: AgentTrace,
        messages: list[LLMMessage],
        tc: LLMToolCall,
        *,
        error: str,
    ) -> None:
        """Send an error back to the LLM as a tool result so it can recover."""
        body = json.dumps({'error': error})
        messages.append(
            LLMMessage(
                role='tool',
                tool_call_id=tc.id,
                name=tc.name,
                content=body,
            )
        )
        trace.push(
            TraceStep(
                kind='tool_result',
                name=tc.name,
                output={'error': error},
                content=error,
                metadata={'failed': True},
            )
        )

    def _fail(
        self,
        trace: AgentTrace,
        run_id: str,
        context: dict[str, Any],
        error: str,
    ) -> RunResult:
        trace.push(TraceStep(kind='error', content=error))
        if not trace.ended_at and trace.steps:
            trace.ended_at = trace.steps[-1].at
        hook_registry.fire(
            AgentEvents.RUN_FAILED,
            agent=self.agent.name,
            run_id=run_id,
            error=error,
        )
        result = RunResult(
            run_id=run_id,
            text='',
            state='failed',
            trace=trace,
            error=error,
        )
        self._on_end(run_id, context, result)
        return result

    def _summarize_history(self, transcript: str) -> str:
        """Provider-backed summarizer for context compaction. A terse, low-cost
        call; on any failure the caller (`compact`) falls back to truncation."""
        resp = self.provider.respond(
            messages=[
                LLMMessage(
                    role='system',
                    content=(
                        'Summarize the following agent transcript in a few sentences. '
                        'Preserve facts established, decisions made, and tasks still '
                        'pending. Be concise.'
                    ),
                ),
                LLMMessage(role='user', content=transcript[:12000]),
            ],
            tools=None,
            temperature=0.0,
            max_tokens=300,
        )
        return resp.text or ''

    def _on_end(self, run_id: str, context: dict[str, Any], result: RunResult) -> None:
        try:
            self.agent.on_run_end(run=run_id, context=context, result=result)
        except Exception as e:  # noqa: BLE001
            logger.warning('agent %s: on_run_end failed: %s', self.agent.name, e)


def _humanise_provider_error(exc: Exception) -> str:
    """Turn a raw provider exception into a short, actionable chat message.

    Most calls land here from openai-compat clients (OpenAI, OpenRouter)
    or our REST wrappers (Gemini, Ollama). We unwrap the upstream JSON
    body when it carries a useful detail (rate-limited, model not
    found, bad key) and fall back to the exception text otherwise.
    """
    s = str(exc) or exc.__class__.__name__
    low = s.lower()
    if 'rate-limit' in low or 'rate limit' in low or '429' in low:
        return (
            'The selected model is rate-limited upstream. '
            'Pick a different model in Settings → AI providers, or add a '
            'paid OpenRouter key for higher limits.'
        )
    if '401' in low or 'invalid api key' in low or 'incorrect api key' in low:
        return (
            'The provider rejected the API key. Re-check it in Settings '
            '→ AI providers and click Save.'
        )
    if 'model_not_found' in low or 'no such model' in low or '404' in low:
        return (
            'The selected model is not available on this provider. '
            'Pick a different one in Settings → AI providers.'
        )
    if 'connection' in low or 'timed out' in low or 'timeout' in low:
        return (
            'Connection to the AI provider failed. Check the base URL '
            'in Settings → AI providers (or your network) and retry.'
        )
    return f'AI provider error: {s[:300]}'
