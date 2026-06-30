"""GraphQL write surface for translations — for external translators + tools.

`set_translation` mirrors the i18n.set_translation MCP tool. Requires the
`i18n.write` scope on the caller's bearer token / API key.
"""

from __future__ import annotations

import strawberry

from api.graphql_permissions import has_scope, require_authenticated


@strawberry.type
class SetTranslationResult:
    ok: bool
    content_type: str
    object_id: str
    field: str
    language_code: str
    error: str


@strawberry.type
class LocalizationMutationExtension:
    @strawberry.mutation(
        description="Set a field's translation for any object. content_type is "
        "'app_label.model' (e.g. 'catalog.product')."
    )
    def set_translation(
        self,
        info: strawberry.Info,
        content_type: str,
        object_id: str,
        field: str,
        language_code: str,
        value: str,
        machine_translated: bool = False,
    ) -> SetTranslationResult:
        require_authenticated(info)

        def _err(msg: str) -> SetTranslationResult:
            return SetTranslationResult(
                ok=False,
                content_type=content_type,
                object_id=str(object_id),
                field=field,
                language_code=language_code,
                error=msg,
            )

        if not has_scope(info, 'i18n.write'):
            return _err('Missing scope: i18n.write')

        from django.contrib.contenttypes.models import ContentType

        from core.i18n import set_translation

        app_label, _, model = (content_type or '').partition('.')
        ct = ContentType.objects.filter(app_label=app_label, model=model.lower()).first()
        if ct is None:
            return _err(f'Unknown content_type: {content_type}')
        obj = ct.model_class().objects.filter(pk=object_id).first()
        if obj is None:
            return _err(f'No {content_type} with id {object_id}')

        set_translation(obj, field, language_code, value, machine_translated=machine_translated)
        return SetTranslationResult(
            ok=True,
            content_type=content_type,
            object_id=str(object_id),
            field=field,
            language_code=language_code,
            error='',
        )
