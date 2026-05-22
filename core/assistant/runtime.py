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


_RETRIABLE_NEEDLES = ('429', 'rate limit', 'rate-limit', 'overloaded',
                      'temporarily', '502', '503', '504', 'timeout',
                      'timed out', 'connection reset')


def _is_retriable(msg: str) -> bool:
    m = (msg or '').lower()
    return any(n in m for n in _RETRIABLE_NEEDLES)


def _friendly_provider_error(raw: str) -> str:
    """Translate a raw provider exception into a user-readable line.

    The dashboard surfaces the assistant's text directly, so a stack
    trace or 200-char JSON blob feels like the platform crashed. Map
    common cases to a short note + a concrete next step.
    """
    text = (raw or '').lower()
    if not text:
        return ('Sorry — I couldn\'t reach the AI provider just now. '
                'Try again in a moment.')
    if '429' in text or 'rate' in text:
        return ('I hit the provider\'s rate limit (the free model is '
                'busy). Try again in ~30s, switch the provider/model in '
                '/dashboard/settings/ai/, or paste your own API key '
                'there to lift the limit.')
    if 'invalid_api_key' in text or 'unauthorized' in text or '401' in text:
        return ('The configured AI key was rejected. Open '
                '/dashboard/settings/ai/ and check the active provider\'s '
                'key.')
    if '402' in text or 'quota' in text or 'insufficient' in text:
        return ('The AI provider says quota / billing is exhausted. '
                'Top it up or switch providers in '
                '/dashboard/settings/ai/.')
    if 'no provider' in text or 'not configured' in text:
        return ('No AI provider is configured yet. Add a key in '
                '/dashboard/settings/ai/ and I\'ll be online.')
    if any(n in text for n in ('502', '503', '504', 'timeout', 'overloaded')):
        return ('The AI provider returned a transient error. Try again '
                'in a moment; if it persists, switch model in '
                '/dashboard/settings/ai/.')
    return f'AI provider error — please try again. ({raw[:140]})'


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


def _page_context_system(context: dict[str, Any] | None) -> str:
    """Compose the one-line system prefix carrying the URL+title of the
    dashboard page Linda was opened from.

    Empty when no page context is provided (CLI / API callers / older
    widget). Kept tiny so it costs near-zero tokens and never derails
    Linda when irrelevant.
    """
    if not context:
        return ''
    url = (context.get('page_url') or '').strip()
    title = (context.get('page_title') or '').strip()
    if not url and not title:
        return ''
    parts = ['You are running in a floating widget on a Morpheus dashboard page.']
    if title:
        parts.append(f'The merchant is viewing: "{title}".')
    if url:
        parts.append(f'Page URL: {url}.')
    parts.append(
        'When the merchant says "this", "this product", "this order", "here", '
        'they mean the row or object on the page above. Prefer to answer in '
        'context of that page; offer to open another dashboard page when a '
        'different surface is the right answer.'
    )
    return ' '.join(parts)


