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
from dataclasses import dataclass, field
from typing import Any

from core.assistant.persistence import StoredMessage, get_default_store
from core.assistant.prompts import build_system_prompt
from core.assistant.providers import get_default_provider

logger = logging.getLogger('morpheus.assistant')


_RETRIABLE_NEEDLES = (
    '429',
    'rate limit',
    'rate-limit',
    'overloaded',
    'temporarily',
    '502',
    '503',
    '504',
    'timeout',
    'timed out',
    'connection reset',
)


def _is_retriable(msg: str) -> bool:
    m = (msg or '').lower()
    return any(n in m for n in _RETRIABLE_NEEDLES)


def _friendly_provider_error(raw: str) -> str:  # noqa: PLR0911
    """Translate a raw provider exception into a user-readable line.

    The dashboard surfaces the assistant's text directly, so a stack
    trace or 200-char JSON blob feels like the platform crashed. Map
    common cases to a short note + a concrete next step.
    """
    text = (raw or '').lower()
    if not text:
        return "Sorry — I couldn't reach the AI provider just now. Try again in a moment."
    if '429' in text or 'rate' in text:
        return (
            "I hit the provider's rate limit (the free model is "
            'busy). Try again in ~30s, switch the provider/model in '
            '/dashboard/settings/ai/, or paste your own API key '
            'there to lift the limit.'
        )
    if 'invalid_api_key' in text or 'unauthorized' in text or '401' in text:
        return (
            'The configured AI key was rejected. Open '
            "/dashboard/settings/ai/ and check the active provider's "
            'key.'
        )
    if 'could not resolve authentication' in text or 'api_key' in text:
        return (
            'The active AI provider has no API key configured. Open '
            '/dashboard/settings/ai/, paste a key for the active '
            'provider (or switch providers), and try again.'
        )
    if '402' in text or 'quota' in text or 'insufficient' in text:
        return (
            'The AI provider says quota / billing is exhausted. '
            'Top it up or switch providers in '
            '/dashboard/settings/ai/.'
        )
    if 'no provider' in text or 'not configured' in text:
        return (
            'No AI provider is configured yet. Add a key in '
            "/dashboard/settings/ai/ and I'll be online."
        )
    if any(n in text for n in ('502', '503', '504', 'timeout', 'overloaded')):
        return (
            'The AI provider returned a transient error. Try again '
            'in a moment; if it persists, switch model in '
            '/dashboard/settings/ai/.'
        )
    return f'AI provider error — please try again. ({raw[:140]})'


@dataclass(slots=True)
class AssistantMessage:
    role: str  # 'user' | 'assistant' | 'system' | 'tool'
    content: str = ''
    tool_call_id: str = ''
    tool_calls: list = field(default_factory=list)
    name: str = ''


@dataclass(slots=True)
class AssistantRunResult:
    text: str
    state: str  # 'completed' | 'failed'
    tool_call_count: int = 0
    error: str = ''
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_ms: int = 0


def _format_recent_memories(query: str = '') -> str:
    """Compact bullet list of remembered facts, prepended each turn.

    ``query`` is the merchant's current message — semantically-similar
    memories rank above merely-recent ones (see ``get_recent_memories``).
    Empty string when nothing's remembered (or the model isn't migrated yet).
    This is the SINGLE memory-injection point; ``build_system_prompt`` no
    longer adds its own ``[MEMORY]`` section (it used to, doubling tokens).
    """
    try:
        from core.assistant.tools.memory import get_recent_memories

        rows = get_recent_memories(limit=50, query=query)
    except Exception:  # noqa: BLE001
        return ''
    if not rows:
        return ''
    lines = ['REMEMBERED FACTS — apply silently unless asked:']
    for r in rows:
        lines.append(f'  • [{r["scope"]}] {r["key"]}: {r["value"]}')
    return '\n'.join(lines)


