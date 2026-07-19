"""Cart-recovery unsubscribe: signed one-click token + email suppression.

RFC 8058 requires bulk marketing mail to carry a ``List-Unsubscribe`` header
plus a one-click ``List-Unsubscribe-Post`` — without them Gmail/Yahoo junk the
send. Cart-recovery recipients aren't newsletter subscribers, so we mint a
stateless *signed* token over the address (no DB row needed to send) and record
an opt-out only when the shopper actually unsubscribes. The token is the auth —
unguessable, and the action only ever *adds* a suppression, so it's safe to
expose to a bare POST from an email provider with no session or CSRF cookie.
"""

from __future__ import annotations

from django.core import signing

_SALT = 'cart-recovery-unsub'


def unsubscribe_token(email: str) -> str:
    """A signed, URL-safe token identifying ``email`` for one-click unsubscribe."""
    return signing.dumps({'e': (email or '').strip().lower()}, salt=_SALT)


def email_from_token(token: str) -> str | None:
    """Recover the address from a token, or None if it's forged/garbled.

    No ``max_age`` — an unsubscribe link must never expire."""
    try:
        data = signing.loads(token, salt=_SALT)
    except signing.BadSignature:
        return None
    email = (data.get('e') or '').strip().lower() if isinstance(data, dict) else ''
    return email or None


def recovery_unsubscribe_url(email: str) -> str:
    """The absolute one-click unsubscribe URL for ``email``."""
    from core.utils.site import site_base_url

    return f'{site_base_url().rstrip("/")}/cart-recovery/unsubscribe/{unsubscribe_token(email)}/'


def unsubscribe_headers(email: str) -> dict:
    """The RFC 8058 one-click header pair for a cart-recovery send to ``email``."""
    url = recovery_unsubscribe_url(email)
    return {
        'List-Unsubscribe': f'<{url}>',
        'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
    }


def is_suppressed(email: str) -> bool:
    """True if ``email`` has unsubscribed from cart-recovery."""
    email = (email or '').strip().lower()
    if not email:
        return False
    from plugins.installed.cart_abandonment.models import RecoverySuppression

    return RecoverySuppression.objects.filter(email__iexact=email).exists()


def suppress_from_token(token: str) -> str | None:
    """Record the opt-out for a token's address (idempotent). Returns the email,
    or None if the token is invalid."""
    email = email_from_token(token)
    if not email:
        return None
    from plugins.installed.cart_abandonment.models import RecoverySuppression

    RecoverySuppression.objects.get_or_create(email=email)
    return email
