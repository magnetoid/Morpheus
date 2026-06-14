"""platform.capabilities — Linda's self-awareness of her full control surface.

Linda already wields ~70 tools spanning the whole store (catalog, orders,
customers, settings, plugins, theme, updates, workflows, content, metafields,
…). The failure mode is not *missing* power but Linda forgetting she has it and
replying "I can't do that." This read-only tool lets her enumerate everything
she can do, grouped by domain, so she discovers the right tool before acting —
and so a merchant can ask "what can you control?" and get a true answer.
"""

from __future__ import annotations

from core.agents import tool
from core.agents.tools import ToolResult


@tool(
    name='platform.capabilities',
    description=(
        'List everything you can do across the store, grouped by domain '
        '(catalog, orders, settings, plugins, customers, cms, theme, …). Call '
        'this to answer "what can you do?" or to find the right tool before '
        'saying something is not possible.'
    ),
    scopes=[],  # read-only meta tool — safe for any caller
)
def capabilities_tool() -> ToolResult:
    from core.assistant.tools import get_default_tools

    seen: dict[str, str] = {}
    for t in get_default_tools():
        if t.name == 'platform.capabilities':
            continue  # don't list ourselves
        seen[t.name] = getattr(t, 'description', '') or ''

    # Plugin-contributed agent tools (registered after each plugin's ready()).
    try:
        from core.agents import agent_registry

        for t in agent_registry.platform_tools():
            seen.setdefault(t.name, getattr(t, 'description', '') or '')
    except Exception:  # noqa: BLE001, S110 — registry not ready (early boot / tests)
        pass

    groups: dict[str, list] = {}
    for name in sorted(seen):
        domain = name.split('.', 1)[0] if '.' in name else 'other'
        groups.setdefault(domain, []).append({'name': name, 'description': seen[name]})

    return ToolResult(
        output={'total': len(seen), 'domain_count': len(groups), 'domains': groups},
        display=f'{len(seen)} tools across {len(groups)} domains.',
    )


@tool(
    name='plugins.describe',
    description=(
        'Learn what an installed plugin does by inspecting it: its manifest '
        '(label, description, version, requires), the database models it owns '
        '(query them with db.* tools), the commands (agent tools) it gives you, '
        'and where its code/docs live (read them with fs.* tools). Use this to '
        'understand a plugin before operating it — especially one that exposes '
        'no commands yet.'
    ),
    scopes=['diagnostics.read'],
)
def plugins_describe_tool(*, name: str) -> ToolResult:
    from django.apps import apps

    from plugins.registry import plugin_registry

    slug = (name or '').strip()
    plugin = plugin_registry.get(slug)
    if plugin is None:
        active = sorted(p.name for p in plugin_registry.active_plugins())
        return ToolResult(
            output={'error': f'plugin {slug!r} is not active', 'active_plugins': active},
            display=f'No active plugin named {slug!r}.',
        )

    # Models this plugin owns — so Linda can query them via db.describe_model / db.count_rows.
    prefix = f'plugins.installed.{slug}.'
    models = sorted(
        {
            m.__name__
            for m in apps.get_models()
            if (getattr(m, '__module__', '') or '').startswith(prefix)
        }
    )

    # Commands the plugin delivers to Linda via the SDK (contribute_agent_tools).
    try:
        commands = [
            {'name': t.name, 'description': getattr(t, 'description', '')}
            for t in (plugin.contribute_agent_tools() or [])
        ]
    except Exception:  # noqa: BLE001
        commands = []

    info = {
        'name': plugin.name,
        'label': getattr(plugin, 'label', ''),
        'description': getattr(plugin, 'description', ''),
        'version': getattr(plugin, 'version', ''),
        'requires': list(getattr(plugin, 'requires', []) or []),
        'has_models': bool(getattr(plugin, 'has_models', False)),
        'models': models,
        'commands': commands,
        'code_path': f'plugins/installed/{slug}/',
        'hint': (
            'No commands? Operate this plugin by reading its models with db.* '
            'and its code/docs with fs.read_file / fs.search_files under code_path.'
        ),
    }
    return ToolResult(
        output=info,
        display=f'{plugin.label or slug}: {len(commands)} command(s), {len(models)} model(s).',
    )
