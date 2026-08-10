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
   latest message is affirmative → allow **once**, then consume the grant.

Grants are single-use and fingerprint-bound, so an approval given for a benign
call can't be spent on a different one (same invariant as
``core.agents.approval.args_fingerprint``). Negation always wins over
affirmation, so "yes, but not the reviews one" denies rather than proceeds.

The ledger lives in the Django cache: consent is short-lived by nature, and a
lost entry fails **closed** (re-ask the human) rather than open.
"""

from __future__ import annotations

import re

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


def _key(conversation_key: str, fingerprint: str) -> str:
    return f'{_CACHE_PREFIX}{conversation_key}:{fingerprint}'


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
    fp = args_fingerprint(tool_name, args)
    cache.set(_key(conversation_key, fp), 'pending', CONSENT_TTL_SECONDS)
    return fp


def consume(
    *, conversation_key: str, tool_name: str, args: dict | None, human_message: str
) -> bool:
    """Spend a pending consent for this exact call, if the human just said yes.

    Both conditions must hold: a consent was *proposed* for this fingerprint
    (so the human saw what they were agreeing to), and the human's current turn
    is affirmative. Single-use — the entry is deleted on success so a single
    "yes" can't authorise a repeated action.
    """
    fp = args_fingerprint(tool_name, args)
    key = _key(conversation_key, fp)
    if cache.get(key) != 'pending':
        return False
    if not is_affirmative(human_message):
        return False
    cache.delete(key)
    return True


def clear(*, conversation_key: str, tool_name: str, args: dict | None) -> None:
    """Drop a pending consent (tests / explicit cancellation)."""
    cache.delete(_key(conversation_key, args_fingerprint(tool_name, args)))
