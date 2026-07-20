"""Database introspection tools."""

from __future__ import annotations

from core.assistant.tools.filesystem import ToolError, ToolResult, tool


@tool(
    name='db.list_models',
    description='List every Django model with row count.',
    scopes=['system.read'],
    schema={'type': 'object', 'properties': {}},
)
def list_models_tool() -> ToolResult:
    from django.apps import apps

    rows = []
    for model in apps.get_models():
        try:
            count = model.objects.count()
        except Exception:  # noqa: BLE001
            count = -1
        rows.append(
            {
                'app': model._meta.app_label,
                'model': model.__name__,
                'rows': count,
            }
        )
    rows.sort(key=lambda r: (r['app'], r['model']))
    return ToolResult(output={'models': rows}, display=f'{len(rows)} models')


@tool(
    name='db.count_rows',
    description='Count rows in a specific model: `app_label.ModelName`.',
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {'model': {'type': 'string'}},
        'required': ['model'],
    },
)
def count_rows_tool(*, model: str) -> ToolResult:
    from django.apps import apps

    try:
        app_label, model_name = model.split('.', 1)
        m = apps.get_model(app_label, model_name)
    except (ValueError, LookupError) as e:
        raise ToolError(f'unknown model: {model}') from e
    try:
        count = m.objects.count()
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'count failed: {e}') from e
    return ToolResult(output={'model': model, 'count': count})