def _to_llm_messages(
    history: list[StoredMessage],
    user_message: str,
    *,
    context: dict[str, Any] | None = None,
) -> list[Any]:
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
    # Inject the page context (URL + title) if the caller supplied one
    # so Linda can answer about "this product / order / page".
    page_ctx = _page_context_system(context)
    if page_ctx:
        msgs.append(LLMMessage(role='system', content=page_ctx))
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
        """Run one user turn; persist the exchange; return the result.

        Implemented as a thin consumer of :meth:`stream` so the JSON
        endpoint keeps working without duplicating loop logic.
        """
        result = AssistantRunResult(text='', state='failed', error='no_events')
        for event in self.stream(message=message,
                                 conversation_key=conversation_key, context=context):
            kind = event.get('type')
            if kind == 'final':
                result = event['result']
            elif kind == 'error':
                result = event['result']
        return result

    def stream(
        self,
        *,
        message: str,
        conversation_key: str,
        context: dict[str, Any] | None = None,
    ):
        """Generator that yields events as the turn progresses.

        Event types (each is a dict):
          * ``{type: 'tool_call_started', name, arguments}``
          * ``{type: 'tool_call_finished', name, output, error?}``
          * ``{type: 'assistant_text', text}`` — interim assistant text
            (per-step, not per-token; provider-side streaming arrives later).
          * ``{type: 'final', result: AssistantRunResult}``
          * ``{type: 'error', result: AssistantRunResult}``
        """
        started = time.monotonic()
        history = self.store.history(conversation_key=conversation_key, limit=30)
        self.store.append(
            conversation_key=conversation_key,
            message=StoredMessage(role='user', content=message[:50_000]),
        )

        msgs = _to_llm_messages(history, message, context=context)
        # Tool-palette scoping (core/assistant/modes.py). The merchant
        # picks a mode per conversation from the chat header chip; it
        # arrives in `context['mode']`. Filter Linda's tool catalogue
        # by the mode's scope whitelist BEFORE passing it to the LLM,
        # so she can't pick a refund tool during a "sales" convo.
        # Unknown / missing mode → general (wildcard) — full access.
        from core.assistant.modes import filter_tools_by_mode, get_mode
        mode_slug = ''
        if context and isinstance(context, dict):
            mode_slug = str(context.get('mode') or '').strip().lower()
        active_mode = get_mode(mode_slug)
        tools = filter_tools_by_mode(self.tools, mode_slug)
        tools_by_name = {t.name: t for t in tools}
        logger.info(
            'assistant: mode=%s tool_count=%d/%d conversation=%s',
            active_mode.slug, len(tools), len(self.tools), conversation_key,
        )

        prompt_tokens = 0
        completion_tokens = 0
        tool_calls = 0

        for _step in range(max(1, self.max_steps)):
            resp = None
            err: str = ''
            for attempt in (0, 1):  # one retry for transient errors
                try:
                    resp = self.provider.respond(
                        messages=msgs, tools=tools or None,
                        temperature=0.2, max_tokens=1500,
                    )
                    err = ''
                    break
                except Exception as e:  # noqa: BLE001
                    err = str(e)
                    logger.warning(
                        'assistant: provider attempt %d failed: %s',
                        attempt + 1, err,
                    )
                    if attempt == 0 and _is_retriable(err):
                        time.sleep(1.0)
                        continue
                    break

            if resp is None:
                friendly = _friendly_provider_error(err)
                self.store.append(
                    conversation_key=conversation_key,
                    message=StoredMessage(role='assistant', content=friendly),
                )
                yield {'type': 'error', 'result': AssistantRunResult(
                    text=friendly, state='failed', error=err,
                    prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                    tool_call_count=tool_calls,
                    duration_ms=int((time.monotonic() - started) * 1000),
                )}
                return

            prompt_tokens += getattr(resp, 'prompt_tokens', 0) or 0
            completion_tokens += getattr(resp, 'completion_tokens', 0) or 0

            if not getattr(resp, 'tool_calls', None):
                final = resp.text or ''
                self.store.append(
                    conversation_key=conversation_key,
                    message=StoredMessage(role='assistant', content=final[:50_000]),
                )
                yield {'type': 'final', 'result': AssistantRunResult(
                    text=final, state='completed',
                    prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                    tool_call_count=tool_calls,
                    duration_ms=int((time.monotonic() - started) * 1000),
                )}
                return

            # Interim assistant text (when a model says something before its
            # tool call — pre-tool reasoning).
            if (resp.text or '').strip():
                yield {'type': 'assistant_text', 'text': resp.text}

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
                tc_name = getattr(tc, 'name', '') or (
                    tc.get('name') if isinstance(tc, dict) else ''
                )
                tc_args = getattr(tc, 'arguments', None) or (
                    tc.get('arguments') if isinstance(tc, dict) else {}
                )
                yield {
                    'type': 'tool_call_started',
                    'name': tc_name, 'arguments': tc_args or {},
                }
                tool_output, tool_error = self._dispatch_tool(
                    tc=tc, tools_by_name=tools_by_name, msgs=msgs,
                    conversation_key=conversation_key, context=context,
                )
                yield {
                    'type': 'tool_call_finished',
                    'name': tc_name,
                    'output': tool_output,
                    'error': tool_error,
                }

        # Loop exhausted.
        self.store.append(
            conversation_key=conversation_key,
            message=StoredMessage(role='assistant', content='(stopped: max steps)'),
        )
        yield {'type': 'error', 'result': AssistantRunResult(
            text='', state='failed', error='max_steps_exceeded',
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            tool_call_count=tool_calls,
            duration_ms=int((time.monotonic() - started) * 1000),
        )}

    def _dispatch_tool(self, *, tc, tools_by_name, msgs, conversation_key, context):
        """Invoke a single tool call, persist the result, append to LLM context.
        Returns ``(output, error_message)`` so :meth:`stream` can echo the
        outcome out to the SSE client.
        """
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
            return payload, payload['error']

        error_msg = ''
        try:
            result = tool.invoke(args, agent=self, context=context or {})
            output = result.output if hasattr(result, 'output') else result
        except Exception as e:  # noqa: BLE001 — never let a tool failure kill the run
            output = {'error': f'{type(e).__name__}: {e}'}
            error_msg = output['error']
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
        return payload, error_msg


def run_assistant(*, message: str, conversation_key: str = 'default',
                  context: dict[str, Any] | None = None) -> AssistantRunResult:
    """Module-level convenience: run a single turn against the default Assistant."""
    return Assistant().run(
        message=message, conversation_key=conversation_key, context=context,
    )
