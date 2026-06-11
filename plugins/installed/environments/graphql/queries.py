"""GraphQL surface for the Environments plugin."""

from __future__ import annotations

import strawberry

from api.graphql_permissions import has_scope, require_authenticated


@strawberry.type
class EnvironmentType:
    id: strawberry.ID
    name: str
    slug: str
    kind: str
    is_protected: bool
    is_active: bool
    domain: str


@strawberry.type
class DeploymentType:
    id: strawberry.ID
    target_slug: str
    status: str
    note: str
    started_at: str
    finished_at: str | None


@strawberry.type
class EnvironmentsQueryExtension:
    @strawberry.field(description='Resolve the environment for the current request.')
    def current_environment(self, info: strawberry.Info) -> EnvironmentType | None:
        request = (
            info.context.get('request')
            if isinstance(info.context, dict)
            else getattr(info.context, 'request', None)
        )
        env = getattr(request, 'environment', None)
        if env is None:
            return None
        return EnvironmentType(
            id=str(env.id),
            name=env.name,
            slug=env.slug,
            kind=env.kind,
            is_protected=env.is_protected,
            is_active=env.is_active,
            domain=env.domain,
        )

    @strawberry.field(description='List environments visible to the caller.')
    def environments(self, info: strawberry.Info) -> list[EnvironmentType]:
        from plugins.installed.environments.models import Environment

        require_authenticated(info)
        if not has_scope(info, 'read:environments'):
            return []
        return [
            EnvironmentType(
                id=str(e.id),
                name=e.name,
                slug=e.slug,
                kind=e.kind,
                is_protected=e.is_protected,
                is_active=e.is_active,
                domain=e.domain,
            )
            for e in Environment.objects.all()
        ]

    @strawberry.field(description='Recent deployments to a given environment.')
    def deployments(
        self,
        info: strawberry.Info,
        environment_slug: str,
        first: int = 25,
    ) -> list[DeploymentType]:
        from plugins.installed.environments.models import Deployment

        require_authenticated(info)
        if not has_scope(info, 'read:environments'):
            return []
        first = max(1, min(int(first), 100))
        qs = (
            Deployment.objects.filter(target__slug=environment_slug)
            .select_related('target')
            .order_by('-started_at')[:first]
        )
        return [
            DeploymentType(
                id=str(d.id),
                target_slug=d.target.slug,
                status=d.status,
                note=d.note,
                started_at=d.started_at.isoformat(),
                finished_at=d.finished_at.isoformat() if d.finished_at else None,
            )
            for d in qs
        ]
