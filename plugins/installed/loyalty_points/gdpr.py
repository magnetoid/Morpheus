"""loyalty_points' slice of the GDPR export hook — balance + ledger."""

from __future__ import annotations


def on_customer_export(value, customer=None, **kwargs):
    from plugins.installed.loyalty_points.models import PointsTransaction  # noqa: PLC0415
    from plugins.installed.loyalty_points.services import get_balance  # noqa: PLC0415

    value['loyalty.json'] = {
        'balance': get_balance(customer),
        'transactions': [
            {
                'points': t.points,
                'reason': t.reason,
                'order_number': t.order_number,
                'note': t.note,
                'created_at': t.created_at,
            }
            for t in PointsTransaction.objects.filter(customer=customer)
        ],
    }
    return value
