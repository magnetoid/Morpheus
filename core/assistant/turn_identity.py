"""Signed, short-lived identity for one Linda turn on the Janus engine.

Janus runs in a subprocess and reaches the store's tools over MCP. Without this,
every call arrives as the shared ``mcp-service`` user holding a standing token,
so the MCP edge cannot tell which merchant is talking, in which conversation, or
under which mode — and therefore cannot apply the consent kernel, the mode
filter, or a human-attributed audit. A static token was also the only way to
give Janus store tools at all, and that token's ``approved_tools`` grant is the
exact standing-consent hole ``core/assistant/consent.py`` exists to close.

A turn token carries only what the edge needs to enforce the same gates the
in-process loop applies: the acting staff user, the conversation, the RESOLVED
mode, and an expiry. It is signed with ``SECRET_KEY`` under a dedicated salt, so
nothing reading it can forge or widen one, and it dies with the turn. It is
handed to Janus through the environment and referenced from the MCP config as
``${LINDA_TURN_TOKEN}``, so no credential is ever written to disk.

The edge re-checks the user on every call (still active, still staff) and
re-resolves the mode against that user, so demoting someone mid-turn takes
effect at their next tool call rather than at token expiry.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

from django.core import signing

#: Distinguishes a turn token from an ordinary MCP API key on the same header.
PREFIX = 'lt1.'
#: Env var the Janus subprocess receives; the MCP header references it.
ENV_VAR = 'LINDA_TURN_TOKEN'

_SALT = 'morpheus.assistant.turn-identity.v1'


@dataclass(frozen=True, slots=True)
class TurnIdentity:
    user_id: str
    conversation_key: str
    mode: str
    expires_at: int


def is_turn_token(token: str) -> bool:
    return bool(token) and token.startswith(PREFIX)


def mint(*, user, conversation_key: str, mode_slug: str, ttl_s: int) -> str:
    """Sign a token for one turn. ``ttl_s`` should cover the turn timeout."""
    payload = {
        'u': str(user.pk),
        'c': conversation_key,
        'm': mode_slug,
        'x': int(time.time()) + max(1, int(ttl_s)),
        # Two turns minted in the same second must not produce identical tokens.
        'n': secrets.token_hex(8),
    }
    return PREFIX + signing.dumps(payload, salt=_SALT, compress=True)


def verify(token: str) -> TurnIdentity | None:
    """The identity a token carries, or None if it is forged, malformed or expired."""
    if not is_turn_token(token):
        return None
    try:
        payload = signing.loads(token[len(PREFIX) :], salt=_SALT)
    except signing.BadSignature:
        return None
    if not isinstance(payload, dict):
        return None
    user_id, conv, mode, expires = (payload.get(k) for k in ('u', 'c', 'm', 'x'))
    well_formed = (
        isinstance(user_id, str)
        and bool(user_id)
        and isinstance(conv, str)
        and bool(conv)
        and isinstance(mode, str)
        and isinstance(expires, int)
    )
    if not well_formed or expires < int(time.time()):
        return None
    return TurnIdentity(user_id=user_id, conversation_key=conv, mode=mode, expires_at=expires)


def resolve_user(identity: TurnIdentity):
    """The staff user behind a turn, or None if they are no longer staff/active."""
    from django.contrib.auth import get_user_model

    return (
        get_user_model().objects.filter(pk=identity.user_id, is_active=True, is_staff=True).first()
    )
