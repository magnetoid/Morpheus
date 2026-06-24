"""Views for the staff MFA flow.

* ``challenge`` — PUBLIC. Runs during sign-in, before the session is
  established (the pending user id lives in the session, set by the
  AUTH_SECOND_FACTOR subscriber after email-OTP passes). Verifies a TOTP
  code or a one-time recovery code, then completes login.
* ``enroll`` — staff-only dashboard page. Self-service enrollment
  (QR + confirm), one-time recovery codes, and self-disable.
"""

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model, login
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from core.utils.rate_limit import RateLimitExceeded, check_and_consume
from morpheus.views import staff_required
from plugins.installed.staff_mfa import services

logger = logging.getLogger('morpheus.staff_mfa')

_CHALLENGE_MAX_ATTEMPTS = 5
_CHALLENGE_WINDOW_SECONDS = 15 * 60


def _safe_next(nxt: str | None) -> str:
    nxt = (nxt or '').strip()
    if nxt.startswith('/') and not nxt.startswith('//'):
        return nxt
    return '/dashboard/'


@csrf_protect
@require_http_methods(['GET', 'POST'])
def challenge(request):
    """TOTP / recovery-code challenge interposed during sign-in."""
    from plugins.installed.staff_mfa.models import StaffMfaDevice

    user_id = request.session.get('mfa_pending_user_id')
    nxt = _safe_next(request.session.get('mfa_next'))
    if not user_id:
        # No pending second factor — nothing to challenge. Back to step one.
        return redirect(reverse('core_auth:otp_request'))

    device = StaffMfaDevice.objects.filter(user_id=user_id, confirmed_at__isnull=False).first()
    if device is None:
        # Device was reset/removed mid-flow — drop the pending state cleanly.
        request.session.pop('mfa_pending_user_id', None)
        request.session.pop('mfa_next', None)
        return redirect(reverse('core_auth:otp_request'))

    error = ''
    if request.method == 'POST':
        # Per-user windowed limit — blocks brute force across IP rotation.
        try:
            check_and_consume(
                key=f'mfa_challenge:{user_id}',
                max_per_window=_CHALLENGE_MAX_ATTEMPTS,
                window_seconds=_CHALLENGE_WINDOW_SECONDS,
            )
        except RateLimitExceeded as e:
            services.audit(
                'mfa.challenge_locked', actor=device.user, request=request, severity='warning'
            )
            resp = render(
                request,
                'staff_mfa/challenge.html',
                {'error': 'Too many attempts. Try again in 15 minutes.'},
            )
            resp.status_code = 429
            resp['Retry-After'] = str(e.retry_after)
            return resp

        code = (request.POST.get('code') or '').strip()
        ok = services.verify_totp(device.secret, code) or services.consume_recovery_code(
            device, code
        )
        if ok:
            device.last_used_at = timezone.now()
            device.save(update_fields=['last_used_at'])
            user = get_user_model().objects.get(pk=user_id)
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            request.session.pop('mfa_pending_user_id', None)
            request.session.pop('mfa_next', None)
            services.audit('mfa.challenge_passed', actor=user, request=request)
            return redirect(nxt)

        error = "That code didn't work. Enter the 6-digit code from your authenticator app, or a recovery code."
        services.audit(
            'mfa.challenge_failed', actor=device.user, request=request, severity='warning'
        )

    return render(request, 'staff_mfa/challenge.html', {'error': error})


@staff_required
@csrf_protect
@require_http_methods(['GET', 'POST'])
def enroll(request):
    """Self-service enrollment / management for the signed-in staff user."""
    from plugins.installed.staff_mfa.models import StaffMfaDevice
    from plugins.registry import plugin_registry

    user = request.user
    device = StaffMfaDevice.objects.filter(user=user).first()
    plugin = plugin_registry.get('staff_mfa')
    issuer = plugin.get_config_value('issuer', 'Morpheus') if plugin else 'Morpheus'

    recovery_codes: list[str] = []
    error = ''

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'disable':
            if device is not None:
                device.delete()
                services.audit('mfa.disabled_self', actor=user, request=request)
            return redirect(request.path)

        if action == 'confirm':
            if device is None or device.is_confirmed:
                # Nothing pending to confirm — re-render current state.
                return redirect(request.path)
            # Throttle confirm attempts too, so the enroll page can't be used
            # as an unbounded TOTP oracle against a pending secret.
            try:
                check_and_consume(
                    key=f'mfa_enroll_confirm:{user.pk}',
                    max_per_window=_CHALLENGE_MAX_ATTEMPTS,
                    window_seconds=_CHALLENGE_WINDOW_SECONDS,
                )
            except RateLimitExceeded:
                error = 'Too many attempts. Try again in 15 minutes.'
            else:
                if services.verify_totp(device.secret, request.POST.get('code', '')):
                    device.confirmed_at = timezone.now()
                    device.save(update_fields=['confirmed_at'])
                    recovery_codes = services.generate_recovery_codes(device)
                    services.audit('mfa.enrolled', actor=user, request=request)
                else:
                    error = "That code didn't verify. Make sure your device clock is correct and try again."

    # Re-read after any mutation above.
    device = StaffMfaDevice.objects.filter(user=user).first()
    confirmed = device is not None and device.is_confirmed

    ctx = {
        'confirmed': confirmed,
        'error': error,
        'recovery_codes': recovery_codes,
    }

    if not confirmed:
        # Ensure a pending (unconfirmed) device with a fresh secret exists.
        if device is None or device.is_confirmed:
            device = StaffMfaDevice.objects.create(user=user, secret=services.new_secret())
        account = getattr(user, 'email', '') or getattr(user, 'username', '') or str(user.pk)
        uri = services.provisioning_uri(device.secret, account=account, issuer=issuer)
        ctx['secret'] = device.secret
        ctx['qr_svg'] = mark_safe(services.qr_svg(uri))  # noqa: S308 — our own SVG, no user input

    return render(request, 'staff_mfa/enroll.html', ctx)
