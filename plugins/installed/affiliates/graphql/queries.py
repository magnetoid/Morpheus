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

    # NOTE: a previous version of this file shipped an `apply_as_affiliate`
    # GraphQL mutation. It was dead code — the storefront affiliate
    # apply page uses a Django POST handler at /affiliates/apply/, not
    # GraphQL. Removing the mutation collapses two implementations of
    # the same logic into one (see plugins.installed.affiliates.views.apply
    # for the canonical path, and services.generate_unique_handle for
    # the shared slug-generation helper).
