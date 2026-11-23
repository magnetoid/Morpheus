"""One-click unsubscribe from the post-purchase marketing emails (C1, v0.189.0).

The review request and the survey are marketing, so each carries the RFC 8058
pair (``List-Unsubscribe`` + ``List-Unsubscribe-Post``) and a footer link. The
token is the address signed: a send needs no row, and an opt-out is recorded
only when someone unsubscribes. A mail client's one-click POST records it at
once; a person following the link gets a button first, because link scanners
fetch every GET in an email and would otherwise unsubscribe everyone.
"""

from __future__ import annotations

from django.core import signing

_SALT = 'post_purchase.unsubscribe'


def _clean(email: str) -> str:
    return (email or '').strip().lower()


def unsubscribe_url(email: str) -> str:
    from django.urls import reverse  # noqa: PLC0415

    from core.utils.site import site_base_url  # noqa: PLC0415

    token = signing.dumps({'e': _clean(email)}, salt=_SALT)
    path = reverse('post_purchase:unsubscribe', kwargs={'token': token})
    return f'{site_base_url().rstrip("/")}{path}'


def headers(email: str) -> dict:
    return {
        'List-Unsubscribe': f'<{unsubscribe_url(email)}>',
        'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
    }


def email_from_token(token: str) -> str | None:
    """The address a token names, or None for a forged one. It never expires."""
    try:
        data = signing.loads(token, salt=_SALT)
    except signing.BadSignature:
        return None
    email = _clean(data.get('e', '')) if isinstance(data, dict) else ''
    return email or None


def opted_out(email: str) -> bool:
    from plugins.installed.post_purchase.models import JourneyOptOut  # noqa: PLC0415

    email = _clean(email)
    return bool(email) and JourneyOptOut.objects.filter(email=email).exists()


def opt_out(email: str) -> None:
    from plugins.installed.post_purchase.models import JourneyOptOut  # noqa: PLC0415

    JourneyOptOut.objects.get_or_create(email=_clean(email))
