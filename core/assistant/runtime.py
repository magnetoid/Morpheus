"""
Linda's turn runtime. Janus is the engine; Linda is the name the merchant sees.

One call to :meth:`Assistant.stream` is one chat turn: store the merchant's
message, apply the merchant's guardrails, run the turn on Janus
(:mod:`core.assistant.janus_engine`), store the reply. Janus runs its own tool
loop in a subprocess and reaches the store's tools over MCP. Every tool call it
makes is gated at that edge — Linda's scope profile, the conversation's mode,
human consent, write audit — by :mod:`core.assistant.gates`, keyed to this turn
by a signed token from :mod:`core.assistant.turn_identity`.

Self-contained: nothing here imports ``plugins.*``.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from core.assistant.persistence import StoredMessage, get_default_store
from core.assistant.prompts import build_system_prompt

logger = logging.getLogger('morpheus.assistant')


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


class Assistant:
    """Linda — the staff AI assistant. Call :meth:`stream` to run one turn."""

    def __init__(self, *, store=None) -> None:
        self.store = store or get_default_store()

    @staticmethod
    def _mode(context):
        """The EFFECTIVE mode for a turn, resolved server-side.

        ``context['mode']`` is a client-supplied slug — a request, never a grant
        (core audit S5/H1). The MCP edge re-resolves it on every tool call.
        """
        from core.assistant.modes import get_mode, resolve_mode

        ctx = context if isinstance(context, dict) else {}
        slug = str(ctx.get('mode') or '').strip().lower()
        user = ctx.get('user')
        return resolve_mode(slug, user) if user is not None else get_mode(slug)

    def _mint_turn_token(self, context, conversation_key: str) -> str:
        """A signed identity for this turn, or '' when there is no staff user.

        No token means the MCP edge answers 401 and Janus has no store tools —
        the right outcome for a call with nobody to consent or be audited.
        """
        user = (context or {}).get('user') if isinstance(context, dict) else None
        if user is None or not getattr(user, 'is_staff', False) or not getattr(user, 'pk', None):
            return ''
        from core.assistant.janus_engine import turn_timeout_s
        from core.assistant.turn_identity import mint

        # Margin past the subprocess timeout: a tool call issued in the turn's
        # final seconds must not be refused while the turn is still legitimate.
        return mint(
            user=user,
            conversation_key=conversation_key,
            mode_slug=self._mode(context).slug,
            ttl_s=turn_timeout_s() + 30,
        )

    def _system_prompt(self, *, message: str, context, history) -> str:
        bits = []
        if isinstance(context, dict):
            page_url = (context.get('page_url') or '')[:512]
            page_title = (context.get('page_title') or '')[:200]
            if page_url or page_title:
                bits.append(f'The merchant opened Linda from: {page_title} {page_url}'.strip())
        # The RESOLVED mode, never the raw client slug.
        try:
            bits.append(f'Active tool palette: {self._mode(context).slug}')
        except Exception:  # noqa: BLE001
            logger.debug('assistant: mode label unavailable', exc_info=True)
        # Morpheus owns the transcript; Janus keeps its own session state in a
        # home that a redeploy wipes. Replay recent history into the prompt so
        # continuity does not depend on that state surviving.
        for part in (
            _format_janus_history(history or []),
            _format_recent_memories(message),
            _format_knowledge(message),
        ):
            if part:
                bits.append(part)
        system = build_system_prompt()
        if bits:
            system = system + '\n\n' + '\n'.join(bits)
        return system + (
            '\n\nIDENTITY: You are Linda. Janus is your engine, never your name. '
            'Do not mention Janus, Magnetoid, or the underlying agent framework '
            'unless the merchant asks how you work.'
        )

    def _finish(self, *, conversation_key: str, text: str, started: float, error: str = ''):
        """Store Linda's reply and build the closing event."""
        self.store.append(
            conversation_key=conversation_key,
            message=StoredMessage(role='assistant', content=text[:50_000]),
        )
        duration = int((time.monotonic() - started) * 1000)
        if error:
            result = AssistantRunResult(
                text=text, state='failed', error=error[:500], duration_ms=duration
            )
            return {'type': 'error', 'result': result}
        return {
            'type': 'final',
            'result': AssistantRunResult(text=text, state='completed', duration_ms=duration),
        }

    def stream(
        self,
        *,
        message: str,
        conversation_key: str,
        context: dict[str, Any] | None = None,
    ):
        """Generator that yields events as the turn progresses.

        Event types (each is a dict):
          * ``{type: 'assistant_text', text}``
          * ``{type: 'final', result: AssistantRunResult}``
          * ``{type: 'error', result: AssistantRunResult}``
        """
        started = time.monotonic()
        history = self.store.history(conversation_key=conversation_key, limit=30)
        self.store.append(
            conversation_key=conversation_key,
            message=StoredMessage(role='user', content=message[:50_000]),
        )

        # Merchant kill switch and daily caps — a deliberate limit, not an outage,
        # so no failure signal. Config is read cross-process fresh (see
        # core.agents.guardrails); default is NOT paused. The caps count the
        # Worker's AgentRun rows, so a Linda turn does not itself add to the
        # tally; it is still refused once the store is over the limit.
        from core.agents.guardrails import agents_paused, run_start_block_reason

        paused = agents_paused()
        cap_reason = None if paused else run_start_block_reason()
        if paused or cap_reason:
            friendly = (
                'The assistant is paused right now. Please try again in a little while.'
                if cap_reason is None
                else "The assistant has reached today's limit set in Agent guardrails."
            )
            yield self._finish(conversation_key=conversation_key, text=friendly, started=started)
            return

        from core.assistant.janus_engine import janus_available, run_janus_turn

        if not janus_available():
            self._emit_failure_signal(reason='janus_unavailable', conversation_key=conversation_key)
            yield self._finish(
                conversation_key=conversation_key,
                text="Linda's engine isn't installed on this server, so she can't answer yet.",
                started=started,
                error='janus_unavailable',
            )
            return

        yield {'type': 'assistant_text', 'text': ''}
        # A Janus turn reports no token usage (the subprocess returns text on
        # stdout), so its own spend never reaches `spend_cap_daily`.
        payload = run_janus_turn(
            message=message,
            conversation_key=conversation_key,
            system_prompt=self._system_prompt(message=message, context=context, history=history),
            context=context if isinstance(context, dict) else None,
            turn_token=self._mint_turn_token(context, conversation_key),
        )
        if payload.get('error'):
            error = str(payload['error'])
            self._emit_failure_signal(
                reason='janus_engine_error', conversation_key=conversation_key, detail=error
            )
            yield self._finish(
                conversation_key=conversation_key,
                text=_friendly_provider_error(error),
                started=started,
                error=error,
            )
            return
        text = payload.get('text') or ''
        yield {'type': 'assistant_text', 'text': text}
        yield self._finish(conversation_key=conversation_key, text=text, started=started)

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
