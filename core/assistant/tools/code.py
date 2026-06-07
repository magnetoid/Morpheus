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

    agent_scopes = set(getattr(agent, 'scopes', None) or [])

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
        # does, pre-dispatch). The bridge bypasses that path, so re-check here.
        if agent is not None and not set(t.scopes or []).issubset(agent_scopes):
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


# ── Phase 4: self-written modules — DRAFT + review only (apply is gated/off) ──


@tool(
    name='code.draft_tool',
    description=(
        'Draft the Python SOURCE for a NEW agent tool and save it as a reviewable '
        'proposal. The source is statically safety-scanned (dangerous calls, '
        'hallucinated imports, shape) but is NEVER executed and NEVER written to '
        'the repo — a human reviews + applies it separately. Use when an existing '
        'tool is missing and you can write a small, safe one. Write a complete '
        'module that defines an @tool-decorated function.'
    ),
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {
            'name': {'type': 'string', 'description': 'kebab/snake tool name, e.g. "low-stock-report".'},
            'source': {'type': 'string', 'description': 'Full Python module source defining an @tool function.'},
            'rationale': {'type': 'string', 'description': 'Why this tool is needed.', 'default': ''},
        },
        'required': ['name', 'source'],
    },
)
def code_draft_tool(*, name: str, source: str, rationale: str = '') -> ToolResult:
    from django.utils.text import slugify

    from core.assistant.codegen import passed, scan_source
    from core.assistant.models import CodeProposal

    slug = slugify(name)[:120]
    if not slug:
        raise ToolError('name must be a non-empty identifier')
    findings = scan_source(source, kind='tool')
    ok = passed(findings)
    proposal = CodeProposal.objects.create(
        name=slug,
        kind='tool',
        rationale=rationale,
        target_path=f'core/assistant/tools/generated/{slug}.py',
        source=source,
        findings=findings,
        passed=ok,
        status='draft',
    )
    blocking = [f for f in findings if f.get('severity') in ('CRITICAL', 'HIGH')]
    return ToolResult(
        output={
            'proposal_id': str(proposal.id),
            'name': slug,
            'passed': ok,
            'findings': findings,
            'status': 'draft',
            'note': 'Saved as a DRAFT proposal. Not executed, not written to the repo — awaiting human review.',
        },
        display=(
            f'Drafted tool "{slug}" — {"clean scan ✓" if ok else f"{len(blocking)} blocking finding(s)"}. '
            f'Saved as a draft for human review (not live).'
        ),
    )


@tool(
    name='code.list_proposals',
    description=(
        'List your drafted code proposals with their scan status, so you (and the '
        'merchant) can see what is pending review. Read-only.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'status': {'type': 'string', 'description': "Filter: draft|approved|rejected|applied.", 'default': ''},
        },
    },
)
def code_list_proposals_tool(*, status: str = '') -> ToolResult:
    from core.assistant.models import CodeProposal

    qs = CodeProposal.objects.all()
    if status:
        qs = qs.filter(status=status)
    rows = [
        {
            'id': str(p.id),
            'name': p.name,
            'kind': p.kind,
            'status': p.status,
            'passed': p.passed,
            'findings': len(p.findings or []),
            'created_at': p.created_at.isoformat(),
        }
        for p in qs[:50]
    ]
    return ToolResult(output={'proposals': rows, 'count': len(rows)}, display=f'{len(rows)} proposal(s).')
