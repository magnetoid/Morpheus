"""Metafields agent tools.

metafields.list_for was migrated here from core/assistant/tools/ecommerce.py so
the Metafield query lives in the plugin that owns it. Tool name + scope
unchanged — Linda sources it by name from the agent registry.
"""

from __future__ import annotations

from core.agents import ToolError, ToolResult, tool


@tool(
    name='metafields.list_for',
    description=(
        'List every metafield on a record. Pass `model` as '
        '`app_label.ModelName` and `object_id` (string pk). Returns a '
        'flat dict keyed by `namespace.key`.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'model': {'type': 'string'},
            'object_id': {'type': 'string'},
        },
        'required': ['model', 'object_id'],
    },
)
def metafields_list_for_tool(*, model: str, object_id: str) -> ToolResult:
    from django.apps import apps
    from django.contrib.contenttypes.models import ContentType

    from plugins.installed.metafields.models import Metafield

    try:
        app_label, model_name = model.split('.', 1)
        m = apps.get_model(app_label, model_name)
    except (ValueError, LookupError) as e:
        raise ToolError(f'unknown model: {model}') from e
    ct = ContentType.objects.get_for_model(m)
    rows = list(Metafield.objects.filter(content_type=ct, object_id=str(object_id)))
    return ToolResult(
        output={
            'model': f'{app_label}.{model_name}',
            'object_id': str(object_id),
            'metafields': [
                {
                    'namespace': mf.namespace,
                    'key': mf.key,
                    'full_key': mf.full_key,
                    'value': mf.value,
                    'value_type': mf.value_type,
                    'description': mf.description,
                }
                for mf in rows
            ],
        },
        display=f'{len(rows)} metafield(s)',
    )
