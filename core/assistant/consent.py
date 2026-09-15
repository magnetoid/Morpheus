"""Kernel-verified human consent for Linda's approval-required tools.

**The hole this closes.** Linda's write tools have always gated on an
LLM-supplied ``confirmed=True`` argument (plus ``hard_gate_ack``/``echo`` on the
destructive tier). Those arguments are produced by *the model*, so they attest
nothing: content Linda reads — a product description, a log line, a customer
note, a fetched page — can induce her to pass ``confirmed=True`` on the very
first call. The docstrings promised "the LLM cannot mutate state without first
asking the user"; nothing enforced it.

**The fix.** Consent moves out of the tool arguments and into the kernel:

1. First attempt of an approval-required tool → **deny**, and record a pending
   consent bound to ``sha256(tool + canonical args)`` for this conversation.
2. Linda tells the human exactly what she wants to do.
3. The human answers **in their own turn** — a ``role='user'`` message, which is
   the one thing injected content can never become.
4. Next attempt with the **same fingerprint** → the kernel checks the human's
   latest message is affirmative **and was sent after the proposal** → allow
   **once**, then consume the grant.

The ordering check matters. Without it, "set the price to 20, ok?" is spent by
its own "ok": the first attempt is refused and recorded, and an immediate retry
in the same turn finds an affirmative human message waiting. The human never saw
the proposal. An agent that retries a refused call inside one turn — Janus does —
would approve itself.

Grants are single-use and fingerprint-bound, so an approval given for a benign
call can't be spent on a different one (same invariant as
``core.agents.approval.args_fingerprint``). Negation always wins over
affirmation, so "yes, but not the reviews one" denies rather than proceeds.

The ledger lives in the Django cache: consent is short-lived by nature, and a
lost entry fails **closed** (re-ask the human) rather than open.
"""

from __future__ import annotations

import re
import time

from django.core.cache import cache

from core.agents.approval import args_fingerprint

# A pending consent outlives the assistant's reply and the human's reading time,
# but not a coffee break — a stale "yes" should not authorise an action proposed
# half an hour ago.
CONSENT_TTL_SECONDS = 600

_CACHE_PREFIX = 'assistant:consent:'

# Word-boundary matched so "know" never reads as "no" and "cancelled" doesn't
# swallow an unrelated sentence. Negation is checked first and wins outright.
_NEGATIVE = re.compile(
    r"\b(no|nope|nah|don'?t|do not|stop|cancel|cancelled|abort|wait|"
    r'never|nevermind|never mind|not yet|hold on|undo|reject|rejected|'
    r'disregard|scratch that)\b',
    re.IGNORECASE,
)
_AFFIRMATIVE = re.compile(
    r'\b(yes|yep|yeah|yup|ya|sure|ok|okay|confirm|confirmed|approve|approved|'
    r'go ahead|go for it|do it|proceed|continue|affirmative|please do|'
    r'sounds good|permission granted|granted)\b',
    re.IGNORECASE,
)


# Arguments the model sets to attest it asked. They carry no consent, so they
# are not part of what the merchant approves: "yes" to refunding order #1234
# must match the retry that adds `confirmed=True`, or the merchant is asked again.
_SELF_ATTESTED = frozenset({'confirmed', 'hard_gate_ack', 'echo'})


def _key(conversation_key: str, fingerprint: str) -> str:
    return f'{_CACHE_PREFIX}{conversation_key}:{fingerprint}'


def _fingerprint(tool_name: str, args: dict | None) -> str:
    return args_fingerprint(
        tool_name, {k: v for k, v in (args or {}).items() if k not in _SELF_ATTESTED}
    )


def is_affirmative(message: str) -> bool:
    """True when a human message reads as an unqualified go-ahead.

    Negation wins: "yes, but skip the second one" is *not* consent, because the
    human is amending the proposal rather than accepting it. Failing that way
    costs one extra round trip; failing the other way executes something the
    human tried to stop.
    """
    text = (message or '').strip()
    if not text:
        return False
    if _NEGATIVE.search(text):
        return False
    return bool(_AFFIRMATIVE.search(text))


def request(*, conversation_key: str, tool_name: str, args: dict | None) -> str:
    """Record that Linda proposed this exact call and is awaiting a human yes.

    Returns the fingerprint (useful for tests and audit). Idempotent — a
    re-proposal of the same call just refreshes the TTL.
    """
    fp = _fingerprint(tool_name, args)
    cache.set(_key(conversation_key, fp), {'proposed_at': time.time()}, CONSENT_TTL_SECONDS)
    return fp


def consume(
    *,
    conversation_key: str,
    tool_name: str,
    args: dict | None,
    human_message: str,
    human_message_at: float | None = None,
) -> bool:
    """Spend a pending consent for this exact call, if the human just said yes.

    All must hold: a consent was *proposed* for this fingerprint, the human's
    message was sent *after* that proposal (so they saw what they were agreeing
    to), and it is affirmative. Single-use — the entry is deleted on success so a single
    "yes" can't authorise a repeated action.
    """
    fp = _fingerprint(tool_name, args)
    key = _key(conversation_key, fp)
    entry = cache.get(key)
    # A pre-v0.64 plain 'pending' entry has no proposal time: fail closed, re-ask.
    if not isinstance(entry, dict):
        return False
    # ``human_message_at`` (epoch seconds) must postdate the proposal. Callers
    # that cannot supply it pass None and skip only this check.
    if human_message_at is not None and human_message_at <= float(entry.get('proposed_at') or 0):
        return False
    if not is_affirmative(human_message):
        return False
    cache.delete(key)
    return True


def clear(*, conversation_key: str, tool_name: str, args: dict | None) -> None:
    """Drop a pending consent (tests / explicit cancellation)."""
    cache.delete(_key(conversation_key, args_fingerprint(tool_name, args)))
