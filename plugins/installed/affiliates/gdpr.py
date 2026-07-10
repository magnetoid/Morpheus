"""affiliates' slice of the GDPR export hook — Affiliate rows + commissions."""

from __future__ import annotations


def on_customer_export(value, customer=None, **kwargs):
    from plugins.installed.affiliates.models import (  # noqa: PLC0415
        Affiliate,
        AffiliateConversion,
    )

    affiliates = []
    for aff in Affiliate.objects.filter(user=customer):
        conversions = [
            {
                'order': c.order.order_number if c.order_id else '',
                'commission': str(c.commission),
                'status': c.status,
                'created_at': c.created_at,
            }
            for c in AffiliateConversion.objects.filter(affiliate=aff).select_related('order')
        ]
        affiliates.append(
            {
                'handle': aff.handle,
                'status': aff.status,
                'display_name': aff.display_name,
                'company': aff.company,
                'payout_email': aff.payout_email,
                'accrued_balance': str(aff.accrued_balance),
                'lifetime_paid': str(aff.lifetime_paid),
                'created_at': aff.created_at,
                'approved_at': aff.approved_at,
                'conversions': conversions,
            }
        )
    value['affiliate.json'] = affiliates
    return value
