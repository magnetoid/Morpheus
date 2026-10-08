"""The promotions card on the Marketing overview (DashboardCard)."""

from __future__ import annotations

from django.utils import timezone


def promotions_card(request) -> dict:
    """Automatic promotions running now (switched on, inside their window)."""
    from plugins.installed.promotions.models import Promotion
    from plugins.installed.promotions.services import models_q_active

    running = Promotion.objects.filter(is_active=True).filter(models_q_active(timezone.now()))
    total = running.count()
    if not total:
        return {'empty': 'No promotion is running.'}
    rows = [(p.name, f'{p.times_used} used') for p in running.order_by('priority', 'name')[:3]]
    return {'value': str(total), 'caption': 'promotions running', 'rows': rows}
