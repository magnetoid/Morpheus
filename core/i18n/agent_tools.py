"""Translation agent tools.

Two layers: convenience product-by-slug tools (translate_product / list), and
**generic** tools (`i18n.languages` / `i18n.get_translations` /
`i18n.set_translation`) that address ANY translatable object by
``content_type`` (``app_label.model``, e.g. ``catalog.product``) + ``object_id``.
The generic tools are the surface external translators + translation tools use
over MCP; the GraphQL layer (localization plugin) mirrors them.
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
    description='List the languages enabled for this store (target languages for translation).',
    scopes=['i18n.read'],
    schema={'type': 'object', 'properties': {}},
)
def list_languages_tool() -> ToolResult:
    from core.i18n.services import list_enabled_languages

    langs = list_enabled_languages()
    return ToolResult(
        output={'languages': langs}, display=f'{len(langs)} language(s): {", ".join(langs)}'
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
    description='Set the translation of one field of any object in one language.',
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


@tool(
    name='i18n.translate_product',
    description="Set translations for a product's fields in a language.",
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'slug': {'type': 'string'},
            'language_code': {'type': 'string', 'description': 'BCP-47 short code, e.g. "es"'},
            'name': {'type': 'string'},
            'short_description': {'type': 'string'},
            'description': {'type': 'string'},
        },
        'required': ['slug', 'language_code'],
    },
    requires_approval=True,
)
def translate_product_tool(
    *,
    slug: str,
    language_code: str,
    name: str = '',
    short_description: str = '',
    description: str = '',
) -> ToolResult:
    from core.i18n import bulk_set_translations
    from plugins.installed.catalog.models import Product

    try:
        product = Product.objects.get(slug=slug)
    except Product.DoesNotExist as e:
        raise ToolError(f'Unknown product: {slug}') from e
    n = bulk_set_translations(
        product,
        language_code,
        {'name': name, 'short_description': short_description, 'description': description},
    )
    return ToolResult(
        output={'product': slug, 'language': language_code, 'fields': n},
        display=f'Set {n} field(s) for {slug} in {language_code}',
    )


@tool(
    name='i18n.list_translations',
    description='Show all translations stored for a product (by slug).',
    scopes=['catalog.read'],
    schema={
        'type': 'object',
        'properties': {'slug': {'type': 'string'}},
        'required': ['slug'],
    },
)
def list_translations_tool(*, slug: str) -> ToolResult:
    from core.i18n import translations_for
    from plugins.installed.catalog.models import Product

    try:
        product = Product.objects.get(slug=slug)
    except Product.DoesNotExist as e:
        raise ToolError(f'Unknown product: {slug}') from e
    return ToolResult(output={'product': slug, 'translations': translations_for(product)})
