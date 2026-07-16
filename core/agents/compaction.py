"""Context-window compaction — keep an agent's message list under a soft token
budget by replacing the oldest turns with a rolling summary.

Cheap by default: :func:`estimate_tokens` is a chars/4 heuristic (no tokenizer
dependency, no API call), and :func:`compact` is a no-op until the estimate
crosses ``soft_limit`` — so short conversations pay nothing. When it does
compact, it keeps a leading system message + the most recent ``keep_recent``
messages verbatim and replaces the middle with one ``summarizer`` call. If the
summarizer is absent or fails, it falls back to plain truncation, so a run is
never broken by compaction.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from core.agents.llm import LLMMessage

logger = logging.getLogger('morpheus.agents.compaction')

DEFAULT_SOFT_LIMIT = 6000  # ~tokens; conservative vs. real context windows
DEFAULT_KEEP_RECENT = 6  # most-recent messages kept verbatim


def estimate_tokens(messages: list[LLMMessage]) -> int:
    """Cheap, dependency-free token estimate (~4 chars/token)."""
    chars = 0
    for m in messages:
        chars += len(m.content or '')
        for tc in m.tool_calls or []:
            chars += len(str(tc.arguments))
    return chars // 4


def compact(
    messages: list[LLMMessage],
    *,
    soft_limit: int = DEFAULT_SOFT_LIMIT,
    keep_recent: int = DEFAULT_KEEP_RECENT,
    summarizer: Callable[[str], str] | None = None,
) -> list[LLMMessage]:
    """Return a possibly-compacted copy of ``messages``.

    No-op (returns the same list) while the estimate is under ``soft_limit`` or
    there's nothing in the middle to summarize.
    """
    if estimate_tokens(messages) <= soft_limit:
        return messages

    head: list[LLMMessage] = []
    body = list(messages)
    if body and body[0].role == 'system':
        head = [body[0]]
        body = body[1:]
    if len(body) <= keep_recent:
        return messages  # only the recent window + head remain; nothing to drop

    middle, recent = body[:-keep_recent], body[-keep_recent:]
    # The kept window must never START with `tool` messages — the index cut
    # can land between an assistant tool_calls message and its tool results,
    # and once the assistant half is summarized away the orphaned tool rows
    # violate the OpenAI-compatible contract (strict providers 400 the whole
    # request). Shift the boundary so the pair stays together in the middle,
    # where it becomes plain summary text.
    while recent and getattr(recent[0], 'role', '') == 'tool':
        middle.append(recent.pop(0))
    if not recent:
        return messages
    summary = _summarize(middle, summarizer)
    if summary is None:
        # Truncation fallback — drop the oldest middle entirely.
        return head + recent
    summary_msg = LLMMessage(role='system', content=f'Summary of earlier conversation:\n{summary}')
    return head + [summary_msg] + recent


def _summarize(middle: list[LLMMessage], summarizer: Callable[[str], str] | None) -> str | None:
    if summarizer is None or not middle:
        return None
    transcript = '\n'.join(f'{m.role}: {m.content}' for m in middle if m.content)
    if not transcript.strip():
        return None
    try:
        out = summarizer(transcript)
    except Exception:  # noqa: BLE001 — compaction must never break the run
        logger.warning('compaction: summarizer failed; truncating instead', exc_info=True)
        return None
    text = (out or '').strip()
    return text or None
