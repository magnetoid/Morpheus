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


# ── Set / delete (migrated from core/assistant/tools/ecommerce_writes.py,
#    arch-debt refactor) ─────────────────────────────────────────────────────
# Names unchanged — Linda sources them by name (get_default_tools._migrated_names).
# Staged-mode / confirm / hard-gate helpers stay core (plugin -> core).


@tool(
    name='metafields.set',
    description=(
        'Set or update a metafield on a record. Pass `model` as '
        '`app_label.ModelName`, `object_id` (string pk), `namespace` '
        '(optional, defaults to ""), `key`, `value`, and an optional '
        '`value_type` hint (string/integer/number/boolean/json/date/'
        'url/email/file_id). Idempotent — re-setting the same '
        '`(model, object_id, namespace, key)` overwrites.'
    ),
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {
            'model': {'type': 'string'},
            'object_id': {'type': 'string'},
            'namespace': {'type': 'string', 'default': ''},
            'key': {'type': 'string'},
            'value': {'type': 'string'},
            'value_type': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
        },
        'required': ['model', 'object_id', 'key', 'value'],
    },
    requires_approval=True,
)
def metafields_set_tool(
    *,
    model: str,
    object_id: str,
    key: str,
    value: str,
    namespace: str = '',
    value_type: str = 'string',
    confirmed: bool = False,
    context: dict | None = None,
) -> ToolResult:
    from core.assistant.tools.ecommerce_writes import (
        _is_staged,
        _obj_ref,
        _require_confirmed,
        _stage,
    )

    staged = _is_staged(context)
    if not staged:
        _require_confirmed(confirmed)
    from django.apps import apps

    try:
        from plugins.installed.metafields.models import Metafield
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'metafields plugin unavailable: {e}') from e
    try:
        app_label, model_name = model.split('.', 1)
        m = apps.get_model(app_label, model_name)
    except (ValueError, LookupError) as e:
        raise ToolError(f'unknown model: {model}') from e
    instance = m.objects.filter(pk=object_id).first()
    if instance is None:
        raise ToolError(f'{model} not found: {object_id}')
    if staged:
        from django.contrib.contenttypes.models import ContentType

        existing = Metafield.objects.filter(
            content_type=ContentType.objects.get_for_model(instance),
            object_id=str(instance.pk),
            namespace=namespace or '',
            key=key,
        ).first()
        if existing is None:
            raise ToolError(
                'cannot stage a NEW metafield — the OpsProposal change format only '
                'expresses updates to existing rows; create it via the interactive '
                'confirmed flow instead.'
            )
        full_key = f'{namespace}.{key}' if namespace else key
        return _stage(
            context=context,
            tool_name='metafields.set',
            kind='metafield.update',
            title=f'Set metafield {full_key} on {model}#{object_id}',
            summary=f'Update metafield {full_key} on {model}#{object_id}.',
            changes=[
                {
                    'object': _obj_ref(existing),
                    'field': 'value',
                    'old': existing.value,
                    'new': str(value),
                }
            ],
            target=instance,
        )
    obj = Metafield.objects.set(
        instance,
        namespace=namespace,
        key=key,
        value=value,
        value_type=value_type,
    )
    return ToolResult(
        output={
            'id': str(obj.id),
            'full_key': obj.full_key,
            'value': obj.value,
            'value_type': obj.value_type,
        },
        display=f'set {obj.full_key} on {model}#{object_id}',
    )


@tool(
    name='metafields.delete',
    description=(
        'Delete a metafield. Pass `model`, `object_id`, `namespace` '
        '(default ""), and `key`. HARD-GATED — pass `confirmed=True`, '
        '`hard_gate_ack="YES"`, AND `echo` (user types the metafield key '
        'back to confirm).'
    ),
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {
            'model': {'type': 'string'},
            'object_id': {'type': 'string'},
            'namespace': {'type': 'string', 'default': ''},
            'key': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
            'hard_gate_ack': {'type': 'string', 'description': 'Must equal "YES".'},
            'echo': {'type': 'string', 'description': 'User-typed key for confirmation.'},
        },
        'required': ['model', 'object_id', 'key'],
    },
    requires_approval=True,
)
def metafields_delete_tool(
    *,
    model: str,
    object_id: str,
    key: str,
    namespace: str = '',
    confirmed: bool = False,
    hard_gate_ack: str = '',
    echo: str = '',
    context: dict | None = None,
) -> ToolResult:
    from core.assistant.tools.ecommerce_writes import (
        _is_staged,
        _require_confirmed,
        _require_hard_gate,
    )

    if _is_staged(context):
        raise ToolError(
            'deletion cannot be staged — destructive actions are not expressible '
            'as an OpsProposal change; use the interactive hard-gated flow.'
        )
    _require_confirmed(confirmed)
    _require_hard_gate(hard_gate_ack=hard_gate_ack, target_name=key, echo=echo)
    from django.apps import apps

    try:
        from plugins.installed.metafields.models import Metafield
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'metafields plugin unavailable: {e}') from e
    try:
        app_label, model_name = model.split('.', 1)
        m = apps.get_model(app_label, model_name)
    except (ValueError, LookupError) as e:
        raise ToolError(f'unknown model: {model}') from e
    instance = m.objects.filter(pk=object_id).first()
    if instance is None:
        raise ToolError(f'{model} not found: {object_id}')
    n = Metafield.objects.delete_for(instance, namespace=namespace, key=key)
    return ToolResult(
        output={'deleted': n}, display=f'deleted {n} metafield(s) on {model}#{object_id}'
    )
