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


def _money_str(value: Any) -> str:
    """Convert a djmoney Money / Decimal / None into a flat string."""
    if value is None:
        return ''
    amount = getattr(value, 'amount', value)
    return str(amount)


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
    SECRET_KEYS = ('api_key', 'secret', 'password', 'token', 'webhook_secret')
    for cfg in PluginConfig.objects.all():
        data = dict(cfg.config_data or {})
        # Redact anything that looks like a secret.
        for k in list(data.keys()):
            lk = k.lower()
            if any(s in lk for s in SECRET_KEYS):
                v = data[k]
                if isinstance(v, str) and len(v) > 4:
                    data[k] = v[:2] + '…(redacted)…' + v[-2:]
                else:
                    data[k] = '(redacted)'
        out[cfg.plugin_name] = {
            'is_enabled': cfg.is_enabled,
            'config': data,
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
