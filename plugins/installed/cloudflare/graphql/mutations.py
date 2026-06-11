"""Cloudflare plugin — GraphQL mutations (manual purge from the admin)."""

from __future__ import annotations

import strawberry

from api.graphql_permissions import (
    PermissionDenied,
    has_scope,
    require_authenticated,
)


@strawberry.type
class PurgeResult:
    success: bool
    invalidation_id: strawberry.ID
    status: str
    error: str


@strawberry.input
class PurgeUrlsInput:
    zone_id: strawberry.ID
    urls: list[str]


@strawberry.type
class CloudflareMutationExtension:
    @strawberry.mutation(description='Manually purge specific URLs from a zone (admin:cloudflare).')
    def purge_cloudflare_urls(
        self,
        info: strawberry.Info,
        input: PurgeUrlsInput,
    ) -> PurgeResult:
        from plugins.installed.cloudflare.models import CloudflareZone
        from plugins.installed.cloudflare.services import purge_urls

        require_authenticated(info)
        if not has_scope(info, 'admin:cloudflare'):
            raise PermissionDenied('admin:cloudflare scope required')

        try:
            zone = CloudflareZone.objects.select_related('account').get(pk=str(input.zone_id))
        except CloudflareZone.DoesNotExist as e:
            raise PermissionDenied('Zone not found') from e

        urls = [u.strip() for u in input.urls if u.strip()]
        if not urls:
            return PurgeResult(
                success=False,
                invalidation_id='',
                status='failed',
                error='At least one URL required',
            )

        inv = purge_urls(zone=zone, urls=urls, triggered_by='manual:graphql')
        return PurgeResult(
            success=inv.status == 'succeeded',
            invalidation_id=str(inv.id),
            status=inv.status,
            error=inv.error_message,
        )

    @strawberry.mutation(description='Manually purge ALL cache for a zone (destructive).')
    def purge_cloudflare_everything(
        self,
        info: strawberry.Info,
        zone_id: strawberry.ID,
    ) -> PurgeResult:
        from plugins.installed.cloudflare.models import CloudflareZone
        from plugins.installed.cloudflare.services import purge_everything

        require_authenticated(info)
        if not has_scope(info, 'admin:cloudflare'):
            raise PermissionDenied('admin:cloudflare scope required')

        try:
            zone = CloudflareZone.objects.select_related('account').get(pk=str(zone_id))
        except CloudflareZone.DoesNotExist as e:
            raise PermissionDenied('Zone not found') from e

        inv = purge_everything(zone=zone, triggered_by='manual:graphql')
        return PurgeResult(
            success=inv.status == 'succeeded',
            invalidation_id=str(inv.id),
            status=inv.status,
            error=inv.error_message,
        )
