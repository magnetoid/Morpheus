"""Newsletter subscription lifecycle — double opt-in.

subscribe() → pending + confirm email; confirm(token) → confirmed + welcome;
unsubscribe(token) → unsubscribed (terminal). Emails go through the core
templated-email pipeline so the merchant can edit them centrally.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.newsletter')


def _confirm_url(token: str) -> str:
    from core.utils.site import site_base_url

    return f'{site_base_url()}/newsletter/confirm/{token}/'


def _unsubscribe_url(token: str) -> str:
    from core.utils.site import site_base_url

    return f'{site_base_url()}/newsletter/unsubscribe/{token}/'


def subscribe(email: str, *, source: str = 'popup', customer=None):
    """Add an email as a PENDING subscriber and send the confirmation email.

    Idempotent: re-subscribing a pending row re-sends confirmation; an already
    confirmed row is left as-is. Returns (subscriber, created)."""
    from plugins.installed.newsletter.models import NewsletterSubscriber

    email = (email or '').strip().lower()
    if not email or '@' not in email:
        return None, False

    sub, created = NewsletterSubscriber.objects.get_or_create(
        email=email,
        defaults={'source': source, 'customer': customer},
    )
    if sub.status == 'confirmed':
        return sub, created
    # (re)set to pending and (re)send confirmation for new or unconfirmed rows.
    if sub.status != 'pending':
        sub.status = 'pending'
        sub.save(update_fields=['status', 'updated_at'])
    _send_confirm(sub)
    return sub, created


def confirm(token: str):
    """Confirm a pending subscriber. Returns the subscriber or None."""
    from django.utils import timezone

    from plugins.installed.newsletter.models import NewsletterSubscriber

    sub = NewsletterSubscriber.objects.filter(confirm_token=token).first()
    if sub is None:
        return None
    if sub.status == 'unsubscribed':
        # Terminal. confirm_token never rotates, so an opted-out person's
        # ORIGINAL confirmation link stays valid forever — clicking it must NOT
        # silently re-add them to the mailable audience. Re-opting-in has to go
        # through subscribe() (which resets to 'pending' + re-sends consent).
        return None
    if sub.status != 'confirmed':
        sub.status = 'confirmed'
        sub.confirmed_at = timezone.now()
        sub.save(update_fields=['status', 'confirmed_at', 'updated_at'])
        _send_welcome(sub)
    return sub


def unsubscribe(token: str):
    """Mark a subscriber unsubscribed (terminal). Returns the subscriber or None."""
    from django.utils import timezone

    from plugins.installed.newsletter.models import NewsletterSubscriber

    sub = NewsletterSubscriber.objects.filter(confirm_token=token).first()
    if sub is None:
        return None
    if sub.status != 'unsubscribed':
        sub.status = 'unsubscribed'
        sub.unsubscribed_at = timezone.now()
        sub.save(update_fields=['status', 'unsubscribed_at', 'updated_at'])
    return sub


def _send_confirm(sub) -> None:
    _send(
        'newsletter_confirm',
        sub,
        'Please confirm your subscription',
        extra={
            'confirm_url': _confirm_url(sub.confirm_token),
        },
    )


def _send_welcome(sub) -> None:
    _send(
        'newsletter_welcome',
        sub,
        'You’re subscribed 🎉',
        extra={
            'unsubscribe_url': _unsubscribe_url(sub.confirm_token),
        },
    )


def _send(key: str, sub, subject: str, *, extra: dict) -> None:
    from core.emails import send_templated_email

    send_templated_email(
        key,
        to=sub.email,
        subject=subject,
        ctx={'subscriber': sub, 'email': sub.email, **extra},
    )
