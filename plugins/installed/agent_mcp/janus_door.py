"""External agents talk to Janus: the door on the MCP server and the GraphQL API.

Design: docs/plans/janus-external-agents-2026-10.md. Rule: Torsor ADR 0039.

An agent holding an API token (Hermes Agent, OpenClaw, Claude Code, a script)
asks Janus, the store's own agent, and gets its answer. Janus then works with
exactly that token's power, never more: the MCP edge holds every tool call of
the turn to the token's scopes and approved tools (``core/assistant/gates.py``),
and nothing said in an external conversation is consent.

* The token must list ``janus.chat`` explicitly. The wildcard does not confer it
  (like ``acp.checkout``), so a legacy or unconfigured token never gains Janus
  without the merchant deciding.
* A turn runs on a worker (``agent_mcp.janus_turn``). A turn can take minutes; a
  web thread must not wait that long, and Janus's own tool calls need free web
  threads on this same server.
* The caller waits up to ``wait_seconds``, then gets ``status: running`` and a
  ``turn`` id to fetch the answer with (``janus.reply`` / ``janusTurn``).
* A conversation and its turns belong to the token: another token can neither
  continue nor read them.
"""

from __future__ import annotations

import logging
import re
import secrets
import time
from typing import Any

logger = logging.getLogger('morpheus.agent_mcp.janus')

SCOPE = 'janus.chat'
TURN_TTL_S = 24 * 3600
WAIT_DEFAULT_S = 20
WAIT_MAX_S = 25
POLL_S = 0.5
TURNS_PER_MINUTE = 10
RUNNING_MAX = 2
#: A turn still unfinished after this long is reported lost (its worker died).
STALE_AFTER_S = 480
MAX_MESSAGE_CHARS = 10_000
_CHAT_ID = re.compile(r'^[0-9a-f]{16}$')
_TURN_ID = re.compile(r'^[0-9a-f]{24}$')

REFUSED_GRANT = (
    'This token may not talk to Janus. The merchant can allow it on the API tokens page '
    '(Settings, Developer, API tokens: "Talk to Janus").'
)


class DoorError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def token_entry(token_id: str) -> dict | None:
    """The token's entry, read fresh, so a revoked token stops at once."""
    if not token_id:
        return None
    try:
        from plugins.models import PluginConfig

        cfg = PluginConfig.objects.filter(plugin_name='agent_mcp').first()
    except Exception:  # noqa: BLE001 — an unreadable store is a refused call
        logger.warning('janus door: token lookup failed', exc_info=True)
        return None
    for entry in ((cfg.config if cfg else {}) or {}).get('public_keys') or []:
        if isinstance(entry, dict) and str(entry.get('id') or '') == token_id:
            return entry
    return None


def janus_granted(entry: Any, surface: str = 'mcp') -> bool:
    """Whether the merchant let this token talk to Janus on ``surface``."""
    if not isinstance(entry, dict) or not entry.get('id'):
        return False
    scopes = entry.get(f'{surface}_scopes')
    return isinstance(scopes, (list, tuple, set)) and SCOPE in {str(s) for s in scopes}


def _turn_key(turn_id: str) -> str:
    return f'janus:ext:turn:{turn_id}'


def _running_key(token_id: str) -> str:
    return f'janus:ext:running:{token_id}'


def _wait_seconds(value: Any) -> int:
    if value is None:
        return WAIT_DEFAULT_S
    try:
        return max(0, min(int(value), WAIT_MAX_S))
    except (TypeError, ValueError):
        return WAIT_DEFAULT_S


