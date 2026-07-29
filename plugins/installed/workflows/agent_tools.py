"""Workflows agent tools.

workflows.run was migrated here from core/assistant/tools/admin_ops.py so the
Workflow lookup + engine call live in the plugin that owns them (boundary
ratchet — drops the last two admin_ops→workflows baseline rows). Tool name +
scopes unchanged — Linda sources it by name from the agent registry. The
confirm gate stays core (`_require_confirmed`), same as the metafields move.
"""

from __future__ import annotations

from core.assistant.tools.ecommerce_writes import _require_confirmed
from morpheus.core import ToolError, ToolResult, tool


@tool(
    name='workflows.run',
    description=(
        'Run a saved workflow by name against a payload. dry_run=True (default) '
        'evaluates safely without firing actions; to actually fire, pass '
        'dry_run=False AND confirmed=True after the user approves.'
    ),
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'payload': {'type': 'object', 'default': {}},
            'dry_run': {'type': 'boolean', 'default': True},
            'confirmed': {'type': 'boolean', 'default': False},
        },
        'required': ['name'],
    },
    requires_approval=True,
)
def workflows_run_tool(
    *, name: str, payload: dict | None = None, dry_run: bool = True, confirmed: bool = False
) -> ToolResult:
    if not dry_run:
        _require_confirmed(confirmed)
    from plugins.installed.workflows.engine import run_workflow
    from plugins.installed.workflows.models import Workflow

    wf = Workflow.objects.filter(name__iexact=name, is_active=True).first()
    if wf is None:
        raise ToolError(f'no active workflow named {name!r}')
    run = run_workflow(wf, payload or {}, dry_run=dry_run)
    return ToolResult(
        output={
            'workflow': name,
            'dry_run': dry_run,
            'state': getattr(run, 'state', None),
            'run_id': str(getattr(run, 'id', '')),
        },
        display=f'Workflow {name}: {getattr(run, "state", "?")} ({"dry-run" if dry_run else "live"}).',
    )
