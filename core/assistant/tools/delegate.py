"""Delegate tools — Linda routes work to background Workers.

After the agent_core pivot (see docs/plans/agent-core-into-core.md),
there is exactly one agent: ``worker``. Linda primarily fans out N
workers in parallel through ``delegate.spawn_workers`` /
``delegate.poll_workers`` / ``delegate.wait_for_workers`` (defined in
``core.assistant.tools.spawn``).

This module keeps:

  - ``delegate.list_agents`` — for introspection / debugging.
  - ``delegate.invoke_agent`` — compatibility shim that spawns one
    worker and waits for it. Old callers (and Linda's pre-pivot system
    prompt) keep working.
"""

from __future__ import annotations

from core.assistant.tools.filesystem import ToolError, ToolResult, tool


@tool(
    name='delegate.list_agents',
    description='List every agent the platform exposes (post-pivot: just `worker`).',
    scopes=['system.read'],
    schema={'type': 'object', 'properties': {}},
)
def list_available_agents_tool() -> ToolResult:
    try:
        from core.agents import agent_registry
    except Exception as e:  # noqa: BLE001
        return ToolResult(output={'agents': [], 'note': f'agent kernel unavailable: {e}'})
    rows = [
        {'name': a.name, 'label': a.label, 'audience': a.audience, 'description': a.description}
        for a in agent_registry.all_agents()
    ]
    rows.sort(key=lambda r: r['name'])
    return ToolResult(output={'agents': rows}, display=f'{len(rows)} agent(s)')


@tool(
    name='delegate.invoke_agent',
    description=(
        'Compatibility shim — runs a single Worker and waits for its result. '
        'For independent sub-tasks that can run in parallel, prefer '
        'delegate.spawn_workers + delegate.wait_for_workers.'
    ),
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {
            'agent_name': {
                'type': 'string',
                'description': 'Ignored post-pivot — always runs the generic worker.',
            },
            'objective': {'type': 'string', 'description': 'What the worker should do.'},
        },
        'required': ['objective'],
    },
)
def invoke_agent_tool(*, objective: str, agent_name: str = 'worker') -> ToolResult:
    from core.assistant.tools.spawn import spawn_workers_tool, wait_for_workers_tool

    spawn = spawn_workers_tool.invoke({'jobs': [{'objective': objective}]})
    spawn_data = spawn.output if hasattr(spawn, 'output') else spawn.get('output', {})
    run_ids = (spawn_data or {}).get('run_ids') or []
    if not run_ids:
        raise ToolError('spawn returned no run_ids')

    wait = wait_for_workers_tool.invoke({'run_ids': run_ids, 'timeout_s': 90})
    wait_data = wait.output if hasattr(wait, 'output') else wait.get('output', {})
    runs = (wait_data or {}).get('runs') or []
    first = runs[0] if runs else {}
    return ToolResult(
        output={
            'agent': 'worker',
            'state': first.get('state', 'unknown'),
            'text': first.get('final_text', ''),
            'error': first.get('error', ''),
        },
        display=(first.get('final_text') or first.get('error') or '')[:160],
    )
