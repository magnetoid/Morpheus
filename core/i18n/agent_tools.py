"""Translation agent tools.

Two layers: convenience product-by-slug tools (translate_product / list), and
**generic** tools (`i18n.languages` / `i18n.get_translations` /
`i18n.set_translation`) that address ANY translatable object by
``content_type`` (``app_label.model``, e.g. ``catalog.product``) + ``object_id``.
The generic tools are the surface external translators + translation tools use
over MCP; the GraphQL layer (localization plugin) mirrors them. An external
translator lists what is missing (`i18n.translation_status`), reads an object's
text in the form to write it back (`i18n.source_text`), and writes all of it in
one call (`i18n.set_translations`). Every tool takes either a kind key
(`booking_marketplace.experience`) or a content type (`app_label.model`). Every text written
through them is reviewed: the merchant approved that exact text. AI drafts are
queued by the localization app's `i18n.draft_translations` and wait for review
(`i18n.translation_status`, `i18n.approve_translation`).
"""

from __future__ import annotations

from core.agents import ToolError, ToolResult, tool


def _resolve(content_type: str, object_id: str):
    """A kind key or ``app_label.model`` + pk → model instance, or raise ToolError."""
    from django.contrib.contenttypes.models import ContentType

    from core.i18n.services import spec_by_key

    spec = spec_by_key(content_type or '')
    if spec is not None:
        obj = spec['model']._base_manager.filter(pk=object_id).first()
        if obj is None:
            raise ToolError(f'No {content_type} with id {object_id}')
        return obj
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


def _content_type(obj) -> str:
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(obj)
    return f'{ct.app_label}.{ct.model}'


def _url(spec: dict, obj) -> str:
    try:
        return str(spec['url'](obj) or '')
    except Exception:  # noqa: BLE001 — an address is a courtesy
        return ''


_TARGET = {
    'type': 'string',
    'description': (
        "A kind key from i18n.translation_status (e.g. 'booking_marketplace.experience') "
        "or 'app_label.model' (e.g. 'catalog.product')."
    ),
}


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
            'content_type': _TARGET,
            'object_id': {'type': 'string'},
            'field': {
                'type': 'string',
                'description': 'Model field name, e.g. "name" or "description".',
            },
            'language_code': {'type': 'string', 'description': 'BCP-47 short code, e.g. "fr".'},
            'value': {'type': 'string'},
            'machine_translated': {
                'type': 'boolean',
                'description': (
                    'Mark as machine output (default false). Text a store agent writes'
                    ' is always marked.'
                ),
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
    agent=None,
    context=None,
) -> ToolResult:
    from core.agents.provenance import ai_author
    from core.i18n import set_translation
    from core.i18n.services import translation_problem

    obj = _resolve(content_type, object_id)
    problem = translation_problem(obj, field, language_code)
    if problem:
        raise ToolError(problem)
    # A translation a store agent writes is AI-written, whatever the model says (Art. 50).
    machine = bool(machine_translated) or bool(ai_author(agent, context))
    set_translation(obj, field, language_code, value, machine_translated=machine)
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
    from core.i18n.services import spec_for

    title_field = (spec_for(obj) or {}).get('title_field')
    if title_field:
        return str(getattr(obj, title_field, '') or obj)
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
        '`language_code` and `status`: missing | draft | translated) to list those objects; '
        'then read each with i18n.source_text and write it with i18n.set_translations.'
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
                {
                    'id': pk,
                    'kind': spec['key'],
                    'content_type': _content_type(objs[pk]),
                    'name': _label(objs[pk]),
                    'url': _url(spec, objs[pk]),
                    'language': lang,
                    'status': wanted,
                }
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