def _format_knowledge(query: str = '') -> str:
    """Compact list of retrieved knowledge chunks, injected each turn.

    Complements the structured tools + remembered facts with *unstructured*
    knowledge (docs, policies, product long-copy) surfaced by the RAG retriever
    a plugin registered in ``core.assistant.knowledge``. Empty string when no
    retriever is registered or nothing matches — RAG is strictly additive.
    """
    try:
        from core.assistant.knowledge import retrieve

        chunks = retrieve(query, k=4)
    except Exception:  # noqa: BLE001
        return ''
    if not chunks:
        return ''
    lines = ['RETRIEVED KNOWLEDGE — cite only if relevant, never invent:']
    for c in chunks:
        title = (c.get('title') or c.get('ref') or '').strip()
        text = (c.get('text') or '').strip()
        if text:
            lines.append(f'  • {title}: {text}' if title else f'  • {text}')
    return '\n'.join(lines) if len(lines) > 1 else ''


def _format_janus_history(history: list[StoredMessage], *, limit: int = 12) -> str:
    """Render recent stored turns as a plain transcript for the Janus prompt.

    The legacy loop hands history to the provider as structured messages. The
    Janus engine takes a single system prompt plus one user message, so the
    conversation has to travel as text or not at all — and "not at all" is what
    shipped first: Linda restarted from nothing whenever the subprocess's own
    session file was missing, which is after every deploy.
    """
    if not history:
        return ''
    lines: list[str] = []
    for h in history[-limit:]:
        if h.role == 'tool':
            output = json.dumps(h.tool_output, default=str)[:600]
            lines.append(f'[tool {h.tool_name or "unknown"} result] {output}')
        elif h.role in ('user', 'assistant'):
            speaker = 'Merchant' if h.role == 'user' else 'Linda'
            lines.append(f'{speaker}: {(h.content or "")[:2000]}')
    if not lines:
        return ''
    body = '\n'.join(lines)
    return f'Earlier in this conversation (most recent last):\n{body}'


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
    memo = _format_recent_memories(user_message)
    if memo:
        msgs.append(LLMMessage(role='system', content=memo))
    # Inject retrieved unstructured knowledge (RAG) for the current message.
    # No-op unless a plugin registered a retriever (ai_assistant); additive.
    know = _format_knowledge(user_message)
    if know:
        msgs.append(LLMMessage(role='system', content=know))
    # Inject the page context (URL + title) if the caller supplied one
    # so Linda can answer about "this product / order / page".
    page_ctx = _page_context_system(context)
    if page_ctx:
        msgs.append(LLMMessage(role='system', content=page_ctx))
    for h in history:
        if h.role == 'tool':
            # Replayed tool results can NOT be sent as role='tool': the
            # OpenAI-compatible contract requires a `tool` message to directly
            # follow the assistant message carrying its matching tool_calls,
            # and the store never persisted tool_call ids (assistant replies
            # are stored as plain text). Strict providers (DeepSeek & co.)
            # hard-400 the dangling pair — "Messages with role 'tool' must be
            # a response to a preceding message with 'tool_calls'" — which
            # cascaded into "All AI providers degraded". Fold them into an
            # assistant-visible text record instead: same recall value,
            # always contract-valid.
            output = json.dumps(h.tool_output, default=str)[:8000]
            msgs.append(
                LLMMessage(
                    role='assistant',
                    content=f'[tool {h.tool_name or "unknown"} result] {output}',
                )
            )
        else:
            msgs.append(LLMMessage(role=h.role, content=h.content))
    msgs.append(LLMMessage(role='user', content=user_message))
    return msgs


def _compact(msgs: list[Any], summarizer) -> list[Any]:
    """Keep Linda's message list under a soft token budget by replacing the
    oldest turns with a rolling summary. No-op for short conversations; falls
    back to the uncompacted list if the agents kernel isn't importable (same
    defensive posture as ``_to_llm_messages``)."""
    try:
        from core.agents.compaction import compact
    except Exception:  # noqa: BLE001
        return msgs
    return compact(msgs, summarizer=summarizer)


