"""GraphQL queries for the marketplace plugin."""

from __future__ import annotations

import strawberry

from api.graphql_permissions import has_scope, require_authenticated


@strawberry.type
class VendorOrderType:
    id: strawberry.ID
    parent_order_number: str
    vendor_name: str
    status: str
    gross_amount: str
    commission_amount: str
    net_amount: str
    currency: str


@strawberry.type
class VendorPayoutType:
    id: strawberry.ID
    vendor_name: str
    status: str
    amount: str
    currency: str
    method: str
    requested_at: str
    paid_at: str


@strawberry.type
class MarketplaceQueryExtension:
    @strawberry.field(
        description="A vendor's orders. Requires vendor:self or admin:marketplace scope."
    )
    def my_vendor_orders(self, info: strawberry.Info, first: int = 25) -> list[VendorOrderType]:
        from plugins.installed.marketplace.models import VendorOrder

        require_authenticated(info)
        if not (has_scope(info, 'vendor:self') or has_scope(info, 'admin:marketplace')):
            return []
        first = max(1, min(int(first), 100))
        qs = VendorOrder.objects.select_related('parent_order', 'vendor').order_by('-created_at')[
            :first
        ]
        return [
            VendorOrderType(
                id=str(v.id),
                parent_order_number=v.parent_order.order_number,
                vendor_name=v.vendor.name,
                status=v.status,
                gross_amount=str(v.gross.amount),
                commission_amount=str(v.commission.amount),
                net_amount=str(v.net.amount),
                currency=str(v.gross.currency),
            )
            for v in qs
        ]

    @strawberry.field(description="A vendor's payout history.")
    def my_vendor_payouts(self, info: strawberry.Info, first: int = 25) -> list[VendorPayoutType]:
        from plugins.installed.marketplace.models import VendorPayout

        require_authenticated(info)
        if not (has_scope(info, 'vendor:self') or has_scope(info, 'admin:marketplace')):
            return []
        first = max(1, min(int(first), 100))
        qs = VendorPayout.objects.select_related('vendor').order_by('-requested_at')[:first]
        return [
            VendorPayoutType(
                id=str(p.id),
                vendor_name=p.vendor.name,
                status=p.status,
                amount=str(p.amount.amount),
                currency=str(p.amount.currency),
                method=p.method,
                requested_at=p.requested_at.isoformat(),
                paid_at=p.paid_at.isoformat() if p.paid_at else '',
            )
            for p in qs
        ]