def ask(
    *,
    entry: Any,
    message: str,
    conversation: str = '',
    wait_seconds: Any = None,
    surface: str = 'mcp',
) -> dict:
    """Queue a question for Janus and wait a little for the answer."""
    from django.core.cache import cache

    from core.utils.rate_limit import RateLimitExceeded, check_and_consume

    if not janus_granted(entry, surface):
        raise DoorError('forbidden', REFUSED_GRANT)
    text = (message or '').strip()
    if not text:
        raise DoorError('invalid', 'Send a message for Janus.')
    if len(text) > MAX_MESSAGE_CHARS:
        raise DoorError('invalid', f'Keep the message under {MAX_MESSAGE_CHARS} characters.')
    chat = (conversation or '').strip().lower()
    if chat and not _CHAT_ID.match(chat):
        raise DoorError('invalid', 'Unknown conversation. Leave it out to start a new one.')
    token_id = str(entry['id'])
    try:
        check_and_consume(
            key=f'janus:ext:{token_id}', max_per_window=TURNS_PER_MINUTE, window_seconds=60
        )
    except RateLimitExceeded as e:
        raise DoorError(
            'rate_limited', f'Too many questions this minute. Try again in {e.retry_after}s.'
        ) from e
    running = _running(token_id)
    if len(running) >= RUNNING_MAX:
        raise DoorError(
            'busy',
            f'{RUNNING_MAX} questions are still running. Fetch them with janus.reply first.',
        )
    turn_id = secrets.token_hex(12)
    state = {
        'turn': turn_id,
        'token': token_id,
        'conversation': chat or secrets.token_hex(8),
        'surface': surface,
        'status': 'queued',
        'reply': '',
        'error': '',
        'tool_calls': 0,
        'created_at': time.time(),
    }
    cache.set(_turn_key(turn_id), state, TURN_TTL_S)
    cache.set(_running_key(token_id), [*running, turn_id], TURN_TTL_S)
    try:
        from plugins.installed.agent_mcp.tasks import janus_turn

        janus_turn.delay(turn_id, text)
    except Exception:  # noqa: BLE001 — a queue outage is an answer, never a 500
        logger.warning('janus door: could not queue the turn', exc_info=True)
        _save(
            state,
            status='failed',
            error='Janus could not start: the task queue is unavailable. Try again shortly.',
        )
    return wait(turn_id=turn_id, token_id=token_id, wait_seconds=wait_seconds)


def reply(*, entry: Any, turn: str, wait_seconds: Any = None, surface: str = 'mcp') -> dict:
    """The answer to an earlier question, waiting a little if it is still running."""
    if not janus_granted(entry, surface):
        raise DoorError('forbidden', REFUSED_GRANT)
    turn_id = (turn or '').strip().lower()
    if not _TURN_ID.match(turn_id):
        raise DoorError('not_found', 'Unknown turn.')
    return wait(turn_id=turn_id, token_id=str(entry['id']), wait_seconds=wait_seconds)


def wait(*, turn_id: str, token_id: str, wait_seconds: Any = None) -> dict:
    from django.core.cache import cache

    deadline = time.monotonic() + _wait_seconds(wait_seconds)
    while True:
        state = cache.get(_turn_key(turn_id))
        if not state or state.get('token') != token_id:
            raise DoorError('not_found', 'Unknown turn. Turns are kept for 24 hours.')
        public = _public(state)
        if public['status'] in ('done', 'failed') or time.monotonic() >= deadline:
            return public
        time.sleep(POLL_S)


def _running(token_id: str) -> list[str]:
    from django.core.cache import cache

    alive = []
    for turn_id in cache.get(_running_key(token_id)) or []:
        state = cache.get(_turn_key(turn_id))
        if state and _public(state)['status'] in ('queued', 'running'):
            alive.append(turn_id)
    return alive


def _public(state: dict) -> dict:
    status = state.get('status') or 'queued'
    error = state.get('error') or ''
    age = time.time() - float(state.get('created_at') or 0)
    if status in ('queued', 'running') and age > STALE_AFTER_S:
        status, error = 'failed', 'The turn was lost (its worker stopped). Ask again.'
    out = {
        'turn': state['turn'],
        'conversation': state['conversation'],
        'status': status,
        'reply': state.get('reply') or '',
        'error': error,
        'tool_calls': int(state.get('tool_calls') or 0),
    }
    if status in ('queued', 'running'):
        out['hint'] = 'Janus is still working. Ask for the answer with this turn id.'
    return out


def _save(state: dict, **changes: Any) -> None:
    from django.core.cache import cache

    state.update(changes)
    cache.set(_turn_key(state['turn']), state, TURN_TTL_S)