@tool(
    name='i18n.source_text',
    description=(
        "An object's own text, field by field, in the form a translation is written "
        "(lists as lines, an itinerary or guest questions as blocks), with each field's "
        'format, the translation stored for `language_code` and whether it is '
        'published. Use it before i18n.set_translations.'
    ),
    scopes=['i18n.read'],
    schema={
        'type': 'object',
        'properties': {
            'content_type': _TARGET,
            'object_id': {'type': 'string'},
            'language_code': {'type': 'string', 'description': 'The language to translate into.'},
        },
        'required': ['content_type', 'object_id', 'language_code'],
    },
)
def source_text_tool(*, content_type: str, object_id: str, language_code: str) -> ToolResult:
    from core.i18n.models import Translation
    from core.i18n.services import (
        _ct,
        content_languages,
        field_format,
        source_language,
        source_values,
        spec_for,
        translatable_into,
    )

    obj = _resolve(content_type, object_id)
    spec = spec_for(obj)
    if spec is None:
        raise ToolError(f'{content_type} is not content this store translates')
    language = (language_code or '').strip().lower()
    if language not in translatable_into(obj):
        raise ToolError(
            f'{language or "(none)"} is not a language this can be translated into; it is '
            f'written in {source_language(obj)} and can go into: '
            f'{", ".join(translatable_into(obj)) or "nothing"}'
        )
    stored = {
        row.field: row
        for row in Translation.objects.filter(
            content_type=_ct(obj), object_id=str(obj.pk), language_code=language
        )
    }
    fields = {}
    for field, text in source_values(obj, spec).items():
        if not (text or '').strip():
            continue
        fmt, how = field_format(spec['fields'][field])
        row = stored.get(field)
        fields[field] = {
            'format': fmt,
            'how_to_write': how,
            'source': text,
            'translation': row.value if row is not None else '',
            'published': bool(row is not None and row.reviewed and (row.value or '').strip()),
        }
    missing = [f for f, v in fields.items() if not v['published']]
    shown = language in (content_languages(obj) or set())
    return ToolResult(
        output={
            'kind': spec['key'],
            'content_type': _content_type(obj),
            'object_id': str(obj.pk),
            'name': _label(obj),
            'url': _url(spec, obj),
            'source_language': source_language(obj),
            'language': language,
            'fields': fields,
            'missing': missing,
            'shown_in_language': shown,
        },
        display=f'{_label(obj)}: {len(fields)} field(s) to translate, {len(missing)} missing',
    )


@tool(
    name='i18n.set_translations',
    description=(
        "Set several fields of one object's translation in one language at once, "
        'written as i18n.source_text describes each field. The text is published as '
        'written (reviewed): pass the text the merchant approved. Set machine_translated '
        'when the text is machine output. Says which fields are still missing and '
        "whether the object's page now appears in that language."
    ),
    scopes=['i18n.write'],
    schema={
        'type': 'object',
        'properties': {
            'content_type': _TARGET,
            'object_id': {'type': 'string'},
            'language_code': {'type': 'string'},
            'values': {
                'type': 'object',
                'description': 'Field name → translated text. An empty text removes it.',
                'additionalProperties': {'type': 'string'},
            },
            'machine_translated': {
                'type': 'boolean',
                'description': 'Mark as machine output (default false).',
            },
        },
        'required': ['content_type', 'object_id', 'language_code', 'values'],
    },
    requires_approval=True,
)
def set_translations_tool(
    *,
    content_type: str,
    object_id: str,
    language_code: str,
    values: dict,
    machine_translated: bool = False,
    agent=None,
    context=None,
) -> ToolResult:
    from django.db import transaction

    from core.agents.provenance import ai_author
    from core.i18n.services import (
        content_languages,
        delete_translation,
        reviewed_values,
        set_translation,
        source_values,
        spec_for,
        translation_problem,
    )

    obj = _resolve(content_type, object_id)
    spec = spec_for(obj)
    if spec is None:
        raise ToolError(f'{content_type} is not content this store translates')
    if not isinstance(values, dict) or not values:
        raise ToolError('values must name at least one field')
    language = (language_code or '').strip().lower()
    problems = [p for p in (translation_problem(obj, f, language) for f in values) if p]
    if problems:
        raise ToolError('; '.join(dict.fromkeys(problems)))
    machine = bool(machine_translated) or bool(ai_author(agent, context))
    with transaction.atomic():
        for field, text in values.items():
            if str(text or '').strip():
                set_translation(obj, field, language, str(text), machine_translated=machine)
            else:
                delete_translation(obj, field, language)
    have = reviewed_values(obj, language).get(str(obj.pk), {})
    needed = [f for f, t in source_values(obj, spec).items() if (t or '').strip()]
    missing = [f for f in needed if not (have.get(f) or '').strip()]
    shown = language in (content_languages(obj) or set())
    return ToolResult(
        output={
            'kind': spec['key'],
            'object_id': str(obj.pk),
            'language': language,
            'saved': sorted(values),
            'missing': missing,
            'shown_in_language': shown,
        },
        display=(
            f'Saved {len(values)} field(s) of {_label(obj)} in {language}; '
            + (f'still missing: {", ".join(missing)}' if missing else 'complete')
        ),
    )
