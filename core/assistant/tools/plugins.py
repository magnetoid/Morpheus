"""Plugin management tools — list / enable / disable plugins."""

from __future__ import annotations

from core.assistant.tools.filesystem import ToolError, ToolResult, tool


@tool(
    name='plugins.list',
    description='List every Morpheus plugin with its active state and version.',
    scopes=['system.read'],
    schema={'type': 'object', 'properties': {}},
)
def list_plugins_tool() -> ToolResult:
    try:
        from plugins.registry import plugin_registry
    except Exception as e:  # noqa: BLE001
        return ToolResult(output={'plugins': [], 'note': f'registry unavailable: {e}'})
    rows = []
    for p in plugin_registry.all_plugins():
        rows.append(
            {
                'name': p.name,
                'label': p.label,
                'version': p.version,
                'active': plugin_registry.is_active(p.name),
                'requires': list(p.requires),
            }
        )
    rows.sort(key=lambda r: r['name'])
    return ToolResult(
        output={'plugins': rows, 'count': len(rows)},
        display=f'{sum(1 for r in rows if r["active"])} of {len(rows)} active',
    )


@tool(
    name='plugins.enable',
    description='Enable a plugin (writes PluginConfig.is_enabled=True). Restart needed for full effect.',
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    },
    requires_approval=True,
)
def enable_plugin_tool(*, name: str) -> ToolResult:
    try:
        from plugins.models import PluginConfig
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'plugins.models unavailable: {e}') from e
    cfg, _ = PluginConfig.objects.update_or_create(
        plugin_name=name,
        defaults={'is_enabled': True},
    )
    return ToolResult(
        output={'plugin': name, 'enabled': True},
        display=f'enabled {name} (restart for full effect)',
    )


@tool(
    name='plugins.disable',
    description=(
        'Disable a plugin (writes PluginConfig.is_enabled=False). HARD-GATED — '
        'pass `hard_gate_ack="YES"` AND `echo` (user types plugin name back).'
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

    _require_hard_gate(hard_gate_ack=hard_gate_ack, target_name=name, echo=echo)
    try:
        from plugins.models import PluginConfig
        from plugins.registry import plugin_registry
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'plugins.models unavailable: {e}') from e
    PluginConfig.objects.update_or_create(
        plugin_name=name,
        defaults={'is_enabled': False},
    )
    try:  # noqa: SIM105
        plugin_registry.deactivate(name)
    except Exception:  # noqa: BLE001, S110
        pass
    return ToolResult(output={'plugin': name, 'enabled': False}, display=f'disabled {name}')
