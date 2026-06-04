"""Platform-operations tools — let Linda run the shop, not just read it.

Self-update (status/apply), store config writes, and plugin enable/disable.
All mutations are two-step (`confirmed`); the deployment-mutating ones
(updates.apply, plugins.toggle) are hard-gated and respect the safety boundary
(PROTECTED_PLUGINS, opt-in self-update). Inventory/SEO/etc. stay Worker-
delegated (Linda spawns a skilled Worker) to keep core free of plugin imports.
"""

from __future__ import annotations

from core.assistant.tools.ecommerce_writes import _require_confirmed, _require_hard_gate
from core.assistant.tools.filesystem import ToolError, ToolResult, tool


@tool(
    name='updates.status',
    description=(
        'Report the platform update status: deployed version, whether an update '
        'is available, and how many commits behind upstream. Read-only.'
    ),
    scopes=['system.read'],
    schema={'type': 'object', 'properties': {}},
)
def updates_status_tool() -> ToolResult:
    from core.updates import platform_update_status  # noqa: PLC0415
    from core.versioning import component_versions  # noqa: PLC0415

    status = platform_update_status(fetch=True)
    versions = component_versions()
    return ToolResult(
        output={'platform': status, 'core': versions.get('core')},
        display=(
            f'Update {status.get("available")} — deployed {status.get("current")}'
            f'{", " + str(status.get("behind")) + " behind" if status.get("behind") else ""}.'
        ),
    )


@tool(
    name='updates.apply',
    description=(
        'Apply the pending platform update (git fast-forward + backup + migrate '
        '+ healthcheck + auto-rollback). DEPLOYMENT-MUTATING: after the user '
        'approves, pass confirmed=True, hard_gate_ack="YES", and echo="platform '
        'update". Requires MORPHEUS_SELF_UPDATE_ENABLED on the server.'
    ),
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {
            'confirmed': {'type': 'boolean', 'default': False},
            'hard_gate_ack': {'type': 'string', 'default': ''},
            'echo': {'type': 'string', 'default': ''},
        },
    },
    requires_approval=True,
)
def updates_apply_tool(
    *, confirmed: bool = False, hard_gate_ack: str = '', echo: str = ''
) -> ToolResult:
    _require_confirmed(confirmed)
    _require_hard_gate(hard_gate_ack=hard_gate_ack, target_name='platform update', echo=echo)
    from core.updates import apply_platform_update  # noqa: PLC0415

    result = apply_platform_update(confirm=True)
    return ToolResult(output=result, display=f'Update {result.get("status")}.')


@tool(
    name='settings.set',
    description=(
        'Set a store/plugin config value: pass `plugin` (the plugin name, e.g. '
        "'storefront'), `key`, and `value`. 'true'/'false'/integers are coerced "
        'to their types. confirmed=True after the user approves.'
    ),
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {
            'plugin': {'type': 'string'},
            'key': {'type': 'string'},
            'value': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
        },
        'required': ['plugin', 'key', 'value'],
    },
    requires_approval=True,
)
def settings_set_tool(*, plugin: str, key: str, value: str, confirmed: bool = False) -> ToolResult:
    _require_confirmed(confirmed)
    from plugins.registry import plugin_registry  # noqa: PLC0415

    instance = plugin_registry.get(plugin)
    if instance is None:
        raise ToolError(f'no such plugin: {plugin!r}')
    coerced: object = value
    low = value.strip().lower()
    if low in ('true', 'false'):
        coerced = low == 'true'
    elif value.strip().lstrip('-').isdigit():
        coerced = int(value.strip())
    try:
        instance.set_config(key, coerced)
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'could not set {plugin}.{key}: {e}') from e
    return ToolResult(
        output={'plugin': plugin, 'key': key, 'value': coerced},
        display=f'Set {plugin}.{key} = {coerced!r}.',
    )


@tool(
    name='plugins.toggle',
    description=(
        'Enable or disable a plugin (writes PluginConfig.is_enabled; a restart '
        'applies it fully). HARD-GATED + refuses protected plugins. Pass '
        '`plugin`, `enabled` (bool), confirmed=True, hard_gate_ack="YES", and '
        'echo=<the plugin name typed back>.'
    ),
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {
            'plugin': {'type': 'string'},
            'enabled': {'type': 'boolean'},
            'confirmed': {'type': 'boolean', 'default': False},
            'hard_gate_ack': {'type': 'string', 'default': ''},
            'echo': {'type': 'string', 'default': ''},
        },
        'required': ['plugin', 'enabled'],
    },
    requires_approval=True,
)
def plugins_toggle_tool(
    *,
    plugin: str,
    enabled: bool,
    confirmed: bool = False,
    hard_gate_ack: str = '',
    echo: str = '',
) -> ToolResult:
    _require_confirmed(confirmed)
    if not enabled:
        from core.safety import is_plugin_protected  # noqa: PLC0415

        if is_plugin_protected(plugin):
            raise ToolError(
                f'{plugin!r} is protected — disabling it would soft-brick the platform. Refused.'
            )
    _require_hard_gate(hard_gate_ack=hard_gate_ack, target_name=plugin, echo=echo)
    from plugins.models import PluginConfig  # noqa: PLC0415

    row, _ = PluginConfig.objects.get_or_create(plugin_name=plugin)
    row.is_enabled = bool(enabled)
    row.save(update_fields=['is_enabled', 'updated_at'])
    state = 'enabled' if enabled else 'disabled'
    return ToolResult(
        output={'plugin': plugin, 'enabled': bool(enabled)},
        display=f'{plugin} {state} (restart to apply fully).',
    )
