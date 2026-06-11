"""Shared LLM-output JSON parsing.

LLM "return strict JSON" prompts come back wrapped in markdown fences,
prefaced with apologies, with trailing commas, and frequently with
literal newlines inside string bodies. Each caller used to roll their
own parser; this module is the canonical extractor so the same
robustness lives in one place.

Public API: ``parse_llm_json(raw)`` — returns ``dict | list | None``.

Returns ``None`` only when no JSON object/array can be recovered
even after repair. Empty dicts / lists return as-is.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger('morpheus.llm_parsing')


def parse_llm_json(raw: str) -> Any:
    """Extract the JSON payload an LLM was asked to return.

    Steps:
      1. Strip leading/trailing ```json fences if present.
      2. Slice down to the outermost {...} OR [...] block.
      3. Try strict ``json.loads`` first.
      4. On failure, run a single repair pass: drop trailing commas
         before ``}``/``]`` and escape literal newlines/CRs/tabs that
         appear *inside* string literals.

    Returns the parsed dict / list. Returns ``None`` if nothing
    recognisable could be extracted; this signals "ask again" or
    "fall back" to the caller. Empty container literals (``{}``,
    ``[]``) return as-is — they're successful parses.
    """
    if not raw:
        return None
    txt = raw.strip()

    # Strip code fences.
    if txt.startswith('```'):
        txt = re.sub(r'^```[a-zA-Z]*\n?', '', txt)
    if txt.endswith('```'):
        txt = txt[:-3]
    txt = txt.strip()

    # Find the outermost container. Prefer {…} (most prompts ask for
    # an object); fall back to […] when the model returned a top-level
    # array.
    candidate = _outermost_block(txt)
    if candidate is None:
        return None

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    repaired = re.sub(r',\s*([}\]])', r'\1', candidate)
    repaired = _escape_literal_whitespace_in_strings(repaired)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as e:
        logger.warning(
            'parse_llm_json: JSON parse failed after repair: %s. First 200 of candidate: %s',
            e,
            candidate[:200],
        )
        return None


def _outermost_block(txt: str) -> str | None:
    """Return the slice from the first '{' or '[' to the matching last '}' or ']'."""
    obj_start, arr_start = txt.find('{'), txt.find('[')
    if obj_start == -1 and arr_start == -1:
        return None
    if obj_start == -1:
        start, closer = arr_start, ']'
    elif arr_start == -1 or obj_start < arr_start:
        start, closer = obj_start, '}'
    else:
        start, closer = arr_start, ']'
    end = txt.rfind(closer)
    if end <= start:
        return None
    return txt[start : end + 1]


def _escape_literal_whitespace_in_strings(s: str) -> str:
    """Replace literal \\n / \\r / \\t inside JSON string literals with
    their escape sequences. Tiny state machine — anything between an
    unescaped " and the matching " is a string body. Doesn't try to be
    a full JSON repairer; just handles the single most common LLM
    error mode (multi-line description fields)."""
    out: list[str] = []
    in_str = False
    escape = False
    for ch in s:
        if escape:
            out.append(ch)
            escape = False
            continue
        if ch == '\\':
            out.append(ch)
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            out.append(ch)
            continue
        if in_str and ch == '\n':
            out.append('\\n')
            continue
        if in_str and ch == '\r':
            out.append('\\r')
            continue
        if in_str and ch == '\t':
            out.append('\\t')
            continue
        out.append(ch)
    return ''.join(out)
