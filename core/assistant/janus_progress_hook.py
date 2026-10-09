"""Janus tool hook: append one line per tool step to the turn's progress file.

Janus runs this as its own process for every ``pre_tool_call`` and
``post_tool_call`` (wired by :func:`core.assistant.activity.hooks_config`), with
the step as JSON on stdin and the progress file as the only argument. The chat
reads that file while the turn runs (:class:`core.assistant.activity.ProgressReader`).

Two rules keep it harmless. It prints nothing: an empty stdout means "no
objection", so this hook can never block or rewrite a tool call. And it swallows
every failure: progress is something to look at, never part of the turn.

Janus starts it with ``python -I -S``, so only the standard library is
available, and it must stay that way (no Django, no Morpheus imports).
"""

from __future__ import annotations

import json
import os
import sys
import time

_MAX_ARGS = 2000  # characters of a tool's arguments kept for the display
_MAX_PLAN = 20000  # characters of the todo tool's result (the whole plan)


def _clip(args: dict) -> dict:
    text = json.dumps(args, ensure_ascii=False, default=str)
    if len(text) <= _MAX_ARGS:
        return args
    return {'_clipped': text[:_MAX_ARGS]}


def record(payload: dict) -> dict | None:
    """The line to write for one hook call, or None when there is nothing to show."""
    event = payload.get('hook_event_name')
    if event not in ('pre_tool_call', 'post_tool_call'):
        return None
    extra = payload.get('extra')
    extra = extra if isinstance(extra, dict) else {}
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
