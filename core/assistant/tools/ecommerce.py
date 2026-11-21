"""Ecommerce read tools — give the Assistant first-class read access to
every commerce surface in the platform.

Each tool is read-only (`scopes=['system.read']`) and capped so a runaway
LLM call can't flood the conversation context. No write paths live here —
those route through the agent_core agents that already gate approval.

The tools are organised by domain:
  * orders.search / orders.get
  * products.search / products.get
  * customers.search / customers.get
  * analytics.summary / analytics.top_products
  * cms.pages
  * email.templates
  * settings.list / settings.describe
  * db.describe_model

Every tool uses lazy plugin imports so a missing plugin returns a clean
"plugin unavailable" message instead of breaking the Assistant.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from core.assistant.tools.filesystem import ToolError, ToolResult, tool


def _money_amount(value: Any) -> Decimal:
    """Pull the numeric amount out of a Money / Decimal / numeric value."""
    if value is None:
        return Decimal('0')
    amount = getattr(value, 'amount', value)
    try:
        return Decimal(str(amount))
    except Exception:  # noqa: BLE001
        return Decimal('0')


# ── Settings / configuration ────────────────────────────────────────────


def _plugin_settings(plugin_name: str) -> dict[str, dict]:
    from plugins import config_schema  # noqa: PLC0415
    from plugins.registry import app_registry  # noqa: PLC0415

    plugin = app_registry.get(plugin_name)
    return config_schema.properties(plugin) if plugin is not None else {}


@tool(
    name='settings.list',
    description=(
        "List every plugin's stored config (read-only). Returns a flat "
        "dict keyed by plugin name. Useful for confirming what's "
        'enabled, what API keys are stored (redacted), and which '
        'feature flags are set.'
    ),
    scopes=['system.read'],
    schema={'type': 'object', 'properties': {}},
)
def settings_list_tool() -> ToolResult:
    try:
        from plugins.models import PluginConfig
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'plugins.models unavailable: {e}') from e
    out: dict[str, Any] = {}
    from plugins import config_schema  # noqa: PLC0415

    for cfg in PluginConfig.objects.all():
        props = _plugin_settings(cfg.plugin_name)
        out[cfg.plugin_name] = {
            'is_enabled': cfg.is_enabled,
            'config': {
                k: config_schema.redact(v, config_schema.is_secret(k, props.get(k)))
                for k, v in (cfg.config or {}).items()
            },
        }
    return ToolResult(
        output={'plugins': out, 'count': len(out)}, display=f'{len(out)} plugin config(s)'
    )


@tool(
    name='settings.describe',
    description=(
        "Describe an app's settings (read-only): for each, its type, allowed "
        'values, default, current value (secrets redacted) and whether you may '
        'change it with settings.set. Pass `plugin` (the app name, e.g. '
        "'storefront'); without it, lists the apps that have settings."
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {'plugin': {'type': 'string', 'default': ''}},
    },
)
def settings_describe_tool(*, plugin: str = '') -> ToolResult:
    from plugins import config_schema  # noqa: PLC0415
    from plugins.registry import app_registry  # noqa: PLC0415

    if not plugin:
        apps = [
            {'plugin': p.name, 'label': p.label, 'settings': len(props)}
            for p in sorted(app_registry.active_plugins(), key=lambda p: p.name)
            if (props := config_schema.properties(p))
        ]
        return ToolResult(
            output={'apps': apps, 'count': len(apps)},
            display=f'{len(apps)} app(s) with settings',
        )
    instance = app_registry.get(plugin)
    if instance is None:
        raise ToolError(f'no such plugin: {plugin!r}')
    entries = config_schema.describe_settings(
        config_schema.properties(instance), instance.get_config()
    )
    return ToolResult(
        output={'plugin': plugin, 'label': instance.label, 'settings': entries},
        display=f'{len(entries)} setting(s) for {instance.label or plugin}',
    )


# ── Schema introspection ────────────────────────────────────────────────


@tool(
    name='db.describe_model',
    description=(
        'Return field schema for a Django model: `app_label.ModelName`. '
        'Use this when you need to know what fields are available before '
        'calling a more specific search tool.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {'model': {'type': 'string'}},
        'required': ['model'],
    },
)
def db_describe_model_tool(*, model: str) -> ToolResult:
    from django.apps import apps

    try:
        app_label, model_name = model.split('.', 1)
        m = apps.get_model(app_label, model_name)
    except (ValueError, LookupError) as e:
        raise ToolError(f'unknown model: {model}') from e
    fields = []
    for f in m._meta.get_fields():
        if f.auto_created and not getattr(f, 'concrete', False):
            # Skip reverse relations for brevity.
            continue
        fields.append(
            {
                'name': f.name,
                'type': f.__class__.__name__,
                'null': getattr(f, 'null', False),
                'unique': getattr(f, 'unique', False),
                'help_text': str(getattr(f, 'help_text', '') or '')[:120],
            }
        )
    return ToolResult(
        output={
            'model': f'{m._meta.app_label}.{m.__name__}',
            'verbose_name': str(m._meta.verbose_name),
            'table': m._meta.db_table,
            'fields': fields,
        },
        display=f'{len(fields)} field(s)',
    )
