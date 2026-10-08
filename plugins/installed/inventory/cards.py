"""The stockout-forecast card on the Products list (DashboardCard).

The forecast's page is a list of the SKUs about to run out; the card is the
count and the worst three, linking to it."""

from __future__ import annotations


def stockout_card(request) -> dict:
    from plugins.installed.inventory.models import StockoutAlert

    alerts = StockoutAlert.objects.filter(status='open')
    total = alerts.count()
    if not total:
        return {'empty': 'Nothing is projected to run out.'}
    rows = []
    for alert in alerts.select_related('variant__product').order_by('days_of_cover')[:3]:
        variant = alert.variant
        name = variant.product.name if variant is not None else '—'
        cover = '—' if alert.days_of_cover is None else f'{alert.days_of_cover:.0f} days left'
        rows.append((name, cover))
    return {
        'value': str(total),
        'caption': f'SKU{"s" if total != 1 else ""} projected to run out before restock',
        'tone': 'warn',
        'rows': rows,
    }