def run(turn_id: str, message: str) -> str:
    """Worker side: run a queued turn. Returns its final status."""
    from django.core.cache import cache

    from core.assistant import gates
    from core.assistant.external import run_turn
    from plugins.installed.agent_mcp.auth import _service_user

    state = cache.get(_turn_key(turn_id))
    if not state:
        return 'missing'
    entry = token_entry(str(state.get('token') or ''))
    if not janus_granted(entry, state.get('surface') or 'mcp'):
        _save(state, status='failed', error='The token was revoked or may no longer talk to Janus.')
        return 'failed'
    _save(state, status='running')
    try:
        outcome = run_turn(
            principal=str(entry['id']),
            label=str(entry.get('label') or ''),
            conversation_key=gates.external_key(str(entry['id']), state['conversation']),
            message=message,
            user=_service_user(),
        )
    except Exception as e:  # noqa: BLE001 — the caller reads the failure; no turn stays stuck
        logger.warning('janus door: turn %s crashed', turn_id, exc_info=True)
        _save(state, status='failed', error=f'Janus could not answer ({type(e).__name__}).')
        return 'failed'
    failed = bool(outcome.get('error')) or outcome.get('state') == 'failed'
    _save(
        state,
        status='failed' if failed else 'done',
        reply=outcome.get('text') or '',
        error=outcome.get('error') or '',
        tool_calls=int(outcome.get('tool_calls') or 0),
    )
    return state['status']


# ── MCP tools on /mcp/admin/v1/ ─────────────────────────────────────────────
# Built here and listed only by the admin server: never registered in the agent
# registry, so neither Janus's own catalogue nor the Worker can call Janus.


def door_tools() -> list:
    from core.agents.tools import Tool

    return [
        Tool(
            name='janus.ask',
            description=(
                "Ask Janus, this store's own AI agent, about the store or ask it to do "
                'something. Janus knows the catalogue, orders, customers and settings, and '
                "uses the store's tools itself with this token's permissions. Returns "
                '{status, reply, conversation, turn}. Pass `conversation` from an earlier '
                'answer to continue it. If status is "running", call janus.reply with `turn`.'
            ),
            handler=_mcp_ask,
            schema={
                'type': 'object',
                'properties': {
                    'message': {
                        'type': 'string',
                        'description': 'What to ask or ask for, in plain language.',
                    },
                    'conversation': {
                        'type': 'string',
                        'description': "An earlier answer's conversation id, to continue it.",
                    },
                    'wait_seconds': {
                        'type': 'integer',
                        'minimum': 0,
                        'maximum': WAIT_MAX_S,
                        'description': f'How long to wait for the answer (default {WAIT_DEFAULT_S}).',
                    },
                },
                'required': ['message'],
            },
            scopes=[SCOPE],
            plugin='agent_mcp',
        ),
        Tool(
            name='janus.reply',
            description=(
                'Get the answer to an earlier janus.ask that was still running. Returns '
                '{status, reply, conversation, turn}.'
            ),
            handler=_mcp_reply,
            schema={
                'type': 'object',
                'properties': {
                    'turn': {'type': 'string', 'description': 'The turn id janus.ask returned.'},
                    'wait_seconds': {
                        'type': 'integer',
                        'minimum': 0,
                        'maximum': WAIT_MAX_S,
                        'description': f'How long to wait for the answer (default {WAIT_DEFAULT_S}).',
                    },
                },
                'required': ['turn'],
            },
            scopes=[SCOPE],
            plugin='agent_mcp',
        ),
    ]


def _mcp_caller() -> dict | None:
    from plugins.installed.agent_mcp.views import _request_state

    return token_entry(str(getattr(_request_state, 'token_id', '') or ''))


def _refused(error: DoorError) -> dict:
    return {'status': 'refused', 'code': error.code, 'error': error.message}


def _mcp_ask(message: str, conversation: str = '', wait_seconds: int | None = None) -> dict:
    try:
        return ask(
            entry=_mcp_caller(),
            message=message,
            conversation=conversation,
            wait_seconds=wait_seconds,
            surface='mcp',
        )
    except DoorError as e:
        return _refused(e)


def _mcp_reply(turn: str, wait_seconds: int | None = None) -> dict:
    try:
        return reply(entry=_mcp_caller(), turn=turn, wait_seconds=wait_seconds, surface='mcp')
    except DoorError as e:
        return _refused(e)
