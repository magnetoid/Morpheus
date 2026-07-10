"""CRM GraphQL queries (admin-only)."""

from __future__ import annotations

import strawberry

from api.graphql_permissions import is_staff as _is_staff


@strawberry.type
class CrmLeadType:
    id: strawberry.ID
    email: str
    name: str
    company: str
    source: str
    status: str
    score: int
    created_at: str


@strawberry.type
class CrmInteractionType:
    id: strawberry.ID
    kind: str
    direction: str
    summary: str
    actor: str
    occurred_at: str


@strawberry.type
class CrmTaskType:
    id: strawberry.ID
    title: str
    priority: str
    due_at: str
    is_open: bool
    is_overdue: bool


@strawberry.type
class CrmQueryExtension:
    @strawberry.field(description='List CRM leads (staff only).')
    def crm_leads(
        self,
        info: strawberry.Info,
        first: int = 25,
        status: str | None = None,
    ) -> list[CrmLeadType]:
        if not _is_staff(info):
            return []
        from plugins.installed.crm.models import Lead

        first = max(1, min(int(first or 25), 100))
        qs = Lead.objects.all().order_by('-created_at')
        if status:
            qs = qs.filter(status=status)
        return [
            CrmLeadType(
                id=strawberry.ID(str(lead.id)),
                email=lead.email,
                name=lead.display_name,
                company=lead.company,
                source=lead.source,
                status=lead.status,
                score=lead.score,
                created_at=lead.created_at.isoformat(),
            )
            for lead in qs[:first]
        ]

    @strawberry.field(description='Customer interaction timeline (staff only).')
    def customer_timeline(
        self,
        info: strawberry.Info,
        email: str,
        first: int = 50,
    ) -> list[CrmInteractionType]:
        if not _is_staff(info):
            return []
        from django.contrib.auth import get_user_model

        from plugins.installed.crm.services import customer_timeline

        User = get_user_model()
        customer = User.objects.filter(email__iexact=email).first()
        if not customer:
            return []
        rows = customer_timeline(customer, limit=max(1, min(int(first or 50), 200)))
        return [
            CrmInteractionType(
                id=strawberry.ID(str(r.id)),
                kind=r.kind,
                direction=r.direction,
                summary=r.summary,
                actor=getattr(r.actor, 'email', '') if r.actor_id else r.actor_name,
                occurred_at=r.occurred_at.isoformat(),
            )
            for r in rows
        ]

    @strawberry.field(description='Open follow-up tasks (staff only).')
    def crm_open_tasks(
        self,
        info: strawberry.Info,
        first: int = 50,
    ) -> list[CrmTaskType]:
        if not _is_staff(info):
            return []
        from plugins.installed.crm.models import CrmTask

        first = max(1, min(int(first or 50), 200))
        qs = CrmTask.objects.filter(completed_at__isnull=True).order_by('due_at')[:first]
        return [
            CrmTaskType(
                id=strawberry.ID(str(t.id)),
                title=t.title,
                priority=t.priority,
                due_at=t.due_at.isoformat(),
                is_open=t.is_open,
                is_overdue=t.is_overdue,
            )
            for t in qs
        ]
