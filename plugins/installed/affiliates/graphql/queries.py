"""Affiliate GraphQL queries and mutations."""
from __future__ import annotations

from typing import List, Optional

import strawberry

from api.graphql_permissions import (
    PermissionDenied,
    current_customer,
    has_scope,
    require_authenticated,
)


@strawberry.type
class AffiliateLinkType:
    id: strawberry.ID
    code: str
    landing_url: str
    label: str
    is_active: bool
    click_count: int
    conversion_count: int


@strawberry.type
class AffiliateAccountType:
    id: strawberry.ID
    handle: str
    status: str
    accrued_amount: str
    accrued_currency: str


@strawberry.type
class AffiliatesQueryExtension:

    @strawberry.field(description="The current user's affiliate accounts.")
    def my_affiliate_accounts(self, info: strawberry.Info) -> List[AffiliateAccountType]:
        require_authenticated(info)
        customer = current_customer(info)
        if customer is None:
            return []
        from plugins.installed.affiliates.models import Affiliate
        return [
            AffiliateAccountType(
                id=str(a.id), handle=a.handle, status=a.status,
                accrued_amount=str(a.accrued_balance.amount),
                accrued_currency=str(a.accrued_balance.currency),
            )
            for a in Affiliate.objects.filter(user=customer)
        ]

    @strawberry.field(description="An affiliate's links (must own the account).")
    def affiliate_links(
        self, info: strawberry.Info, affiliate_id: strawberry.ID,
    ) -> List[AffiliateLinkType]:
        require_authenticated(info)
        customer = current_customer(info)
        from plugins.installed.affiliates.models import Affiliate, AffiliateLink

        try:
            affiliate = Affiliate.objects.get(pk=str(affiliate_id))
        except Affiliate.DoesNotExist as e:
            raise PermissionDenied('Affiliate not found') from e
        if affiliate.user_id != customer.pk and not has_scope(info, 'admin:affiliates'):
            raise PermissionDenied('Cannot read links for an affiliate you do not own')
        return [
            AffiliateLinkType(
                id=str(link.id), code=link.code, landing_url=link.landing_url,
                label=link.label, is_active=link.is_active,
                click_count=link.click_count, conversion_count=link.conversion_count,
            )
            for link in AffiliateLink.objects.filter(affiliate=affiliate)
        ]


@strawberry.input
class CreateAffiliateLinkInput:
    affiliate_id: strawberry.ID
    landing_url: str = '/'
    label: str = ''


@strawberry.input
class ApplyAsAffiliateInput:
    handle: str
    program_slug: str = ''      # empty → first active program
    payout_email: str = ''
    company: str = ''
    notes: str = ''


@strawberry.type
class AffiliatesMutationExtension:

    @strawberry.mutation(description='Create a tracked link for one of your affiliate accounts.')
    def create_affiliate_link(
        self, info: strawberry.Info, input: CreateAffiliateLinkInput,
    ) -> AffiliateLinkType:
        require_authenticated(info)
        customer = current_customer(info)
        from plugins.installed.affiliates.models import Affiliate, AffiliateLink

        try:
            affiliate = Affiliate.objects.get(pk=str(input.affiliate_id), user=customer)
        except Affiliate.DoesNotExist as e:
            raise PermissionDenied('Affiliate not found') from e
        if affiliate.status != 'approved':
            raise PermissionDenied('Affiliate account is not approved')

        link = AffiliateLink.objects.create(
            affiliate=affiliate,
            landing_url=input.landing_url[:500] or '/',
            label=input.label[:100],
        )
        return AffiliateLinkType(
            id=str(link.id), code=link.code, landing_url=link.landing_url,
            label=link.label, is_active=link.is_active,
            click_count=link.click_count, conversion_count=link.conversion_count,
        )

    @strawberry.mutation(description='Apply to become an affiliate. Creates a pending Affiliate row that an admin must approve.')
    def apply_as_affiliate(
        self, info: strawberry.Info, input: ApplyAsAffiliateInput,
    ) -> AffiliateAccountType:
        require_authenticated(info)
        customer = current_customer(info)
        from django.utils.text import slugify
        from plugins.installed.affiliates.models import Affiliate, AffiliateProgram

        # Resolve the program — explicit slug if given, otherwise first active.
        program = None
        if input.program_slug:
            program = AffiliateProgram.objects.filter(
                slug=input.program_slug, is_active=True,
            ).first()
        if program is None:
            program = AffiliateProgram.objects.filter(is_active=True).order_by('created_at').first()
        if program is None:
            raise PermissionDenied('No active affiliate program is accepting applications.')

        # Don't let the same customer apply twice to the same program.
        existing = Affiliate.objects.filter(user=customer, program=program).first()
        if existing:
            return AffiliateAccountType(
                id=str(existing.id), handle=existing.handle, status=existing.status,
                accrued_amount=str(existing.accrued_balance.amount),
                accrued_currency=str(existing.accrued_balance.currency),
            )

        # `handle` is the unique slug used in tracked links. Slugify defensively
        # and append a short suffix if it collides.
        handle = slugify(input.handle)[:80] or slugify(customer.email.split('@')[0])[:80]
        base = handle
        idx = 2
        while Affiliate.objects.filter(handle=handle).exists():
            handle = f'{base[:74]}-{idx}'
            idx += 1
            if idx > 50:
                raise PermissionDenied('Could not pick a unique handle.')

        a = Affiliate.objects.create(
            program=program,
            user=customer,
            handle=handle,
            status='pending',
            company=(input.company or '')[:200],
            payout_email=(input.payout_email or customer.email)[:254],
            notes=(input.notes or '')[:2000],
        )
        return AffiliateAccountType(
            id=str(a.id), handle=a.handle, status=a.status,
            accrued_amount=str(a.accrued_balance.amount),
            accrued_currency=str(a.accrued_balance.currency),
        )
