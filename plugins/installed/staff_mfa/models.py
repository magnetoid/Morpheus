"""Staff MFA persistence — one TOTP device per staff user + recovery codes.

`StaffMfaDevice.secret` is the base32 TOTP seed. It is stored server-side
only: the plugin exposes no agent tool over these models, so the secret is
never serialized to the assistant, the public API, logs, or webhooks. The
platform has no field-encryption helper yet (secrets live plaintext in
`PluginConfig` today), so this matches the existing secret posture; at-rest
encryption of the seed is a documented follow-up, not invented here.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class StaffMfaDevice(models.Model):
    """A staff user's enrolled TOTP authenticator (confirmed once a code verifies)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='staff_mfa_device',
    )
    secret = models.CharField(max_length=64)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'staff MFA device'
        verbose_name_plural = 'staff MFA devices'

    def __str__(self) -> str:
        return f'MFA[user={self.user_id}] {"confirmed" if self.confirmed_at else "pending"}'

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None


class MfaRecoveryCode(models.Model):
    """One single-use recovery code, stored as a SHA-256 hash of a high-entropy token."""

    device = models.ForeignKey(
        StaffMfaDevice,
        on_delete=models.CASCADE,
        related_name='recovery_codes',
    )
    code_hash = models.CharField(max_length=64)  # sha256 hex
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f'recovery[{self.device_id}] {"used" if self.used_at else "unused"}'

    @property
    def is_used(self) -> bool:
        return self.used_at is not None
