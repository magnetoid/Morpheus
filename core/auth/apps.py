"""
core.auth — passwordless email OTP login.

A small parallel auth path next to django-allauth's password flow.
The merchant clicks "Email me a code instead", types their email,
gets a 6-digit code, types it back in, and is logged in. No
passwords needed — handy for first-time customers, mobile shoppers,
and anyone who's already locked out of an old account.

Why it lives in core, not a plugin:
  * It's a primitive: any plugin (B2B invites, agent-driven
    account recovery, sensitive-action confirmation) wants
    `issue_otp(email) -> code` and `consume_otp(email, code) -> User|None`
    without depending on a plugin that might be disabled.
  * It hooks into the same `AUTH_USER_MODEL` everything else uses.

Storage: one model `EmailOTP` with hashed code, expiry, and
single-use flag. Codes are 6 digits, expire after 10 minutes,
and self-clean on consume.
"""

from django.apps import AppConfig


class CoreAuthConfig(AppConfig):
    name = 'core.auth'
    label = 'core_auth'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        # Every sign-in route ends in login(), which sends user_logged_in.
        from django.contrib.auth.signals import user_logged_in

        from core.auth.sign_ins import record_sign_in

        user_logged_in.connect(record_sign_in, dispatch_uid='core.auth.record_sign_in')