class Assistant:
    """Linda — the hardcoded staff AI assistant.

    Construct with optional overrides; call `.run(message, key=...)` to chat.
    """

    name = 'assistant'
    label = 'Linda AI Assistant'
    max_steps = 8

    #: Scope profile — the union her built-in catalogue needs, and no more.
    #: The Worker has always been scope-checked (`enforce_policy`); Linda was
    #: not, so ANY registry tool a plugin contributed was callable by her
    #: regardless of what it demanded. Holding an explicit set means a
    #: contributed tool wanting `orders.write`/`rbac.*` is denied until it is
    #: deliberately granted, while nothing in today's catalogue breaks.
    scopes: list[str] = [
        'system.read',
        'system.write',
        'selfdev',
        'customers.write',
        'diagnostics.read',
    ]

    #: Token cap for one turn; 0 = unlimited (the guardrails convention). The
    #: merchant-facing daily caps live in `core.agents.guardrails`.
    token_budget: int = 0

    def __init__(
        self,
        *,
        provider=None,
        tools=None,
        store=None,
        max_steps: int | None = None,
        scopes: list[str] | None = None,
        token_budget: int | None = None,
    ) -> None:
        self.provider = provider or get_default_provider()
        self._provider_overridden = provider is not None
        # Lazy-resolve tools the first time they're needed so a broken
        # tool import doesn't take the Assistant down at construct time.
        self._tools = tools
        self.store = store or get_default_store()
        if max_steps is not None:
            self.max_steps = max_steps
        if scopes is not None:
            self.scopes = list(scopes)
        if token_budget is not None:
            self.token_budget = token_budget

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

    def _janus_mode(self, context):
        """Resolve the EFFECTIVE mode for a turn, server-side.

        ``context['mode']`` is a client-supplied slug — a request, never a
        grant (core audit S5/H1). The legacy loop resolves it and then filters
        the tool catalogue by the mode's scopes; this mirrors the resolution so
        the Janus path can decide whether it is allowed to run at all.
        """
        from core.assistant.modes import get_mode, resolve_mode

        ctx = context if isinstance(context, dict) else {}
        slug = str(ctx.get('mode') or '').strip().lower()
        user = ctx.get('user')
        return resolve_mode(slug, user) if user is not None else get_mode(slug)

    def _should_use_janus(self, context=None) -> bool:
        """Janus is OPT-IN; tests that inject a provider stay on the legacy loop.

        The engine runs out-of-process and reaches its tools over MCP, so a
        Janus turn passes through none of ``_gate_reason`` (scope → budget →
        deadline → kernel consent) and none of ``_audit_write_tool``. Until the
        MCP edge enforces that same stack, the default stays ``legacy`` — see
        ``LINDA_ENGINE`` in ``morph/settings.py``.
        """
        if self._provider_overridden:
            return False
        try:
            from django.conf import settings

            engine = str(getattr(settings, 'LINDA_ENGINE', 'legacy') or 'legacy').lower()
        except Exception:  # noqa: BLE001
            engine = 'legacy'
        if engine != 'janus':
            return False
        # The mode chip is an enforcement boundary, not a label: the legacy loop
        # narrows Linda's tool catalogue to the mode's scopes. No such filter
        # exists on the MCP side, so a RESTRICTED mode (sales/support/ops) falls
        # back to the in-process loop rather than silently receiving the
        # wildcard palette. Wildcard modes (general/dev) lose nothing by
        # running on Janus.
        try:
            if '*' not in self._janus_mode(context).scopes:
                return False
        except Exception:  # noqa: BLE001 — an unresolvable mode is not a wildcard
            logger.warning('assistant: mode resolution failed; staying on legacy', exc_info=True)
            return False
        try:
            from core.assistant.janus_engine import janus_available

            return janus_available()
        except Exception:  # noqa: BLE001
            return False

    def _stream_via_janus(
        self, *, message: str, conversation_key: str, context, started: float, history=None
    ):
        """One turn on the Janus engine; the merchant-facing name stays Linda."""
        from core.assistant.janus_engine import run_janus_turn
        from core.assistant.prompts import build_system_prompt

        prefix_bits = []
        if context and isinstance(context, dict):
            page_url = (context.get('page_url') or '')[:512]
            page_title = (context.get('page_title') or '')[:200]
            if page_url or page_title:
                prefix_bits.append(
                    f'The merchant opened Linda from: {page_title} {page_url}'.strip()
                )
        # The RESOLVED mode, never the raw client slug.
        try:
            prefix_bits.append(f'Active tool palette: {self._janus_mode(context).slug}')
        except Exception:  # noqa: BLE001
            logger.debug('assistant: mode label unavailable', exc_info=True)
        # Morpheus owns the transcript; Janus keeps its own session state in a
        # container-local file that every deploy wipes. Replay recent history
        # into the prompt so continuity does not depend on that file surviving.
        transcript = _format_janus_history(history or [])
        if transcript:
            prefix_bits.append(transcript)
        mem = _format_recent_memories(message)
        if mem:
            prefix_bits.append(mem)
        know = _format_knowledge(message)
        if know:
            prefix_bits.append(know)
        system = build_system_prompt()
        if prefix_bits:
            system = system + '\n\n' + '\n'.join(prefix_bits)
        system += (
            '\n\nIDENTITY: You are Linda. Janus is your engine, never your name. '
            'Do not mention Janus, Magnetoid, or the underlying agent framework '
            'unless the merchant asks how you work.'
        )

        yield {'type': 'assistant_text', 'text': ''}
        payload = run_janus_turn(
            message=message,
            conversation_key=conversation_key,
            system_prompt=system,
            context=context if isinstance(context, dict) else None,
        )
        duration = payload.get('duration_ms') or int((time.monotonic() - started) * 1000)
        if payload.get('error'):
            friendly = _friendly_provider_error(str(payload['error']))
            self.store.append(
                conversation_key=conversation_key,
                message=StoredMessage(role='assistant', content=friendly),
            )
            # Same telemetry the legacy loop emits on a provider failure —
            # without it the self-improvement loop never sees a Janus turn fail.
            self._emit_failure_signal(
                reason='janus_engine_error',
                conversation_key=conversation_key,
                detail=str(payload['error']),
            )
            yield {
                'type': 'error',
                'result': AssistantRunResult(
                    text=friendly,
                    state='failed',
                    error=str(payload['error'])[:500],
                    duration_ms=duration,
                ),
            }
            return
        text = payload.get('text') or ''
        self.store.append(
            conversation_key=conversation_key,
            message=StoredMessage(role='assistant', content=text[:50_000]),
        )
        yield {'type': 'assistant_text', 'text': text}
        yield {
            'type': 'final',
            'result': AssistantRunResult(text=text, state='completed', duration_ms=duration),
        }

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
        for event in self.stream(
            message=message, conversation_key=conversation_key, context=context
        ):
            kind = event.get('type')
            if kind == 'final' or kind == 'error':  # noqa: PLR1714
                result = event['result']
        return result

    def _summarize_history(self, transcript: str) -> str:
        """Provider-backed summarizer for context compaction. A terse, low-cost
        call; on any failure `compact` falls back to truncation. Mirrors the
        agent runtime's summarizer so Linda and agents compact the same way."""
        try:
            from core.agents.llm import LLMMessage

            resp = self.provider.respond(
                messages=[
                    LLMMessage(
                        role='system',
                        content=(
                            'Summarize the following assistant conversation in a few '
                            'sentences. Preserve facts established, decisions made, and '
                            'tasks still pending. Be concise.'
                        ),
                    ),
                    LLMMessage(role='user', content=transcript[:12000]),
                ],
                tools=None,
                temperature=0.0,
                max_tokens=300,
            )
            return resp.text or ''
        except Exception as e:  # noqa: BLE001 — compaction must never break a turn
            logger.warning('assistant: history summarization failed: %s', e)
            return ''

    def stream(  # noqa: PLR0915, PLR0912
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

        # Merchant kill switch — Linda is a chat surface, so a paused agent
        # layer declines gracefully (never a stack trace). A deliberate pause is
        # not an outage, so no _emit_failure_signal. Config is read cross-process
        # fresh (see core.agents.guardrails); default is NOT paused.
        from core.agents.guardrails import agents_paused

        if agents_paused():
            friendly = 'The assistant is paused right now. Please try again in a little while.'
            self.store.append(
                conversation_key=conversation_key,
                message=StoredMessage(role='assistant', content=friendly),
            )
            yield {
                'type': 'final',
                'result': AssistantRunResult(
                    text=friendly,
                    state='completed',
                    duration_ms=int((time.monotonic() - started) * 1000),
                ),
            }
            return

        # NOTE: a Janus turn reports no token counts (the subprocess returns text
        # on stdout, not usage), so `spend_cap_daily` cannot see it. The
        # model-independent `max_agent_runs_daily` cap is the only backstop on
        # this path — the same gap `core/agents/pricing.py` has for an unpriced
        # model.
        if self._should_use_janus(context):
            yield from self._stream_via_janus(
                message=message,
                conversation_key=conversation_key,
                context=context,
                started=started,
                history=history,
            )
            return

        msgs = _to_llm_messages(history, message, context=context)
        # Tool-palette scoping (core/assistant/modes.py). The merchant
        # picks a mode per conversation from the chat header chip; it
        # arrives in `context['mode']`. Filter Linda's tool catalogue
        # by the mode's scope whitelist BEFORE passing it to the LLM,
        # so she can't pick a refund tool during a "sales" convo.
        # Unknown / missing mode → general (wildcard) — full access.
        from core.assistant.modes import filter_tools_by_mode, get_mode, resolve_mode

        mode_slug = ''
        user = None
        if context and isinstance(context, dict):
            mode_slug = str(context.get('mode') or '').strip().lower()
            user = context.get('user')
        # A real client request always carries the acting user (the assistant
        # views set request.user) → resolve the EFFECTIVE mode server-side: the
        # client slug is a request, never a grant, so a non-engineer can't select
        # `dev` (diagnostics) and an unknown slug can't escalate to the wildcard
        # (core audit S5/H1). No acting user = a trusted internal/system call →
        # honour the requested mode.
        active_mode = resolve_mode(mode_slug, user) if user is not None else get_mode(mode_slug)
        tools = filter_tools_by_mode(self.tools, active_mode.slug)
        # Both spellings: canonical dotted name + provider-safe api_name
        # (dots→__) — models echo back the api_name from the tool schema.
        tools_by_name = {t.name: t for t in tools}
        tools_by_name.update({t.api_name: t for t in tools})
        logger.info(
            'assistant: mode=%s tool_count=%d/%d conversation=%s',
            active_mode.slug,
            len(tools),
            len(self.tools),
            conversation_key,
        )

        prompt_tokens = 0
        completion_tokens = 0
        tool_calls = 0
        consecutive_tool_errors = 0  # Phase 1b: trip a replan nudge at 2 in a row

        for _step in range(max(1, self.max_steps)):
            # Context compaction — keep `msgs` under a soft token budget by
            # summarizing the oldest turns (tool outputs accumulate across steps
            # within a turn, and history is only count-capped, not token-capped).
            # No-op for short conversations.
            msgs = _compact(msgs, self._summarize_history)

            resp = None
            err: str = ''
            for attempt in (0, 1):  # one retry for transient errors
                try:
                    resp = self.provider.respond(
                        messages=msgs,
                        tools=tools or None,
                        temperature=0.2,
                        max_tokens=1500,
                    )
                    err = ''
                    break
                except Exception as e:  # noqa: BLE001
                    err = str(e)
                    logger.warning(
                        'assistant: provider attempt %d failed: %s',
                        attempt + 1,
                        err,
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
                self._emit_failure_signal(
                    reason='provider_error', conversation_key=conversation_key, detail=err
                )
                yield {
                    'type': 'error',
                    'result': AssistantRunResult(
                        text=friendly,
                        state='failed',
                        error=err,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        tool_call_count=tool_calls,
                        duration_ms=int((time.monotonic() - started) * 1000),
                    ),
                }
                return

            prompt_tokens += getattr(resp, 'prompt_tokens', 0) or 0
            completion_tokens += getattr(resp, 'completion_tokens', 0) or 0

            # A degraded sentinel is an outage marker, not an answer. The
            # breaker/fallback-router return it as response TEXT (so agent
            # transcripts stay consistent), which means it arrives here
            # looking like a normal completion — without this check the raw
            # "[All AI providers degraded. Last error: …]" string (stack
            # trace included) ships straight into the chat. Route it through
            # the same friendly-error path as a raised provider exception.
            try:
                from core.agents.llm import is_degraded_response
            except Exception:  # noqa: BLE001 — kernel import must never break Linda
                is_degraded_response = lambda _t: False  # noqa: E731
            if is_degraded_response(getattr(resp, 'text', '')):
                friendly = _friendly_provider_error(resp.text)
                self.store.append(
                    conversation_key=conversation_key,
                    message=StoredMessage(role='assistant', content=friendly),
                )
                self._emit_failure_signal(
                    reason='provider_degraded',
                    conversation_key=conversation_key,
                    detail=resp.text[:500],
                )
                yield {
                    'type': 'error',
                    'result': AssistantRunResult(
                        text=friendly,
                        state='failed',
                        error=resp.text[:500],
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        tool_call_count=tool_calls,
                        duration_ms=int((time.monotonic() - started) * 1000),
                    ),
                }
                return

            if not getattr(resp, 'tool_calls', None):
                final = resp.text or ''
                self.store.append(
                    conversation_key=conversation_key,
                    message=StoredMessage(
                        role='assistant',
                        content=final[:50_000],
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        model=getattr(resp, 'model', '') or '',
                    ),
                )
                yield {
                    'type': 'final',
                    'result': AssistantRunResult(
                        text=final,
                        state='completed',
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        tool_call_count=tool_calls,
                        duration_ms=int((time.monotonic() - started) * 1000),
                    ),
                }
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
            msgs.append(
                LLMMessage(
                    role='assistant',
                    content=resp.text or '',
                    tool_calls=resp.tool_calls,
                )
            )
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
                    'name': tc_name,
                    'arguments': tc_args or {},
                }
                tool_output, tool_error = self._dispatch_tool(
                    tc=tc,
                    tools_by_name=tools_by_name,
                    msgs=msgs,
                    conversation_key=conversation_key,
                    context=context,
                    human_message=message,
                    spent_tokens=prompt_tokens + completion_tokens,
                )
                yield {
                    'type': 'tool_call_finished',
                    'name': tc_name,
                    'output': tool_output,
                    'error': tool_error,
                }
                # Phase 1b: if tools keep failing, nudge the model to step back and
                # replan instead of grinding through identical retries to max_steps.
                if tool_error:
                    consecutive_tool_errors += 1
                    if consecutive_tool_errors >= 2:
                        from core.agents.llm import LLMMessage as _ReplanMsg

                        msgs.append(
                            _ReplanMsg(
                                role='system',
                                content=(
                                    'Two tool calls failed in a row. Stop and restate the '
                                    'goal in one sentence, then choose a DIFFERENT tool or '
                                    'approach — or ask the user for the missing detail '
                                    'rather than retrying the same call.'
                                ),
                            )
                        )
                        consecutive_tool_errors = 0
                else:
                    consecutive_tool_errors = 0

        # Loop exhausted.
        self.store.append(
            conversation_key=conversation_key,
            message=StoredMessage(role='assistant', content='(stopped: max steps)'),
        )
        self._emit_failure_signal(reason='max_steps_exceeded', conversation_key=conversation_key)
        yield {
            'type': 'error',
            'result': AssistantRunResult(
                text='',
                state='failed',
                error='max_steps_exceeded',
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                tool_call_count=tool_calls,
                duration_ms=int((time.monotonic() - started) * 1000),
            ),
        }

    def _emit_failure_signal(self, *, reason, conversation_key, detail=''):
        """Phase 1d: record a Linda failure as a self-improvement signal so the
        engine sees where the assistant gets stuck (deduped by reason via the
        fingerprint). Fail-soft — never break the turn over telemetry."""
        try:
            from core.self_improvement.services import emit_signal

            emit_signal(
                source='agent_failure',
                fingerprint=f'assistant:{reason}',
                severity=40,
                payload={
                    'reason': reason,
                    'conversation': conversation_key,
                    'detail': str(detail)[:500],
                },
            )
        except Exception:  # noqa: BLE001 — telemetry is best-effort
            logger.debug('assistant: failure-signal emit skipped', exc_info=True)

    def _repair_tool_args(self, tool, args, err):
        """One bounded LLM re-ask to correct malformed tool arguments — returns a
        corrected args dict, or None if repair fails (Phase 1b self-correction).

        A TypeError means the model sent wrong/missing kwargs; rather than just
        echoing the raw Python error back, give it the tool's JSON schema and the
        error and let it fix the arguments before we surface a failure.
        """
        try:
            from core.agents.llm import LLMMessage
            from core.llm_parsing import parse_llm_json

            schema = getattr(tool, 'schema', {}) or {}
            resp = self.provider.respond(
                messages=[
                    LLMMessage(
                        role='user',
                        content=(
                            f'The arguments for tool `{getattr(tool, "name", "")}` were '
                            f'invalid: {err}\nJSON schema: {json.dumps(schema)}\n'
                            f'You sent: {json.dumps(args, default=str)}\n'
                            'Reply with ONLY the corrected JSON arguments object, no prose.'
                        ),
                    )
                ],
                temperature=0.0,
                max_tokens=400,
            )
            parsed = parse_llm_json(getattr(resp, 'text', '') or '')
            return parsed if isinstance(parsed, dict) else None
        except Exception:  # noqa: BLE001 — repair is best-effort, never fatal
            return None

    def _gate_reason(  # noqa: PLR0911 — flat guard chain, mirrors AgentRuntime
        self, *, tool, tool_name, args, context, conversation_key, human_message, spent_tokens
    ) -> str | None:
        """Return a refusal reason, or ``None`` to let the call through.

        The same enforcement stack the Worker has always run: scope → budget →
        deadline → approval.
        """
        # Scope: an under-scoped caller never reaches an over-scoped tool.
        try:
            from core.agents.policies import ScopeDenied, enforce_policy

            enforce_policy(scopes=self.scopes, required=list(getattr(tool, 'scopes', None) or []))
        except ScopeDenied as e:
            return str(e)
        except Exception:  # noqa: BLE001 — a broken policy import must not open the gate
            logger.warning('assistant: scope check unavailable', exc_info=True)
            return 'scope_check_unavailable'

        # Token budget (0 = unlimited) and the cooperative wall-clock deadline —
        # a timed-out turn stops issuing NEW tool calls instead of running on as
        # a zombie (the reason AgentRuntime polls `context['deadline']`).
        try:
            from core.agents.policies import BudgetExceeded, enforce_budget
            from core.agents.runtime import _deadline_exceeded

            enforce_budget(spent=spent_tokens, cap=self.token_budget or None)
            if _deadline_exceeded(context or {}):
                return 'deadline_exceeded'
        except BudgetExceeded:
            return 'budget_exceeded'
        except Exception:  # noqa: BLE001 — budget/deadline are advisory, not a gate
            logger.debug('assistant: budget/deadline check skipped', exc_info=True)

        # Approval — kernel-verified HUMAN consent. Staged mode is exempt only
        # for tools that actually stage (`supports_staging`): such a tool records
        # an OpsProposal for review instead of executing, and that proposal IS
        # the sign-off. A tool with no staging path must still pass the gate, or
        # the exemption reopens the S1 hole for the staged path.
        _staged = isinstance(context, dict) and context.get('staged')
        _staged_exempt = _staged and getattr(tool, 'supports_staging', False)
        if getattr(tool, 'requires_approval', False) and not _staged_exempt:
            from core.assistant import consent

            if not consent.consume(
                conversation_key=conversation_key,
                tool_name=tool_name,
                args=args,
                human_message=human_message,
            ):
                consent.request(conversation_key=conversation_key, tool_name=tool_name, args=args)
                return (
                    'approval_required: tell the user exactly what this will do and ask them '
                    'to confirm. Do NOT re-call until they have answered — their own reply is '
                    'what authorises it, not a `confirmed` argument.'
                )
        return None

    def _dispatch_tool(
        self,
        *,
        tc,
        tools_by_name,
        msgs,
        conversation_key,
        context,
        human_message: str = '',
        spent_tokens: int = 0,
    ):
        """Invoke a single tool call, persist the result, append to LLM context.
        Returns ``(output, error_message)`` so :meth:`stream` can echo the
        outcome out to the SSE client.

        Guarded by the same enforcement stack as the Worker
        (:class:`core.agents.runtime.AgentRuntime`) — scope, budget, deadline,
        approval. Linda ran ungated until now: her only write-path handling was
        the POST-HOC audit below, and her dangerous tools trusted an
        LLM-supplied ``confirmed=True`` argument that injected content could
        induce. See :mod:`core.assistant.consent`.
        """
        tool_name = getattr(tc, 'name', '')
        args = getattr(tc, 'arguments', {}) or {}
        tool = tools_by_name.get(tool_name)
        try:
            from core.agents.llm import LLMMessage
        except Exception:  # noqa: BLE001
            LLMMessage = type(msgs[0])

        def _refuse(reason: str):
            """Hand a refusal back to the model as a tool result (never an
            exception): the LLM can explain it or pick another path, and the
            transcript records why."""
            payload = {'error': reason}
            msgs.append(
                LLMMessage(
                    role='tool',
                    tool_call_id=getattr(tc, 'id', ''),
                    name=tool_name,
                    content=json.dumps(payload),
                )
            )
            self.store.append(
                conversation_key=conversation_key,
                message=StoredMessage(
                    role='tool', tool_name=tool_name, tool_args=args, tool_output=payload
                ),
            )
            return payload, reason

        if tool is None:
            return _refuse(f'unknown tool: {tool_name}')

        gate = self._gate_reason(
            tool=tool,
            tool_name=tool_name,
            args=args,
            context=context,
            conversation_key=conversation_key,
            human_message=human_message,
            spent_tokens=spent_tokens,
        )
        if gate:
            # Audit the ATTEMPT. A refused write is more interesting to a
            # merchant auditing "what did the AI try to change?" than a
            # successful one — without this, a blocked injection leaves no
            # trace outside the transcript.
            self._audit_write_tool(
                tool=tool,
                args=args,
                payload={'refused': gate},
                error_msg=gate,
                conversation_key=conversation_key,
                context=context,
            )
            return _refuse(gate)

        error_msg = ''
        try:
            result = tool.invoke(args, agent=self, context=context or {})
            output = result.output if hasattr(result, 'output') else result
        except Exception as e:  # noqa: BLE001 — never let a tool failure kill the run
            # Tool.invoke wraps a bad-arguments TypeError as ToolError("TypeError:
            # ... argument ..."). On that specific case, make ONE bounded LLM repair
            # attempt before surfacing the error (Phase 1b self-correction).
            # Intentional validation ToolErrors ("query required") pass straight
            # through to the model via the error result, as before.
            msg = str(e)
            repaired = False
            if 'TypeError' in msg and 'argument' in msg:
                fixed = self._repair_tool_args(tool, args, e)
                if isinstance(fixed, dict) and fixed != args:
                    try:
                        result = tool.invoke(fixed, agent=self, context=context or {})
                        output = result.output if hasattr(result, 'output') else result
                        args = fixed
                        repaired = True
                    except Exception:  # noqa: BLE001 — repair failed; fall through
                        repaired = False
            if not repaired:
                output = {'error': f'{type(e).__name__}: {e}'}
                error_msg = output['error']
        payload = output if isinstance(output, (dict, list, str, int, float, bool)) else str(output)
        msgs.append(
            LLMMessage(
                role='tool',
                tool_call_id=getattr(tc, 'id', ''),
                name=tool_name,
                content=json.dumps(payload, default=str)[:8000],
            )
        )
        self.store.append(
            conversation_key=conversation_key,
            message=StoredMessage(
                role='tool', tool_name=tool_name, tool_args=args, tool_output=payload
            ),
        )
        self._audit_write_tool(
            tool=tool,
            args=args,
            payload=payload,
            error_msg=error_msg,
            conversation_key=conversation_key,
            context=context,
        )
        return payload, error_msg

    def _audit_write_tool(
        self, *, tool, args, payload, error_msg, conversation_key, context
    ) -> None:
        """Record write-tool invocations to core.audit (fail-soft).

        Chat transcripts are Linda's only record otherwise — a merchant
        auditing "what did the AI change?" must be able to answer from the
        audit log, not by re-reading conversations. Read tools are skipped
        (volume, no state change).
        """
        try:
            is_write = bool(getattr(tool, 'requires_approval', False)) or any(
                'write' in s or s in ('orders.cancel', 'selfdev')
                for s in (getattr(tool, 'scopes', None) or [])
            )
            if not is_write:
                return
            from core.audit.services import record

            user = (context or {}).get('user')
            record(
                event_type='assistant.tool_write',
                actor=user if getattr(user, 'pk', None) else None,
                target=getattr(tool, 'name', ''),
                severity='warning' if error_msg else 'info',
                metadata={
                    'args': json.dumps(args, default=str)[:2000],
                    'output_head': json.dumps(payload, default=str)[:500],
                    'error': (error_msg or '')[:300],
                    'conversation': conversation_key,
                },
            )
        except Exception:  # noqa: BLE001 — auditing must never break the turn
            logger.debug('assistant: write-tool audit skipped', exc_info=True)


def run_assistant(
    *, message: str, conversation_key: str = 'default', context: dict[str, Any] | None = None
) -> AssistantRunResult:
    """Module-level convenience: run a single turn against the default Assistant."""
    return Assistant().run(
        message=message,
        conversation_key=conversation_key,
        context=context,
    )
