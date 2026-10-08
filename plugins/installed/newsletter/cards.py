"""The newsletter card on the Marketing overview (DashboardCard)."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone


def newsletter_card(request) -> dict:
    """Confirmed subscribers, the last week's new ones, and what is pending."""
    from plugins.installed.newsletter.models import NewsletterSubscriber, SignupPopup

    subs = NewsletterSubscriber.objects
    confirmed = subs.filter(status='confirmed').count()
    week = subs.filter(status='confirmed', confirmed_at__gte=timezone.now() - timedelta(days=7))
    pending = subs.filter(status='pending').count()
    if not (confirmed or pending):
        return {'empty': 'No subscribers yet.'}
    return {
        'value': str(confirmed),
        'caption': 'confirmed subscribers',
        'rows': [
            ('New this week', week.count()),
            ('Awaiting confirmation', pending),
            ('Sign-up popups on', SignupPopup.objects.filter(enabled=True).count()),
        ],
    }
