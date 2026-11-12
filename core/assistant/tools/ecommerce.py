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
  * settings.list
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


_SECRET_NAMES = ('api_key', 'secret', 'password', 'token', 'webhook_secret')


def _password_fields(plugin_name: str) -> set[str]:
    """The settings an app's schema marks ``format: password``: the dashboard
    never shows them again, so neither does an agent tool."""
    from plugins.registry import app_registry  # noqa: PLC0415

    schemas = []
    plugin = app_registry.get(plugin_name)
    if plugin is not None:
        schemas.append(plugin.get_config_schema() or {})
    panel = app_registry.settings_panel(plugin_name)
    if panel is not None:
        schemas.append(panel.schema or {})
    return {
        key
        for schema in schemas
        for key, prop in (schema.get('properties') or {}).items()
        if isinstance(prop, dict) and prop.get('format') == 'password'
    }


def _secret_name(key: Any) -> bool:
    return any(s in str(key).lower() for s in _SECRET_NAMES)


def _redacted(value: Any, secret: bool = False) -> Any:
    """``value`` with every secret inside it redacted, nested ones too (an API
    token is a ``token`` inside a list of dicts)."""
    if isinstance(value, dict):
        return {k: _redacted(v, secret or _secret_name(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redacted(v, secret) for v in value]
    if not secret:
        return value
    if isinstance(value, str) and len(value) > 4:
        return value[:2] + '…(redacted)…' + value[-2:]
    return '(redacted)'


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
    for cfg in PluginConfig.objects.all():
        hidden = _password_fields(cfg.plugin_name)
        out[cfg.plugin_name] = {
            'is_enabled': cfg.is_enabled,
            'config': {
                k: _redacted(v, k in hidden or _secret_name(k))
                for k, v in (cfg.config or {}).items()
            },
        }
    return ToolResult(
        output={'plugins': out, 'count': len(out)}, display=f'{len(out)} plugin config(s)'
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
