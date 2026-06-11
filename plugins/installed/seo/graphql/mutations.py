"""SEO GraphQL mutations."""

from __future__ import annotations

import strawberry

from api.graphql_permissions import (
    PermissionDenied,
    has_scope,
    require_authenticated,
)


@strawberry.input
class UpsertSeoMetaInput:
    target_app: str
    target_model: str
    target_id: str
    title: str = ''
    description: str = ''
    og_image: str = ''
    canonical_url: str = ''
    robots: str = 'index, follow'


@strawberry.input
class CreateRedirectInput:
    from_path: str
    to_path: str
    status_code: int = 301
    note: str = ''


@strawberry.type
class SeoMutationResult:
    success: bool
    message: str = ''
    id: strawberry.ID = strawberry.ID('')


@strawberry.type
class SeoMutationExtension:
    @strawberry.mutation(description='Create or update SEO meta for an object (admin:seo).')
    def upsert_seo_meta(
        self,
        info: strawberry.Info,
        input: UpsertSeoMetaInput,
    ) -> SeoMutationResult:
        from django.contrib.contenttypes.models import ContentType

        from plugins.installed.seo.models import SeoMeta

        require_authenticated(info)
        if not has_scope(info, 'admin:seo'):
            raise PermissionDenied('admin:seo scope required')

        try:
            ct = ContentType.objects.get(
                app_label=input.target_app, model=input.target_model.lower()
            )
        except ContentType.DoesNotExist:
            return SeoMutationResult(success=False, message='Unknown target_app/target_model.')

        meta, _ = SeoMeta.objects.update_or_create(
            content_type=ct,
            object_id=str(input.target_id),
            defaults={
                'title': input.title[:200],
                'description': input.description[:320],
                'og_image': input.og_image[:600],
                'canonical_url': input.canonical_url[:600],
                'robots': input.robots[:40],
                'auto_filled': False,
            },
        )
        return SeoMutationResult(success=True, id=str(meta.id))

    @strawberry.mutation(description='Create a redirect rule (admin:seo).')
    def create_seo_redirect(
        self,
        info: strawberry.Info,
        input: CreateRedirectInput,
    ) -> SeoMutationResult:
        from plugins.installed.seo.models import Redirect

        require_authenticated(info)
        if not has_scope(info, 'admin:seo'):
            raise PermissionDenied('admin:seo scope required')

        if not input.from_path.startswith('/') or not input.to_path.startswith('/'):
            return SeoMutationResult(
                success=False,
                message='from_path and to_path must start with /',
            )
        status = input.status_code if input.status_code in (301, 302) else 301
        row, _ = Redirect.objects.update_or_create(
            from_path=input.from_path[:500],
            defaults={
                'to_path': input.to_path[:500],
                'status_code': status,
                'note': input.note[:200],
                'is_active': True,
            },
        )
        return SeoMutationResult(success=True, id=str(row.id))
