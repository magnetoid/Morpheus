"""App tools — list apps, switch one on or off (through `plugins.services.set_enabled`)."""

from __future__ import annotations

from core.assistant.tools.filesystem import ToolError, ToolResult, tool


@tool(
    name='plugins.list',
    description=(
        'List every app with whether it is running, its version, what it requires, the '
        'Morpheus versions it supports, and, for an app that is switched on but not '
        'running, why (`not_running`: an unsupported Morpheus version, or a requirement '
        'that is missing or off).'
    ),
    scopes=['system.read'],
    schema={'type': 'object', 'properties': {}},
)
def list_plugins_tool() -> ToolResult:
    try:
        from plugins.registry import app_registry
    except Exception as e:  # noqa: BLE001
        return ToolResult(output={'plugins': [], 'note': f'registry unavailable: {e}'})
    rows = []
    for p in app_registry.all_plugins():
        rows.append(
            {
                'name': p.name,
                'label': p.label,
                'version': p.version,
                'active': app_registry.is_active(p.name),
                'requires': list(p.requires),
                'min_morpheus': p.min_morpheus,
                'max_morpheus': p.max_morpheus,
                'not_running': app_registry.skipped.get(p.name, ''),
            }
        )
    rows.sort(key=lambda r: r['name'])
    display = f'{sum(1 for r in rows if r["active"])} of {len(rows)} active'
    if stuck := sum(1 for r in rows if r['not_running']):
        display += f'; {stuck} switched on but not running'
    return ToolResult(output={'plugins': rows, 'count': len(rows)}, display=display)


@tool(
    name='plugins.enable',
    description=(
        'Switch an app on for the whole store: every web and background worker follows '
        'at its next request or task; its scheduled jobs and GraphQL fields change at the '
        'next restart. Refuses an app whose requirements are off.'
    ),
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    },
    requires_approval=True,
)
def enable_plugin_tool(*, name: str) -> ToolResult:
    switch = _switch(name, enabled=True)
    return ToolResult(
        output={'plugin': name, 'enabled': True},
        display=f'{switch.label} is on across the store',
    )


def _switch(name: str, *, enabled: bool):
    """Both tools go through the one writer every surface uses."""
    from plugins.services import AppSwitchRefused, set_enabled

    try:
        return set_enabled(name, enabled, actor='linda')
    except AppSwitchRefused as e:
        raise ToolError(f'refused: {e}') from e


@tool(
    name='plugins.disable',
    description=(
        'Switch an app off for the whole store: every web and background worker follows '
        'at its next request or task; its scheduled jobs and GraphQL fields change at the '
        'next restart. Refuses a protected app and an app another app that '
        'is on needs. HARD-GATED — pass `hard_gate_ack="YES"` AND `echo` (user types the '
        'app name back).'
    ),
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'hard_gate_ack': {'type': 'string'},
            'echo': {'type': 'string'},
        },
        'required': ['name'],
    },
    requires_approval=True,
)
def disable_plugin_tool(*, name: str, hard_gate_ack: str = '', echo: str = '') -> ToolResult:
    # Hard-gated — second confirmation + name echo required.
    from core.assistant.tools.ecommerce_writes import _require_hard_gate

    # Never disable a protected plugin (admin_dashboard/orders/…): disabling it
    # soft-bricks the platform. Checked before the confirmation gate so it fails
    # fast. Single source of truth is core.safety — the guard the registry + CLI
    # must also honour (plugin_toggle_softbrick).
    from core.safety import protection_reason  # noqa: PLC0415

    reason = protection_reason(name)
    if reason:
        raise ToolError(f'refused: {name} is protected and cannot be disabled ({reason})')
    _require_hard_gate(hard_gate_ack=hard_gate_ack, target_name=name, echo=echo)
    switch = _switch(name, enabled=False)
    return ToolResult(
        output={'plugin': name, 'enabled': False}, display=f'{switch.label} is off across the store'
    )
