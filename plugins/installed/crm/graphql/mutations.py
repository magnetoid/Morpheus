"""CRM GraphQL mutations (admin-only)."""

from __future__ import annotations

import strawberry


@strawberry.type
class CrmLeadMutationResult:
    id: strawberry.ID
    email: str
    status: str
    error: str


@strawberry.input
class CrmCreateLeadInput:
    email: str
    first_name: str = ''
    last_name: str = ''
    company: str = ''
    phone: str = ''
    source: str = 'manual'


def _is_staff(info) -> bool:
    request = getattr(info.context, 'request', None) or (
        info.context.get('request') if isinstance(info.context, dict) else None
    )
    user = getattr(request, 'user', None) if request else None
    return bool(user and getattr(user, 'is_staff', False))


@strawberry.type
class CrmMutationExtension:
    @strawberry.mutation(description='Create or update a CRM lead by email.')
    def crm_create_lead(
        self,
        info: strawberry.Info,
        input: CrmCreateLeadInput,
    ) -> CrmLeadMutationResult:
        if not _is_staff(info):
            return CrmLeadMutationResult(
                id=strawberry.ID(''),
                email=input.email,
                status='',
                error='Forbidden — staff only.',
            )
        from plugins.installed.crm.services import upsert_lead

        try:
            lead = upsert_lead(
                email=input.email,
                first_name=input.first_name,
                last_name=input.last_name,
                company=input.company,
                phone=input.phone,
                source=input.source,
            )
        except Exception as e:  # noqa: BLE001
            return CrmLeadMutationResult(
                id=strawberry.ID(''),
                email=input.email,
                status='',
                error=str(e),
            )
        return CrmLeadMutationResult(
            id=strawberry.ID(str(lead.id)),
            email=lead.email,
            status=lead.status,
            error='',
        )
