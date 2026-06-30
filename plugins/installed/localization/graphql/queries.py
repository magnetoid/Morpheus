"""GraphQL read surface for translations — for external translators + tools.

Mirrors the generic i18n MCP tools (core/i18n/agent_tools.py): the same bearer
token (minted at /dashboard/apps/agent_mcp/tokens/) works from MCP or GraphQL.
Objects are addressed by ``content_type`` (``app_label.model``) + ``object_id``.
"""

from __future__ import annotations

import strawberry

from api.graphql_permissions import has_scope, require_authenticated


@strawberry.type
class TranslationEntry:
    field: str
    language_code: str
    value: str
    is_machine_translated: bool


def _resolve_ct(content_type: str):
    from django.contrib.contenttypes.models import ContentType

    app_label, _, model = (content_type or '').partition('.')
    if not app_label or not model:
        return None
    return ContentType.objects.filter(app_label=app_label, model=model.lower()).first()


@strawberry.type
class LocalizationQueryExtension:
    @strawberry.field(description='Languages enabled for this store (translation targets).')
    def enabled_languages(self, info: strawberry.Info) -> list[str]:
        require_authenticated(info)
        if not has_scope(info, 'i18n.read'):
            return []
        from core.i18n.services import list_enabled_languages

        return list_enabled_languages()

    @strawberry.field(
        description="Stored translations for an object. content_type is 'app_label.model' "
        "(e.g. 'catalog.product'); filter by language_code optionally."
    )
    def translations(
        self,
        info: strawberry.Info,
        content_type: str,
        object_id: str,
        language_code: str = '',
    ) -> list[TranslationEntry]:
        require_authenticated(info)
        if not has_scope(info, 'i18n.read'):
            return []
        from core.i18n.models import Translation

        ct = _resolve_ct(content_type)
        if ct is None:
            return []
        qs = Translation.objects.filter(content_type=ct, object_id=str(object_id))
        if language_code:
            qs = qs.filter(language_code=language_code)
        return [
            TranslationEntry(
                field=t.field,
                language_code=t.language_code,
                value=t.value,
                is_machine_translated=t.is_machine_translated,
            )
            for t in qs.order_by('field', 'language_code')
        ]
