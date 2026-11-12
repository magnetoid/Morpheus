"""Translation agent tools.

Two layers: convenience product-by-slug tools (translate_product / list), and
**generic** tools (`i18n.languages` / `i18n.get_translations` /
`i18n.set_translation`) that address ANY translatable object by
``content_type`` (``app_label.model``, e.g. ``catalog.product``) + ``object_id``.
The generic tools are the surface external translators + translation tools use
over MCP; the GraphQL layer (localization plugin) mirrors them. Every text written
through them is reviewed: the merchant approved that exact text. AI drafts are
queued by the localization app's `i18n.draft_translations` and wait for review
(`i18n.translation_status`, `i18n.approve_translation`).
"""

from __future__ import annotations

from core.agents import ToolError, ToolResult, tool


def _resolve(content_type: str, object_id: str):
    """Resolve ``app_label.model`` + pk → model instance, or raise ToolError."""
    from django.contrib.contenttypes.models import ContentType

    app_label, _, model = (content_type or '').partition('.')
    if not app_label or not model:
        raise ToolError("content_type must be 'app_label.model', e.g. 'catalog.product'")
    try:
        ct = ContentType.objects.get(app_label=app_label, model=model.lower())
    except ContentType.DoesNotExist as e:
        raise ToolError(f'Unknown content_type: {content_type}') from e
    obj = ct.model_class().objects.filter(pk=object_id).first()
    if obj is None:
        raise ToolError(f'No {content_type} with id {object_id}')
    return obj


@tool(
    name='i18n.languages',
    description=(
        'The languages this store is served in: the default first, then the ones '
        'content can be translated into. They are chosen when the store is deployed.'
    ),
    scopes=['i18n.read'],
    schema={'type': 'object', 'properties': {}},
)
def list_languages_tool() -> ToolResult:
    from core.i18n.services import default_language, store_languages, target_languages

    langs = store_languages()
    return ToolResult(
        output={
            'languages': langs,
            'default': default_language(),
            'translatable_into': target_languages(),
        },
        display=f'{len(langs)} language(s): {", ".join(langs)}',
    )


@tool(
    name='i18n.get_translations',
    description='Read all stored translations for any object, addressed by content_type + object_id.',
    scopes=['i18n.read'],
    schema={
        'type': 'object',
        'properties': {
            'content_type': {
                'type': 'string',
                'description': "'app_label.model', e.g. 'catalog.product'",
            },
            'object_id': {'type': 'string'},
            'language_code': {
                'type': 'string',
                'description': 'Optional — filter to one language.',
            },
        },
        'required': ['content_type', 'object_id'],
    },
)
def get_translations_tool(
    *, content_type: str, object_id: str, language_code: str = ''
) -> ToolResult:
    from core.i18n import translations_for

    obj = _resolve(content_type, object_id)
    data = (
        translations_for(obj, language_code=language_code)
        if language_code
        else translations_for(obj)
    )
    return ToolResult(
        output={'content_type': content_type, 'object_id': str(object_id), 'translations': data}
    )


@tool(
    name='i18n.set_translation',
    description=(
        'Set the translation of one field of any object in one language. The text is '
        'published as written (reviewed): pass the exact text the merchant approved.'
    ),
    scopes=['i18n.write'],
    schema={
        'type': 'object',
        'properties': {
            'content_type': {
                'type': 'string',
                'description': "'app_label.model', e.g. 'catalog.product'",
            },
            'object_id': {'type': 'string'},
            'field': {
                'type': 'string',
                'description': 'Model field name, e.g. "name" or "description".',
            },
            'language_code': {'type': 'string', 'description': 'BCP-47 short code, e.g. "fr".'},
            'value': {'type': 'string'},
            'machine_translated': {
                'type': 'boolean',
                'description': 'Mark as machine output (default false).',
            },
        },
        'required': ['content_type', 'object_id', 'field', 'language_code', 'value'],
    },
    requires_approval=True,
)
def set_translation_tool(
    *,
    content_type: str,
    object_id: str,
    field: str,
    language_code: str,
    value: str,
    machine_translated: bool = False,
) -> ToolResult:
    from core.i18n import set_translation

    obj = _resolve(content_type, object_id)
    set_translation(obj, field, language_code, value, machine_translated=machine_translated)
    return ToolResult(
        output={
            'content_type': content_type,
            'object_id': str(object_id),
            'field': field,
            'language': language_code,
        },
        display=f'Set {field} for {content_type}#{object_id} in {language_code}',
    )


