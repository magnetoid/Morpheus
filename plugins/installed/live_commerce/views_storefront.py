"""Public storefront views for live events."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from plugins.installed.live_commerce import services


def live_index(request: HttpRequest) -> HttpResponse:
    """List upcoming/live events and past replays."""
    return render(
        request,
        'live_commerce/list.html',
        {
            'upcoming': list(services.upcoming_or_live()),
            'past': list(services.past_events()),
        },
    )


def live_event(request: HttpRequest, slug: str) -> HttpResponse:
    """Event page: embedded player + pinned product rail (UTM-tagged links)."""
    from plugins.installed.live_commerce.models import LiveEvent

    event = get_object_or_404(LiveEvent.objects.prefetch_related('products__product'), slug=slug)
    rail = [
        {'product': ep.product, 'url': services.utm_link(ep.product, event.slug)}
        for ep in event.products.all()
    ]
    return render(
        request,
        'live_commerce/event.html',
        {'event': event, 'rail': rail},
    )
