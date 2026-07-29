"""Live-commerce query + status-transition helpers."""

from __future__ import annotations


def upcoming_or_live():
    """Scheduled + live events, soonest first — for the teaser and list header."""
    from plugins.installed.live_commerce.models import LiveEvent

    return LiveEvent.objects.filter(status__in=['scheduled', 'live']).order_by('scheduled_start')


def past_events(limit: int = 24):
    """Ended events, most recent first."""
    from plugins.installed.live_commerce.models import LiveEvent

    return LiveEvent.objects.filter(status='ended').order_by('-scheduled_start')[:limit]


def featured_teaser():
    """The single event to tease on the storefront (live wins, else next scheduled)."""
    live = upcoming_or_live()
    return live.filter(status='live').first() or live.first()


def utm_link(product, campaign: str) -> str:
    """Storefront product URL tagged so live-driven conversions attribute via UTM."""
    return f'/products/{product.slug}/?utm_source=live&utm_medium=live_commerce&utm_campaign={campaign}'


def set_status(event, status: str) -> bool:
    """Transition an event's status, firing the matching hook on real changes.

    Returns True if the status actually changed.
    """
    from morpheus.core import MorpheusEvents, hook_registry

    if status not in {'scheduled', 'live', 'ended'} or event.status == status:
        return False
    event.status = status
    if status == 'ended':
        event.save(update_fields=['status', 'updated_at'])
        hook_registry.fire(MorpheusEvents.LIVE_EVENT_ENDED, live_event=event)
    elif status == 'live':
        event.save(update_fields=['status', 'updated_at'])
        hook_registry.fire(MorpheusEvents.LIVE_EVENT_STARTED, live_event=event)
    else:
        event.save(update_fields=['status', 'updated_at'])
    return True
