"""CRM GraphQL mutations (admin-only)."""

from __future__ import annotations

import strawberry

from api.graphql_permissions import mutation_scope_error


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


@strawberry.type
class CrmMutationExtension:
    @strawberry.mutation(description='Create or update a CRM lead by email.')
    def crm_create_lead(
        self,
        info: strawberry.Info,
        input: CrmCreateLeadInput,
    ) -> CrmLeadMutationResult:
        denied = mutation_scope_error(info, ['crm.write'])
        if denied:
            return CrmLeadMutationResult(
                id=strawberry.ID(''),
                email=input.email,
                status='',
                error=denied,
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
