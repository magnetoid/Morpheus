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
        'Report what this store runs: version, commit, when it was installed, the backup of '
        'the database made before the last update that changed it, and whether the store '
        'can update itself. Where it can (a git checkout), also whether an update is '
        'available and how many commits behind upstream. Read-only.'
    ),
    scopes=['system.read'],
    schema={'type': 'object', 'properties': {}},
)
def updates_status_tool() -> ToolResult:
    from core.deploys import running_release  # noqa: PLC0415
    from core.updates import platform_update_status  # noqa: PLC0415
    from core.versioning import component_versions  # noqa: PLC0415

    running = running_release()
    status = platform_update_status(fetch=True)
    versions = component_versions()
    output = {'running': _as_json(running), 'platform': status, 'core': versions.get('core')}
    if not running['self_update']:
        return ToolResult(output=output, display=_built_image_summary(running, status))
    return ToolResult(
        output=output,
        display=(
            f'Update {status.get("available")} — deployed {status.get("current")}'
            f'{", " + str(status.get("behind")) + " behind" if status.get("behind") else ""}.'
        ),
    )


def _as_json(running: dict) -> dict:
    """running_release() with its times as ISO text: tool output is stored as JSON (the
    audit trail, Linda's chat history) with no encoder for dates."""
    backup = running['backup']
    return {
        **running,
        'deployed_at': running['deployed_at'].isoformat() if running['deployed_at'] else None,
        'backup': {**backup, 'taken_at': backup['taken_at'].isoformat()} if backup else None,
    }


def _built_image_summary(running: dict, status: dict) -> str:
    """What updates.status says on a store that cannot update itself."""
    parts = [f'Running {running["version"]}']
    if running['commit']:
        parts.append(f' (commit {running["commit_short"]})')
    if running['deployed_at']:
        parts.append(f', installed {running["deployed_at"]:%Y-%m-%d %H:%M} UTC')
    parts.append('. This store updates when a new version is released; it cannot update itself.')
    if status.get('available') == 'yes' and status.get('latest'):
        parts.append(f' {status["latest"]} is out.')
    if running['backup']:
        taken = running['backup']['taken_at']
        parts.append(
            f' Database backup from before the last update that changed it: {taken:%Y-%m-%d %H:%M} UTC.'
        )
    return ''.join(parts)


@tool(
    name='updates.apply',
    description=(
        'Apply the pending platform update (git fast-forward + backup + migrate '
        '+ healthcheck + auto-rollback). Only a store that runs from a git checkout can: '
        'check updates.status first. Anywhere else (a built image, like most stores) this '
        'answers that the store updates when a new version is released. '
        'DEPLOYMENT-MUTATING: after the user approves, pass confirmed=True, '
        'hard_gate_ack="YES", and echo="platform update". Requires '
        'MORPHEUS_SELF_UPDATE_ENABLED on the server.'
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
    from core.updates import apply_platform_update, can_self_update  # noqa: PLC0415

    if not can_self_update():
        return ToolResult(
            output={'ok': False, 'status': 'unavailable', 'reason': 'no git checkout'},
            display=(
                "This store can't update itself: it runs from a built image and updates "
                'when a new version is released. There is nothing to apply here.'
            ),
        )
    _require_confirmed(confirmed)
    _require_hard_gate(hard_gate_ack=hard_gate_ack, target_name='platform update', echo=echo)
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
    from plugins.registry import app_registry  # noqa: PLC0415

    instance = app_registry.get(plugin)
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
        from core.safety import protection_reason  # noqa: PLC0415

        reason = protection_reason(plugin)
        if reason:
            raise ToolError(f'{plugin!r} is protected and cannot be disabled ({reason}). Refused.')
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


@tool(
    name='theme.activate',
    description=(
        'Switch the active storefront theme by name. SITE-WIDE change — after '
        'the user approves, pass confirmed=True, hard_gate_ack="YES", and '
        'echo=<the theme name typed back>.'
    ),
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {
            'theme': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
            'hard_gate_ack': {'type': 'string', 'default': ''},
            'echo': {'type': 'string', 'default': ''},
        },
        'required': ['theme'],
    },
    requires_approval=True,
)
def theme_activate_tool(
    *, theme: str, confirmed: bool = False, hard_gate_ack: str = '', echo: str = ''
) -> ToolResult:
    _require_confirmed(confirmed)
    _require_hard_gate(hard_gate_ack=hard_gate_ack, target_name=theme, echo=echo)
    from themes.models import ThemeConfig  # noqa: PLC0415
    from themes.registry import theme_registry  # noqa: PLC0415

    if theme_registry.get(theme) is None:
        discovered = sorted(t.name for t in theme_registry.all_themes())
        raise ToolError(f'theme {theme!r} not found among {discovered}')
    errors = theme_registry.validate_active_theme_for(theme)
    if errors:
        raise ToolError('; '.join(errors))
    row, _ = ThemeConfig.objects.get_or_create(theme_name=theme)
    row.is_active = True
    row.save()  # ThemeConfig.save() deactivates the others
    theme_registry.set_active(theme)
    return ToolResult(output={'active_theme': theme}, display=f'Activated theme {theme}.')


# workflows.run migrated to plugins/installed/workflows/agent_tools.py (boundary
# ratchet) — Linda sources it by name via tools/__init__.py `_migrated_names`.
