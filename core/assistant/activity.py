"""What Linda is doing right now, for the chat to show while a turn runs.

Janus fires its tool hooks for every step, its own tools (plan, web search,
playbooks, memory) and the store's tools over MCP alike. The generated config
points both hooks at :mod:`core.assistant.janus_progress_hook`, which appends
one JSON line per step to the conversation home's progress file. The turn reads
the new lines on every tick (:class:`ProgressReader`) and streams them as chat
events:

* ``{type: 'step', id, state: 'running'|'done'|'error', tool, label,
  done_label, detail, ms, store_tool}`` — one per tool call, sent when it starts
  and again when it ends;
* ``{type: 'plan', items: [{id, text, status}]}`` — Linda's plan after each
  update, from the todo tool's own result (the full list, even after a
  partial update).

Hooks fail open in Janus, so nothing here may matter to safety: it is a display.
The store tool's arguments and output still reach the chat from the rows the
MCP edge records (:func:`core.assistant.runtime._tool_events`).
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger('morpheus.assistant.activity')

PROGRESS_FILE = 'progress.jsonl'
HOOK_SCRIPT = Path(__file__).resolve().with_name('janus_progress_hook.py')
# Janus's name for a store tool: ``mcp_<server>_<tool>``, non-word characters
# replaced by ``_`` (tools/mcp_tool.py: sanitize_mcp_name_component).
_STORE_PREFIX = 'mcp_morpheus_admin_'
_MAX_READ = 256 * 1024

# Janus's own tools: (doing, done). Anything else gets its name, humanised.
_NATIVE = {
    'web_search': ('Searching the web', 'Searched the web'),
    'session_search': (
        'Looking back through this conversation',
        'Looked back through this conversation',
    ),
    'skills_list': ('Checking her playbooks', 'Checked her playbooks'),
    'skill_view': ('Reading a playbook', 'Read a playbook'),
    'skill_manage': ('Writing a playbook', 'Wrote a playbook'),
    'memory': ('Saving a note', 'Saved a note'),
    'recall_memory': ('Recalling her notes', 'Recalled her notes'),
    'recall_lessons': ('Recalling past lessons', 'Recalled past lessons'),
    'pin_agreement': ('Noting what you agreed', 'Noted what you agreed'),
    'recall_agreements': ('Recalling what you agreed', 'Recalled what you agreed'),
    'propose_plan': ('Drafting a plan', 'Drafted a plan'),
}
# Which argument says what a native step is about.
_DETAIL_ARG = {'web_search': 'query', 'session_search': 'query', 'skill_view': 'name'}

# Store areas, in the merchant's words. Unlisted areas are humanised.
_AREAS = {
    'products': 'products',
    'catalog': 'the catalog',
    'inventory': 'stock',
    'seo': 'SEO',
    'i18n': 'translations',
    'plugins': 'apps',
    'rbac': 'roles',
    'crm': 'customer messages',
    'cms': 'pages',
    'fs': 'files',
    'db': 'the database',
}


def hooks_config(progress_path: Path) -> str:
    """The config.yaml block that makes Janus report each step to ``progress_path``.

    ``hooks_auto_accept`` stands in for the consent prompt Janus shows at a TTY
    the first time it sees a hook; the command is written here, never by the model.
    """
    command = shlex.join([sys.executable, '-I', '-S', str(HOOK_SCRIPT), str(progress_path)])
    entry = f'    - command: {json.dumps(command)}\n      timeout: 5\n'
    return f'hooks_auto_accept: true\nhooks:\n  pre_tool_call:\n{entry}  post_tool_call:\n{entry}'


def _humanise(name: str) -> str:
    words = re.sub(r'[_\W]+', ' ', name).strip()
    return words[:1].upper() + words[1:] if words else 'A step'


def _store_tools() -> list:
    """Every store tool, the way the MCP edge builds its catalogue (core only)."""
    from core.agents import agent_registry
    from core.assistant.tools import get_default_tools

    return [*get_default_tools(), *agent_registry.platform_tools()]


def _sanitised(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9_]', '_', name)


class ProgressReader:
    """Reads what the hook wrote since the last read, as chat events."""

    def __init__(self, path: Path):
        self.path = path
        self.offset = 0
        self._seq = 0
        self._open: list[dict] = []
        self._store: dict[str, Any] | None = None

    def reset(self) -> None:
        """Start the turn with an empty file, so no step from the last turn replays."""
        self.offset = 0
        with contextlib.suppress(OSError):
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            os.close(fd)

    def read(self) -> list[dict]:
        try:
            with self.path.open('rb') as fh:
                fh.seek(self.offset)
                chunk = fh.read(_MAX_READ)
        except OSError:
            return []
        end = chunk.rfind(b'\n')
        if end < 0:
            return []  # nothing, or a line the hook is still writing
        self.offset += end + 1
        events: list[dict] = []
        for raw in chunk[:end].splitlines():
            try:
                rec = json.loads(raw)
            except ValueError:
                continue
            if isinstance(rec, dict):
                events.extend(self._events(rec))
        return events

    def _events(self, rec: dict) -> list[dict]:
        tool = str(rec.get('tool') or '')
        if tool == 'todo':
            plan = _plan(rec) if rec.get('ev') == 'end' else None
            return [{'type': 'plan', 'items': plan}] if plan is not None else []
        if rec.get('ev') == 'start':
            self._seq += 1
            step = {'type': 'step', 'id': f's{self._seq}', 'state': 'running', 'ms': None}
            step.update(self._describe(tool, rec.get('args')))
            self._open.append({'call': str(rec.get('id') or ''), 'step': step})
            return [step]
        if rec.get('ev') == 'end':
            opened = self._close(tool, str(rec.get('id') or ''))
            if opened is None:
                return []
            failed = rec.get('status') not in ('ok', 'success', '') or bool(rec.get('error'))
            ms = rec.get('ms')
            return [
                {
                    **opened,
                    'state': 'error' if failed else 'done',
                    'ms': int(ms) if isinstance(ms, (int, float)) else None,
                }
            ]
        return []

    def _close(self, tool: str, call: str) -> dict | None:
        for i, item in enumerate(self._open):
            same = item['call'] == call if call else item['step']['tool'] == tool
            if same:
                return self._open.pop(i)['step']
        return None

    def _describe(self, tool: str, args: Any) -> dict:
        args = args if isinstance(args, dict) else {}
        out = {'tool': tool, 'store_tool': '', 'detail': ''}
        if tool.startswith(_STORE_PREFIX):
            return {**out, **self._describe_store(tool[len(_STORE_PREFIX) :])}
        doing, done = _NATIVE.get(tool, (_humanise(tool), _humanise(tool)))
        detail = args.get(_DETAIL_ARG.get(tool, ''), '')
        return {**out, 'label': doing, 'done_label': done, 'detail': str(detail or '')[:160]}

    def _describe_store(self, suffix: str) -> dict:
        if self._store is None:
            try:
                self._store = {_sanitised(t.name): t for t in _store_tools()}
            except Exception:  # noqa: BLE001 — a label is not worth failing a turn
                logger.debug('activity: store tool names unavailable', exc_info=True)
                self._store = {}
        tool = self._store.get(suffix)
        if tool is None:
            label = _humanise(suffix)
            return {'label': label, 'done_label': label}
        from core.assistant.gates import is_write_tool

        area, _, action = tool.name.partition('.')
        noun = _AREAS.get(area, _humanise(area).lower())
        write = is_write_tool(tool)
        return {
            'label': f'{"Updating" if write else "Checking"} {noun}',
            'done_label': f'{"Updated" if write else "Checked"} {noun}',
            'detail': _humanise(action).lower(),
            'store_tool': tool.name,
        }


def _plan(rec: dict) -> list[dict] | None:
    try:
        todos = json.loads(rec.get('result') or '').get('todos')
    except (ValueError, AttributeError):
        return None
    if not isinstance(todos, list):
        return None
    items = []
    for t in todos[:30]:
        if isinstance(t, dict) and str(t.get('content') or '').strip():
            items.append(
                {
                    'id': str(t.get('id') or '')[:40],
                    'text': str(t['content']).strip()[:200],
                    'status': str(t.get('status') or 'pending')[:20],
                }
            )
    return items
