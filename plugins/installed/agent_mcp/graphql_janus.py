"""GraphQL door to Janus: ``askJanus`` and ``janusTurn``.

The same door as the MCP tools ``janus.ask`` / ``janus.reply``
(``janus_door.py``): an API token that lists ``janus.chat`` on its GraphQL
scopes asks Janus, the store's own agent, and Janus works with that token's
power. A dashboard session talks to Janus in the chat, not here.
"""

from __future__ import annotations

import strawberry

from api.graphql_permissions import mutation_scope_error


@strawberry.type
class JanusAnswer:
    turn: str
    conversation: str
    status: str
    reply: str
    error: str
    tool_calls: int


@strawberry.input
class AskJanusInput:
    message: str
    conversation: str | None = None
    wait_seconds: int | None = None


def _request(info: strawberry.Info):
    context = info.context
    request = getattr(context, 'request', None)
    if request is None and isinstance(context, dict):
        request = context.get('request')
    return request


def _caller(info: strawberry.Info) -> tuple[dict | None, str]:
    from plugins.installed.agent_mcp.janus_door import (
        REFUSED_GRANT,
        SCOPE,
        janus_granted,
        token_entry,
    )

    denied = mutation_scope_error(info, [SCOPE])
    if denied:
        return None, denied
    token_id = str(getattr(_request(info), '_morph_token_id', '') or '')
    if not token_id:
        return None, 'Talk to Janus with an API token. In the dashboard, use the chat.'
    entry = token_entry(token_id)
    if not janus_granted(entry, 'graphql'):
        return None, REFUSED_GRANT
    return entry, ''


def _answer(payload: dict) -> JanusAnswer:
    return JanusAnswer(
        turn=str(payload.get('turn') or ''),
        conversation=str(payload.get('conversation') or ''),
        status=str(payload.get('status') or ''),
        reply=str(payload.get('reply') or ''),
        error=str(payload.get('error') or ''),
        tool_calls=int(payload.get('tool_calls') or 0),
    )


def _refused(message: str) -> JanusAnswer:
    return JanusAnswer(
        turn='', conversation='', status='refused', reply='', error=message, tool_calls=0
    )


@strawberry.type
class JanusMutationExtension:
    @strawberry.mutation(
        description=(
            "Ask Janus, the store's own AI agent, about the store or ask it to do something. "
            "Janus works with this token's permissions. When status is RUNNING, fetch the "
            'answer with janusTurn(turn).'
        )
    )
    def ask_janus(self, info: strawberry.Info, input: AskJanusInput) -> JanusAnswer:  # noqa: A002
        from plugins.installed.agent_mcp.janus_door import DoorError, ask

        entry, denied = _caller(info)
        if denied:
            return _refused(denied)
        try:
            return _answer(
                ask(
                    entry=entry,
                    message=input.message,
                    conversation=input.conversation or '',
                    wait_seconds=input.wait_seconds,
                    surface='graphql',
                )
            )
        except DoorError as e:
            return _refused(e.message)


@strawberry.type
class JanusQueryExtension:
    @strawberry.field(description='The answer to an earlier askJanus that was still running.')
    def janus_turn(
        self, info: strawberry.Info, turn: str, wait_seconds: int | None = None
    ) -> JanusAnswer:
        from plugins.installed.agent_mcp.janus_door import DoorError, reply

        entry, denied = _caller(info)
        if denied:
            return _refused(denied)
        try:
            return _answer(
                reply(entry=entry, turn=turn, wait_seconds=wait_seconds, surface='graphql')
            )
        except DoorError as e:
            return _refused(e.message)
