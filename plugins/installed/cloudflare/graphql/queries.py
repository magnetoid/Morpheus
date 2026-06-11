"""Cloudflare plugin — GraphQL queries."""

from __future__ import annotations

import strawberry

from api.graphql_permissions import has_scope, require_authenticated


@strawberry.type
class CloudflareZoneType:
    id: strawberry.ID
    zone_id: str
    domain: str
    is_active: bool
    auto_purge_on_product_update: bool
    last_purge_at: str


@strawberry.type
class CacheInvalidationType:
    id: strawberry.ID
    domain: str
    scope: str
    status: str
    targets_count: int
    triggered_by: str
    created_at: str


@strawberry.type
class CloudflareQueryExtension:
    @strawberry.field(description='Cloudflare zones registered to this Morpheus instance.')
    def cloudflare_zones(self, info: strawberry.Info) -> list[CloudflareZoneType]:
        from plugins.installed.cloudflare.models import CloudflareZone

        require_authenticated(info)
        if not has_scope(info, 'admin:cloudflare'):
            return []
        return [
            CloudflareZoneType(
                id=str(z.id),
                zone_id=z.zone_id,
                domain=z.domain,
                is_active=z.is_active,
                auto_purge_on_product_update=z.auto_purge_on_product_update,
                last_purge_at=z.last_purge_at.isoformat() if z.last_purge_at else '',
            )
            for z in CloudflareZone.objects.select_related('account')
        ]

    @strawberry.field(description='Recent cache purge audit log.')
    def cloudflare_invalidations(
        self,
        info: strawberry.Info,
        first: int = 25,
    ) -> list[CacheInvalidationType]:
        from plugins.installed.cloudflare.models import CacheInvalidation

        require_authenticated(info)
        if not has_scope(info, 'admin:cloudflare'):
            return []
        first = max(1, min(int(first), 100))
        qs = CacheInvalidation.objects.select_related('zone').order_by('-created_at')[:first]
        return [
            CacheInvalidationType(
                id=str(i.id),
                domain=i.zone.domain,
                scope=i.scope,
                status=i.status,
                targets_count=len(i.targets or []),
                triggered_by=i.triggered_by,
                created_at=i.created_at.isoformat(),
            )
            for i in qs
        ]
