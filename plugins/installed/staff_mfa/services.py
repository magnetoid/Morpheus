"""TOTP second-factor service layer + the AUTH_SECOND_FACTOR subscriber.

Kept thin: pyotp does the RFC-6238 math, hashlib hashes recovery codes,
and ``second_factor_response`` is the single decision point the core
``AUTH_SECOND_FACTOR`` filter calls after the email-OTP (factor one) passes.
"""

from __future__ import annotations

import hashlib
import logging
import secrets

from django.shortcuts import redirect
from django.utils import timezone

logger = logging.getLogger('morpheus.staff_mfa')

# Self-service enrollment lives at the plugin's dashboard page, mounted by the
# registry at /dashboard/apps/<plugin>/<slug>/ (slug='enroll').
ENROLL_URL = '/dashboard/apps/staff_mfa/enroll/'
_RECOVERY_CODE_COUNT = 10


# ── TOTP ─────────────────────────────────────────────────────────────────────
def new_secret() -> str:
    import pyotp

    return pyotp.random_base32()


def provisioning_uri(secret: str, *, account: str, issuer: str) -> str:
    """The otpauth:// URI an authenticator app scans to add the account."""
    import pyotp

    return pyotp.TOTP(secret).provisioning_uri(
        name=account or 'staff', issuer_name=issuer or 'Morpheus'
    )


def verify_totp(secret: str, code: str) -> bool:
    import pyotp

    digits = ''.join(ch for ch in (code or '') if ch.isdigit())
    if len(digits) != 6:
        return False
    # valid_window=1 tolerates ±30s of clock drift between server and device.
    return bool(pyotp.TOTP(secret).verify(digits, valid_window=1))


# ── Recovery codes ───────────────────────────────────────────────────────────
def _hash_code(code: str) -> str:
    return hashlib.sha256((code or '').strip().lower().encode()).hexdigest()


def generate_recovery_codes(device, *, count: int = _RECOVERY_CODE_COUNT) -> list[str]:
    """Replace any existing codes with `count` fresh ones; return the PLAINTEXT
    codes so the caller can show them exactly once (only hashes are stored)."""
    from plugins.installed.staff_mfa.models import MfaRecoveryCode

    device.recovery_codes.all().delete()
    plain = [secrets.token_hex(5) for _ in range(count)]  # 10 hex chars each
    MfaRecoveryCode.objects.bulk_create(
        [MfaRecoveryCode(device=device, code_hash=_hash_code(c)) for c in plain]
    )
    return plain


def consume_recovery_code(device, code: str) -> bool:
    """Burn one matching unused recovery code. Returns True on success."""
    from plugins.installed.staff_mfa.models import MfaRecoveryCode

    row = MfaRecoveryCode.objects.filter(
        device=device, used_at__isnull=True, code_hash=_hash_code(code)
    ).first()
    if row is None:
        return False
    row.used_at = timezone.now()
    row.save(update_fields=['used_at'])
    return True


# ── QR rendering (no extra deps: pure-SVG from qrcode's module matrix) ────────
def qr_svg(data: str, *, box: int = 5) -> str:
    """Render `data` as an inline SVG QR code (no PIL/lxml needed)."""
    import qrcode

    qr = qrcode.QRCode(border=4, box_size=box)
    qr.add_data(data)
    qr.make(fit=True)
    matrix = qr.get_matrix()  # includes the quiet-zone border
    size = len(matrix) * box
    rects = [
        f'<rect x="{c * box}" y="{r * box}" width="{box}" height="{box}"/>'
        for r, row in enumerate(matrix)
        for c, on in enumerate(row)
        if on
    ]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}" shape-rendering="crispEdges" fill="#111">'
        f'<rect width="{size}" height="{size}" fill="#fff"/>{"".join(rects)}</svg>'
    )


# ── Audit ────────────────────────────────────────────────────────────────────
def _client_ip(request) -> str | None:
    if request is None:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',', 1)[0].strip() or None
    return request.META.get('REMOTE_ADDR') or None


def audit(
    event_type: str, *, actor=None, target: str = '', request=None, metadata=None, severity='info'
):
    """Record an mfa.* audit event. Never raises (core.audit swallows DB errors)."""
    from core.audit.services import record

    record(
        event_type=event_type,
        actor=actor,
        target=target,
        metadata=metadata or {},
        severity=severity,
        ip_address=_client_ip(request),
    )


# ── The AUTH_SECOND_FACTOR decision ──────────────────────────────────────────
def second_factor_response(plugin, request, user, nxt: str):
    """Return an HttpResponse to interpose, or None to let login proceed.

    Only staff are gated. An enrolled staffer is sent to the TOTP challenge
    (hard gate — login does not complete without it). An *un*enrolled staffer
    is only forced to enrollment when the merchant set ``require_for_staff``
    AND at least one staff device already exists org-wide (first-admin grace,
    so the first admin can't lock everyone out before anyone has enrolled).
    """
    if user is None or not getattr(user, 'is_staff', False):
        return None

    from plugins.installed.staff_mfa.models import StaffMfaDevice

    device = StaffMfaDevice.objects.filter(user=user, confirmed_at__isnull=False).first()
    if device is not None:
        # str(): the user PK is a UUID and the JSON session serializer can't
        # encode a raw UUID — store the string form (as Django's own login()
        # does for _auth_user_id) so the session write doesn't 500.
        request.session['mfa_pending_user_id'] = str(user.pk)
        request.session['mfa_next'] = nxt
        request.session.pop('morph_otp_email', None)
        request.session.pop('morph_otp_next', None)
        return redirect('staff_mfa:challenge')

    require = bool(plugin.get_config_value('require_for_staff', False))
    if require and StaffMfaDevice.objects.filter(confirmed_at__isnull=False).exists():
        # Log them in so they can reach the enrollment page, then force them
        # there. (Hard per-request gating of every dashboard URL is a
        # documented Phase-B follow-up; this nudges at the login boundary.)
        from django.contrib.auth import login

        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)
        request.session.pop('morph_otp_email', None)
        request.session.pop('morph_otp_next', None)
        audit('mfa.enrollment_required', actor=user, request=request)
        return redirect(ENROLL_URL)

    return None
