"""The live-shopping card on the Marketing overview (DashboardCard)."""

from __future__ import annotations

from django.utils import formats, timezone


def live_card(request) -> dict:
    """What is live now, else what is coming up next."""
    from plugins.installed.live_commerce.models import LiveEvent

    live = LiveEvent.objects.filter(status='live').order_by('scheduled_start').first()
    upcoming = LiveEvent.objects.filter(
        status='scheduled', scheduled_start__gte=timezone.now()
    ).order_by('scheduled_start')
    if live is not None:
        return {
            'value': 'Live now',
            'caption': live.title,
            'tone': 'ok',
            'rows': [(e.title, _when(e)) for e in upcoming[:2]],
        }
    nxt = upcoming.first()
    if nxt is None:
        return {'empty': 'No live show scheduled.'}
    return {
        'value': _when(nxt),
        'caption': f'next: {nxt.title}',
        'rows': [(e.title, _when(e)) for e in upcoming[1:3]],
    }


def _when(event) -> str:
    return formats.date_format(timezone.localtime(event.scheduled_start), 'M j, H:i')
