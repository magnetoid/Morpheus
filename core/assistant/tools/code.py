"""Linda's sandboxed code execution — compose tools in Python (uplift Phase 2).

`run_python` lets Linda write a short script that calls her tools via a bridge,
instead of one tool-call per turn — collapsing multi-step read/analysis pipelines
into a single sandboxed run.

Safety (defence in depth):
  * Runs in the core AGENT sandbox (no import/file/network, AST-validated, 3s wall).
  * The bridge exposes ONLY the tools the current run is already authorized for
    (``agent.get_tools()`` — scope-filtered upstream) AND only NON-approval tools.
    So a script can never call an approval-gated write (those keep the normal
    human-in-the-loop flow) and can never exceed the run's existing privileges.
  * Per-script tool-call cap. No new scope is granted by running code.
"""

# ruff: noqa: PLC0415 — lazy imports keep tool resolution load-order-safe.
from __future__ import annotations

import json as _json
import logging

from core.assistant.tools.filesystem import ToolError, ToolResult, tool

logger = logging.getLogger('morpheus.assistant.code')

_MAX_TOOL_CALLS = 50


def _is_read_only(t) -> bool:
    """A tool is script-safe only if it's READ-ONLY: no declared scope mentions
    'write'. This excludes system.write tools that happen to be non-approval
    (delegate.spawn_workers, skills.distill, memory.remember/forget) — scripts
    get reads/analysis only; mutations keep the normal human-in-the-loop flow."""
    return not any('write' in s for s in (getattr(t, 'scopes', None) or []))


def _available_tools(agent) -> dict:
    """The script-callable tools, by name: non-approval AND read-only, drawn from
    the current run's authorized set (``agent.get_tools()`` — already scope-
    filtered) so a script can never exceed the run's privileges. Falls back to
    Linda's default catalog when called outside a run (tests)."""
    if agent is not None and hasattr(agent, 'get_tools'):
        tools = agent.get_tools()
    else:
        from core.assistant.tools import get_default_tools

        tools = get_default_tools()
    return {
        t.name: t
        for t in tools
        if not getattr(t, 'requires_approval', False)
        and _is_read_only(t)
        and t.name != 'run_python'
    }


@tool(
    name='run_python',
    description=(
        'Run a short Python script in a SANDBOX to compose tools in code instead '
        'of one call per turn. In the script: `call("<tool_name>", **kwargs)` runs '
        'a tool and returns its output; `list_tools()` lists what you can call; '
        '`json` is available; set `result` to your answer. Only READ/safe tools '
        'you already have are callable (no approval-gated writes — use the normal '
        'flow for those). No import/file/network; 3s timeout; 50-call cap.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'code': {
                'type': 'string',
                'description': 'Python. Use call(name, **kwargs) + list_tools(); set `result`.',
            },
            'description': {'type': 'string', 'default': ''},
        },
        'required': ['code'],
    },
)
def run_python_tool(*, code: str, agent=None, context=None, description: str = '') -> ToolResult:
    from core.agents.sandbox import SandboxError, run_sandboxed

    by_name = _available_tools(agent)
    calls: list[dict] = []

    # Distinguish "no scope model" from "explicitly empty scopes": kernel
    # Workers declare `.scopes` (empty = deny scoped tools), while Linda's
    # Assistant has no such attribute at all — her catalog is curated +
    # mode-filtered upstream, so the bridge must not dead-letter her.
    _declared_scopes = getattr(agent, 'scopes', None)
    agent_scopes = set(_declared_scopes or [])
    has_scope_model = _declared_scopes is not None

    def call(name, **kwargs):
        if len(calls) >= _MAX_TOOL_CALLS:
            raise RuntimeError(f'tool-call cap ({_MAX_TOOL_CALLS}) exceeded')
        t = by_name.get(name)
        if t is None:
            raise RuntimeError(
                f'tool {name!r} is not callable from a script '
                f'(read/safe tools only — see list_tools())'
            )
        # Defence in depth: Tool.invoke() does NOT enforce scopes (the runtime
        # does, pre-dispatch). The bridge bypasses that path, so re-check here —
        # but only when the caller actually models scopes (kernel Workers do;
        # an explicitly EMPTY scope list still means "deny scoped tools").
        # Linda's Assistant declares no `.scopes` at all; the old
        # `agent is not None` guard treated her as empty-scoped and wrongly
        # refused every scoped read tool, dead-lettering the bridge.
        if has_scope_model and not set(t.scopes or []).issubset(agent_scopes):
            raise RuntimeError(f'missing scope for {name!r}')
        res = t.invoke(dict(kwargs), agent=agent, context=context)
        calls.append({'tool': name})
        return getattr(res, 'output', res)

    def list_tools():
        return sorted(by_name.keys())

    try:
        result = run_sandboxed(
            code,
            extra_globals={'call': call, 'list_tools': list_tools, 'json': _json},
            timeout_ms=3000,
        )
    except SandboxError as e:
        raise ToolError(str(e)) from e

    return ToolResult(
        output={'result': result, 'tool_calls': calls, 'call_count': len(calls)},
        display=f'Ran script — {len(calls)} tool call(s).',
    )
