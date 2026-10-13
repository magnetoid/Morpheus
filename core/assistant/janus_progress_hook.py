"""Janus hook: append one line per step to the turn's progress file.

Janus runs this as its own process for every ``pre_tool_call`` and
``post_tool_call``, after every model call (``post_api_request``: the words the
model wrote before its tool calls, and the tokens it used) and when a model call
fails (``api_request_error``), wired by :func:`core.assistant.activity.hooks_config`,
with the event as JSON on stdin and the progress file as the only argument. The
chat reads that file while the turn runs (:class:`core.assistant.activity.ProgressReader`).

Two rules keep it harmless. It prints nothing: an empty stdout means "no
objection", so this hook can never block or rewrite a tool call. And it swallows
every failure: progress is something to look at, never part of the turn.

Janus starts it with ``python -I -S``, so only the standard library is
available, and it must stay that way (no Django, no Morpheus imports).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time

_MAX_ARGS = 2000  # characters of a tool's arguments kept for the display
_MAX_PLAN = 20000  # characters of the todo tool's result (the whole plan)
_MAX_SAY = 600  # characters of what the model says before its tool calls
# Reasoning some providers inline in the content; it is not what she says.
_THINKING = re.compile(r'<(think|thinking|reasoning)>.*?</\1>', re.S | re.I)


def _clip(args: dict) -> dict:
    text = json.dumps(args, ensure_ascii=False, default=str)
    if len(text) <= _MAX_ARGS:
        return args
    return {'_clipped': text[:_MAX_ARGS]}


def _int(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _model_call(extra: dict) -> dict:
    """What a model call said before its tool calls, and the tokens it used.

    The final answer reaches the chat the normal way, so a call with no tool
    calls keeps only its tokens. The request (the whole conversation) is dropped.
    """
    tools = _int(extra.get('assistant_tool_call_count')) or 0
    text = ''
    if tools:
        response = extra.get('response')
        message = response.get('assistant_message') if isinstance(response, dict) else None
        content = message.get('content') if isinstance(message, dict) else None
        if isinstance(content, str):
            text = _THINKING.sub('', content).strip()[:_MAX_SAY]
    usage = extra.get('usage')
    usage = usage if isinstance(usage, dict) else {}
    tokens = _int(usage.get('total_tokens'))
    if tokens is None:
        tokens = (_int(usage.get('input_tokens')) or 0) + (_int(usage.get('output_tokens')) or 0)
    return {
        't': round(time.time(), 3),
        'ev': 'call',
        'text': text,
        'tools': tools,
        'tokens': tokens,
    }


def _model_error(extra: dict) -> dict:
    """A failed model call: its HTTP status and whether Janus may try again
    (the same provider or a fallback one).

    The provider's error text stays out: it can quote a key or an account.
    """
    return {
        't': round(time.time(), 3),
        'ev': 'retry',
        'status': _int(extra.get('status_code')),
        'retry': bool(extra.get('retryable')),
    }


def record(payload: dict) -> dict | None:
    """The line to write for one hook call, or None when there is nothing to show."""
    event = payload.get('hook_event_name')
    extra = payload.get('extra')
    extra = extra if isinstance(extra, dict) else {}
    if event == 'post_api_request':
        return _model_call(extra)
    if event == 'api_request_error':
        return _model_error(extra)
    if event not in ('pre_tool_call', 'post_tool_call'):
        return None
    tool = str(payload.get('tool_name') or '')[:200]
    line = {
        't': round(time.time(), 3),
        'ev': 'start' if event == 'pre_tool_call' else 'end',
        'tool': tool,
        'id': str(extra.get('tool_call_id') or '')[:100],
    }
    args = payload.get('tool_input')
    if isinstance(args, dict):
        line['args'] = _clip(args)
    if event == 'post_tool_call':
        line['status'] = str(extra.get('status') or '')[:40]
        ms = extra.get('duration_ms')
        line['ms'] = ms if isinstance(ms, (int, float)) and not isinstance(ms, bool) else None
        if extra.get('error_message'):
            line['error'] = str(extra['error_message'])[:300]
        # Only the plan's result is kept: it is the whole list after a partial
        # update. Any other tool's output stays out of this file.
        if tool == 'todo' and isinstance(extra.get('result'), str):
            line['result'] = extra['result'][:_MAX_PLAN]
    return line


def main(argv: list[str], stdin) -> int:
    if len(argv) < 2:
        return 0
    try:
        payload = json.loads(stdin.read() or '{}')
        line = record(payload) if isinstance(payload, dict) else None
        if line is None:
            return 0
        data = (json.dumps(line, ensure_ascii=False, default=str) + '\n').encode('utf-8')
        # One write with O_APPEND: two hooks running at once (parallel tool
        # calls) each land a whole line.
        fd = os.open(argv[1], os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, data)
        finally:
            os.close(fd)
    except Exception:  # noqa: BLE001, S110 — a display must never fail a tool call
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv, sys.stdin))
