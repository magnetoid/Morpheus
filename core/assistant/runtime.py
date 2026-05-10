"""
Assistant runtime — the chat + tool-use loop.

Self-contained: doesn't import from `plugins.*` or any plugin code at
module-load time. Tools are looked up lazily so a broken plugin tool
doesn't break the Assistant's import.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from core.assistant.persistence import StoredMessage, get_default_store
from core.assistant.prompts import build_system_prompt
from core.assistant.providers import get_default_provider

logger = logging.getLogger('morpheus.assistant')


@dataclass(slots=True)
class AssistantMessage:
    role: str            # 'user' | 'assistant' | 'system' | 'tool'
    content: str = ''
    tool_call_id: str = ''
    tool_calls: list = field(default_factory=list)
    name: str = ''


@dataclass(slots=True)
class AssistantRunResult:
    text: str
    state: str               # 'completed' | 'failed'
    tool_call_count: int = 0
    error: str = ''
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_ms: int = 0


def _format_recent_memories() -> str:
    """Compact bullet list of remembered facts, prepended each turn.
    Empty string when nothing's remembered (or the model isn't migrated yet)."""
    try:
        from core.assistant.tools.memory import get_recent_memories
        rows = get_recent_memories(limit=50)
    except Exception:  # noqa: BLE001
        return ''
    if not rows:
        return ''
    lines = ['REMEMBERED FACTS — apply silently unless asked:']
    for r in rows:
        lines.append(f'  • [{r["scope"]}] {r["key"]}: {r["value"]}')
    return '\n'.join(lines)


def _to_llm_messages(history: list[StoredMessage], user_message: str) -> list[Any]:
    """Convert stored history + new user msg → LLMMessage objects from agents.llm.

    We import lazily so the Assistant survives an agents-kernel import failure;
    we fall back to plain dicts if the agents kernel isn't available.
    """
    try:
        from core.agents.llm import LLMMessage
    except Exception:  # noqa: BLE001
        @dataclass
        class LLMMessage:
            role: str
            content: str = ''
            tool_call_id: str | None = None
            tool_calls: list = field(default_factory=list)
            name: str | None = None

    msgs = [LLMMessage(role='system', content=build_system_prompt())]
    # Inject remembered facts (top of turn) so Linda recalls preferences
    # across sessions without an explicit memory.recall call.
    memo = _format_recent_memories()
    if memo:
        msgs.append(LLMMessage(role='system', content=memo))
    for h in history:
        if h.role == 'tool':
            msgs.append(LLMMessage(
                role='tool', content=json.dumps(h.tool_output, default=str)[:8000],
                name=h.tool_name or '',
            ))
        else:
            msgs.append(LLMMessage(role=h.role, content=h.content))
    msgs.append(LLMMessage(role='user', content=user_message))
    return msgs


class Assistant:
    """Linda — the hardcoded staff AI assistant.

    Construct with optional overrides; call `.run(message, key=...)` to chat.
    """

    name = 'assistant'
    label = 'Linda AI Assistant'
    max_steps = 8

    def __init__(self, *, provider=None, tools=None, store=None,
                 max_steps: int | None = None) -> None:
        self.provider = provider or get_default_provider()
        # Lazy-resolve tools the first time they're needed so a broken
        # tool import doesn't take the Assistant down at construct time.
        self._tools = tools
        self.store = store or get_default_store()
        if max_steps is not None:
            self.max_steps = max_steps

    @property
    def tools(self) -> list:
        if self._tools is None:
            from core.assistant.tools import get_default_tools
            try:
                self._tools = get_default_tools()
            except Exception as e:  # noqa: BLE001
                logger.warning('assistant: tool resolution failed: %s', e)
                self._tools = []
        return self._tools

    def run(
        self,
        *,
        message: str,
        conversation_key: str,
        context: dict[str, Any] | None = None,
    ) -> AssistantRunResult:
        """Run one user turn; persist the exchange; return the result."""
        started = time.monotonic()
        history = self.store.history(conversation_key=conversation_key, limit=30)
        self.store.append(
            conversation_key=conversation_key,
            message=StoredMessage(role='user', content=message[:50_000]),
        )

        msgs = _to_llm_messages(history, message)
        tools = self.tools
        tools_by_name = {t.name: t for t in tools}

        prompt_tokens = 0
        completion_tokens = 0
        tool_calls = 0

        for _step in range(max(1, self.max_steps)):
            try:
                resp = self.provider.respond(
                    messages=msgs, tools=tools or None,
                    temperature=0.2, max_tokens=1500,
                )
            except Exception as e:  # noqa: BLE001
                logger.error('assistant: provider failed: %s', e, exc_info=True)
                err = f'provider_error: {e}'
                self.store.append(
                    conversation_key=conversation_key,
                    message=StoredMessage(role='assistant', content=f'(error) {err}'),
                )
                return AssistantRunResult(
                    text='', state='failed', error=err,
                    prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                    tool_call_count=tool_calls,
                    duration_ms=int((time.monotonic() - started) * 1000),
                )

            prompt_tokens += getattr(resp, 'prompt_tokens', 0) or 0
            completion_tokens += getattr(resp, 'completion_tokens', 0) or 0

            if not getattr(resp, 'tool_calls', None):
                final = resp.text or ''
                self.store.append(
                    conversation_key=conversation_key,
                    message=StoredMessage(role='assistant', content=final[:50_000]),
                )
                return AssistantRunResult(
                    text=final, state='completed',
                    prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                    tool_call_count=tool_calls,
                    duration_ms=int((time.monotonic() - started) * 1000),
                )

            # Append the assistant turn (tool-calling), then dispatch each tool.
            try:
                from core.agents.llm import LLMMessage
            except Exception:  # noqa: BLE001 — already handled above
                LLMMessage = type(msgs[0])
            msgs.append(LLMMessage(
                role='assistant', content=resp.text or '',
                tool_calls=resp.tool_calls,
            ))
            for tc in resp.tool_calls:
                tool_calls += 1
                self._dispatch_tool(
                    tc=tc, tools_by_name=tools_by_name, msgs=msgs,
                    conversation_key=conversation_key, context=context,
                )

        # Loop exhausted.
        self.store.append(
            conversation_key=conversation_key,
            message=StoredMessage(role='assistant', content='(stopped: max steps)'),
        )
        return AssistantRunResult(
            text='', state='failed', error='max_steps_exceeded',
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            tool_call_count=tool_calls,
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    def _dispatch_tool(self, *, tc, tools_by_name, msgs, conversation_key, context):
        """Invoke a single tool call, persist the result, append to LLM context."""
        tool_name = getattr(tc, 'name', '')
        args = getattr(tc, 'arguments', {}) or {}
        tool = tools_by_name.get(tool_name)
        try:
            from core.agents.llm import LLMMessage
        except Exception:  # noqa: BLE001
            LLMMessage = type(msgs[0])

        if tool is None:
            payload = {'error': f'unknown tool: {tool_name}'}
            msgs.append(LLMMessage(role='tool', tool_call_id=getattr(tc, 'id', ''),
                                   name=tool_name, content=json.dumps(payload)))
            self.store.append(
                conversation_key=conversation_key,
                message=StoredMessage(role='tool', tool_name=tool_name,
                                      tool_args=args, tool_output=payload),
            )
            return

        try:
            result = tool.invoke(args, agent=self, context=context or {})
            output = result.output if hasattr(result, 'output') else result
        except Exception as e:  # noqa: BLE001 — never let a tool failure kill the run
            output = {'error': f'{type(e).__name__}: {e}'}
        payload = output if isinstance(output, (dict, list, str, int, float, bool)) else str(output)
        msgs.append(LLMMessage(
            role='tool', tool_call_id=getattr(tc, 'id', ''),
            name=tool_name, content=json.dumps(payload, default=str)[:8000],
        ))
        self.store.append(
            conversation_key=conversation_key,
            message=StoredMessage(role='tool', tool_name=tool_name,
                                  tool_args=args, tool_output=payload),
        )


def run_assistant(*, message: str, conversation_key: str = 'default',
                  context: dict[str, Any] | None = None) -> AssistantRunResult:
    """Module-level convenience: run a single turn against the default Assistant."""
    return Assistant().run(
        message=message, conversation_key=conversation_key, context=context,
    )
