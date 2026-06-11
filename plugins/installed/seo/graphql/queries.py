"""SEO GraphQL queries."""

from __future__ import annotations

import strawberry

from api.graphql_permissions import has_scope, require_authenticated


@strawberry.type
class SeoMetaType:
    id: strawberry.ID
    target_app: str
    target_model: str
    target_id: str
    title: str
    description: str
    og_image: str
    canonical_url: str
    robots: str
    auto_filled: bool


@strawberry.type
class RedirectType:
    id: strawberry.ID
    from_path: str
    to_path: str
    status_code: int
    is_active: bool
    hit_count: int


@strawberry.type
class SeoQueryExtension:
    @strawberry.field(description='List recent SEO meta overrides (admin scope).')
    def seo_meta_entries(
        self,
        info: strawberry.Info,
        first: int = 50,
    ) -> list[SeoMetaType]:
        from plugins.installed.seo.models import SeoMeta

        require_authenticated(info)
        if not has_scope(info, 'admin:seo'):
            return []
        first = max(1, min(int(first), 200))
        rows = SeoMeta.objects.select_related('content_type').order_by('-updated_at')[:first]
        return [
            SeoMetaType(
                id=str(r.id),
                target_app=r.content_type.app_label,
                target_model=r.content_type.model,
                target_id=r.object_id,
                title=r.title,
                description=r.description,
                og_image=r.og_image,
                canonical_url=r.canonical_url,
                robots=r.robots,
                auto_filled=r.auto_filled,
            )
            for r in rows
        ]

    @strawberry.field(description='Active redirect rules (admin scope).')
    def seo_redirects(
        self,
        info: strawberry.Info,
        first: int = 100,
    ) -> list[RedirectType]:
        from plugins.installed.seo.models import Redirect

        require_authenticated(info)
        if not has_scope(info, 'admin:seo'):
            return []
        first = max(1, min(int(first), 500))
        rows = Redirect.objects.filter(is_active=True).order_by('-updated_at')[:first]
        return [
            RedirectType(
                id=str(r.id),
                from_path=r.from_path,
                to_path=r.to_path,
                status_code=r.status_code,
                is_active=r.is_active,
                hit_count=r.hit_count,
            )
            for r in rows
        ]
