"""GraphQL queries for the Functions plugin."""

from __future__ import annotations

import strawberry

from api.graphql_permissions import has_scope, require_authenticated


@strawberry.type
class FunctionType:
    id: strawberry.ID
    target: str
    name: str
    description: str
    is_enabled: bool
    priority: int
    invocation_count: int
    error_count: int
    last_error: str


@strawberry.type
class FunctionsQueryExtension:
    @strawberry.field(
        description='List functions visible to the caller (admin or read:functions scope).'
    )
    def functions(
        self,
        info: strawberry.Info,
        target: str | None = None,
    ) -> list[FunctionType]:
        from plugins.installed.functions.models import Function

        require_authenticated(info)
        if not has_scope(info, 'read:functions'):
            return []
        qs = Function.objects.all()
        if target:
            qs = qs.filter(target=target)
        return [
            FunctionType(
                id=str(f.id),
                target=f.target,
                name=f.name,
                description=f.description,
                is_enabled=f.is_enabled,
                priority=f.priority,
                invocation_count=f.invocation_count,
                error_count=f.error_count,
                last_error=f.last_error,
            )
            for f in qs
        ]
