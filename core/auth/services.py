"""Pure helpers for the passwordless OTP flow."""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.auth.models import EmailOTP

logger = logging.getLogger('morpheus.core.auth')


_VALIDITY_MINUTES = 10
_CODE_LENGTH = 6
_MAX_RECENT_PER_EMAIL = 5  # rolling window — refuse if too many in last hour


def _hash_code(*, code: str, email: str) -> str:
    """SHA-256 over (code || email) so a leaked DB doesn't leak codes."""
    payload = f'{code.strip()}::{email.strip().lower()}'
    return hashlib.sha256(payload.encode()).hexdigest()


def issue_otp(email: str, *, request_ip: str | None = None) -> tuple[str, EmailOTP] | tuple[None, None]:
    """Issue a fresh OTP. Invalidates any prior unconsumed code for this email.

    Returns ``(code, model)`` on success. Returns ``(None, None)`` and
    logs a warning when the rate cap is hit; the caller should respond
    with a generic "we're working on it" message rather than leak that
    state.
    """
    email = (email or '').strip().lower()
    if not email or '@' not in email:
        return (None, None)

    cutoff = timezone.now() - timedelta(hours=1)
    recent = EmailOTP.objects.filter(email=email, created_at__gte=cutoff).count()
    if recent >= _MAX_RECENT_PER_EMAIL:
        logger.warning('otp: rate cap hit for %s (%d in last hour)', email, recent)
        return (None, None)

    # Invalidate any live, unconsumed code so only the latest works.
    now = timezone.now()
    EmailOTP.objects.filter(email=email, consumed_at__isnull=True).update(consumed_at=now)

    code = ''.join(secrets.choice('0123456789') for _ in range(_CODE_LENGTH))
    obj = EmailOTP.objects.create(
        email=email,
        code_hash=_hash_code(code=code, email=email),
        expires_at=now + timedelta(minutes=_VALIDITY_MINUTES),
        request_ip=request_ip,
    )
    return (code, obj)


def consume_otp(email: str, code: str):
    """Verify a code + return the matching User (creating one if missing).

    Returns the `User` instance on success, or ``None`` on:
      * unknown / wrong code,
      * expired code,
      * already-consumed code.

    A successful consume marks the row consumed and ensures the user
    exists. Auto-creating users on first OTP keeps the shopper flow
    one-step (paste code → logged in) without a separate signup form.
    """
    email = (email or '').strip().lower()
    code = (code or '').strip()
    if not (email and code):
        return None

    code_hash = _hash_code(code=code, email=email)
    now = timezone.now()
    obj = (
        EmailOTP.objects
        .filter(email=email, code_hash=code_hash, consumed_at__isnull=True,
                expires_at__gt=now)
        .order_by('-created_at')
        .first()
    )
    if obj is None:
        return None

    obj.consumed_at = now
    obj.save(update_fields=['consumed_at'])

    User = get_user_model()
    user, created = User.objects.get_or_create(
        email=email,
        defaults={'username': email[:150]} if 'username' in {f.name for f in User._meta.fields} else {},
    )
    if created and hasattr(user, 'source') and not user.source:
        user.source = 'signup'
        user.save(update_fields=['source'])
    return user


def send_otp_email(*, to: str, code: str) -> None:
    """Best-effort send of the OTP via the configured email backend.

    Failures are logged but never raised; the calling view must NOT
    leak send-failures to the user (would expose whether an account
    exists). Generic "if your email is on file, a code is on the way"
    response is the right shape for the calling view.
    """
    try:
        from django.core.mail import EmailMultiAlternatives
        subject = 'Your sign-in code'
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com')
        text = (
            f'Your sign-in code is {code}.\n\n'
            f'It expires in {_VALIDITY_MINUTES} minutes. If you didn\'t '
            f'request it, you can safely ignore this message.'
        )
        html = (
            f'<p style="font-family:system-ui,sans-serif;font-size:14px;">'
            f'Your sign-in code is:</p>'
            f'<p style="font-family:Menlo,monospace;font-size:32px;letter-spacing:.3em;'
            f'font-weight:600;color:#1a1a1a;">{code}</p>'
            f'<p style="font-size:12px;color:#666;">Expires in {_VALIDITY_MINUTES} '
            f'minutes. If you didn\'t request this, ignore the message.</p>'
        )
        msg = EmailMultiAlternatives(subject, text, from_email, [to])
        msg.attach_alternative(html, 'text/html')
        msg.send(fail_silently=True)
    except Exception as e:  # noqa: BLE001 — never bubble; caller will handle
        logger.warning('otp send failed for %s: %s', to, e, exc_info=True)
