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
    # 'selfdev' = Linda's self-development toolkit. Workers don't carry this scope,
    # so these tools stay Linda-only (the kernel assistant skips scope-filtering).
    scopes=['system.write', 'selfdev'],
    schema={
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'description': 'kebab/snake tool name, e.g. "low-stock-report".',
            },
            'source': {
                'type': 'string',
                'description': 'Full Python module source defining an @tool function.',
            },
            'rationale': {
                'type': 'string',
                'description': 'Why this tool is needed.',
                'default': '',
            },
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
        # Applied code lands under plugins/installed/ (ADR 0014: core/ is hard-
        # blocked; linda_generated is the disable-testable landing zone).
        target_path=f'plugins/installed/linda_generated/tools/{slug}.py',
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
    scopes=['system.read', 'selfdev'],
    schema={
        'type': 'object',
        'properties': {
            'status': {
                'type': 'string',
                'description': 'Filter: draft|approved|rejected|applied.',
                'default': '',
            },
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
    return ToolResult(
        output={'proposals': rows, 'count': len(rows)}, display=f'{len(rows)} proposal(s).'
    )


@tool(
    name='code.evaluate_proposal',
    description=(
        'Run a MULTI-MODEL consensus review of a drafted code proposal: several '
        'configured LLM providers independently critique it and a quorum decides. '
        'A model reviewing its own output rubber-stamps it, so cross-model review '
        'catches more. Advisory only — never auto-approves; a human still gates. '
        'Returns insufficient when <2 providers are configured.'
    ),
    scopes=['system.write', 'selfdev'],
    schema={
        'type': 'object',
        'properties': {'proposal_id': {'type': 'string'}},
        'required': ['proposal_id'],
    },
)
def code_evaluate_proposal_tool(*, proposal_id: str) -> ToolResult:
    from core.assistant.consensus import evaluate
    from core.assistant.models import CodeProposal

    proposal = CodeProposal.objects.filter(id=proposal_id).first()
    if proposal is None:
        raise ToolError(f'no proposal with id {proposal_id!r}')
    result = evaluate(proposal)
    proposal.consensus = result
    proposal.save(update_fields=['consensus', 'updated_at'])
    decision = result.get('decision')
    return ToolResult(
        output={
            'proposal_id': proposal_id,
            'decision': decision,
            'providers': result.get('providers', 0),
            'approvals': result.get('approvals', 0),
            'concerns': result.get('concerns', []),
            'note': result.get('note', ''),
        },
        display=(
            f'Consensus on "{proposal.name}": {decision} '
            f'({result.get("approvals", 0)}/{result.get("providers", 0)} approve). '
            f'Advisory — a human still approves before anything goes live.'
        ),
    )


@tool(
    name='code.apply_proposal',
    description=(
        'Apply an OWNER-APPROVED code proposal: write its source to a NEW git '
        'branch (never main), behind every gate (kill switch + re-scan + consensus '
        '+ path boundary + circuit breaker). DORMANT by default — does nothing '
        'unless ops set MORPHEUS_SELF_UPDATE_ENABLED AND the owner approved the '
        'proposal (via the selfdev_approve command). After the user approves, pass '
        'confirmed=True, hard_gate_ack="YES", and echo the proposal name. Never '
        'touches the live running code — the change lands ONLY on a selfdev/* '
        'branch for review (staging deploy / promote is a separate phase).'
    ),
    scopes=['system.write', 'selfdev'],
    schema={
        'type': 'object',
        'properties': {
            'proposal_id': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
            'hard_gate_ack': {'type': 'string', 'default': ''},
            'echo': {
                'type': 'string',
                'description': 'Type the proposal name to confirm.',
                'default': '',
            },
        },
        'required': ['proposal_id'],
    },
    requires_approval=True,
)
def code_apply_proposal_tool(
    *, proposal_id: str, confirmed: bool = False, hard_gate_ack: str = '', echo: str = ''
) -> ToolResult:
    from core.assistant.apply import apply_enabled, apply_proposal
    from core.assistant.models import CodeProposal

    proposal = CodeProposal.objects.filter(id=proposal_id).first()
    if proposal is None:
        raise ToolError(f'no proposal with id {proposal_id!r}')

    # Master kill switch — short-circuit while dormant so the gate prompts below
    # never even appear unless ops has armed self-update.
    if not apply_enabled():
        return ToolResult(
            output={
                'applied': False,
                'dormant': True,
                'reason': 'self-update disabled (MORPHEUS_SELF_UPDATE_ENABLED unset)',
            },
            display='Self-development apply is OFF (dormant). Nothing was written.',
        )

    # Type-to-confirm ack + echo (ADR 0014) on top of the recorded owner approval.
    if not confirmed:
        raise ToolError('re-call with confirmed=True after the owner has approved.')
    if (hard_gate_ack or '').strip().upper() != 'YES':
        raise ToolError('this writes code — pass hard_gate_ack="YES" and echo the proposal name.')
    if (echo or '').strip().lower() != (proposal.name or '').strip().lower():
        raise ToolError(f'echo mismatch — type the proposal name {proposal.name!r} to confirm.')

    result = apply_proposal(proposal)
    if result.get('applied'):
        return ToolResult(
            output=result,
            display=(
                f'Applied "{proposal.name}" to branch {result["branch"]} — '
                f'NOT live; awaiting review/deploy.'
            ),
        )
    return ToolResult(output=result, display=f'Apply blocked: {result.get("reason")}')