def _label(obj) -> str:
    return str(getattr(obj, 'name', '') or getattr(obj, 'title', '') or obj)


def _language_arg(language_code: str) -> str:
    from core.i18n.services import target_languages

    code = (language_code or '').strip().lower()
    targets = target_languages()
    if code not in targets:
        raise ToolError(
            f'{code or "(none)"} is not a language this store translates into; '
            f'it has: {", ".join(targets) or "none (one language only)"}'
        )
    return code


@tool(
    name='i18n.translation_status',
    description=(
        'How much of the store is translated: per language and kind of content '
        '(products, places, pages …) the total, the translated (reviewed and complete), '
        'the AI drafts waiting for review and the missing. Pass `kind` (and optionally '
        '`language_code` and `status`: missing | draft | translated) to list those objects.'
    ),
    scopes=['i18n.read'],
    schema={
        'type': 'object',
        'properties': {
            'kind': {'type': 'string', 'description': "A kind key, e.g. 'catalog.product'."},
            'language_code': {'type': 'string'},
            'status': {'type': 'string', 'enum': ['missing', 'draft', 'translated']},
            'limit': {'type': 'integer', 'description': 'Objects to list (default 25, max 100).'},
        },
    },
)
def translation_status_tool(
    *, kind: str = '', language_code: str = '', status: str = '', limit: int = 25
) -> ToolResult:
    from core.i18n.services import (
        object_statuses,
        spec_by_key,
        status_summary,
        target_languages,
        translatable_specs,
    )

    languages = [_language_arg(language_code)] if language_code else target_languages()
    specs = translatable_specs()
    if kind:
        spec = spec_by_key(kind)
        if spec is None:
            raise ToolError(f'Unknown kind {kind}; kinds: {", ".join(s["key"] for s in specs)}')
        specs = [spec]
    summary = [status_summary(spec, lang) for lang in languages for spec in specs]
    output: dict = {'summary': summary, 'kinds': [s['key'] for s in translatable_specs()]}
    if kind:
        limit = max(1, min(int(limit or 25), 100))
        spec = specs[0]
        wanted = status or 'missing'
        listed = []
        for lang in languages:
            statuses = object_statuses(spec, lang)
            pks = [pk for pk, st in statuses.items() if st == wanted][:limit]
            objs = {str(o.pk): o for o in spec['model']._base_manager.filter(pk__in=pks)}
            listed.extend(
                {'id': pk, 'name': _label(objs[pk]), 'language': lang, 'status': wanted}
                for pk in pks
                if pk in objs
            )
        output['objects'] = listed
    if not languages:
        display = 'This store is offered in one language: there is nothing to translate.'
    else:
        display = '; '.join(
            f'{row["label"]} in {row["language"]}: {row["translated"]}/{row["total"]} '
            f'translated, {row["draft"]} draft(s), {row["missing"]} missing'
            for row in summary
        )
    return ToolResult(output=output, display=display)


@tool(
    name='i18n.approve_translation',
    description=(
        "Publish one object's AI-drafted translations in a language: they become "
        'reviewed and shoppers see them. Only after the merchant read and accepted them.'
    ),
    scopes=['i18n.write'],
    schema={
        'type': 'object',
        'properties': {
            'kind': {'type': 'string', 'description': "A kind key, e.g. 'catalog.product'."},
            'object_id': {'type': 'string'},
            'language_code': {'type': 'string'},
        },
        'required': ['kind', 'object_id', 'language_code'],
    },
    requires_approval=True,
)
def approve_translation_tool(*, kind: str, object_id: str, language_code: str) -> ToolResult:
    from core.i18n.services import approve_drafts, spec_by_key

    spec = spec_by_key(kind)
    if spec is None:
        raise ToolError(f'Unknown kind {kind}')
    language = _language_arg(language_code)
    obj = spec['model']._base_manager.filter(pk=object_id).first()
    if obj is None:
        raise ToolError(f'No {kind} with id {object_id}')
    n = approve_drafts(obj, language)
    return ToolResult(
        output={'kind': kind, 'object_id': str(object_id), 'language': language, 'approved': n},
        display=f'Approved {n} drafted field(s) of {_label(obj)} in {language}',
    )
