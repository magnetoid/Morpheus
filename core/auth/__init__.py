"""Passwordless authentication primitives.

Provides email-OTP login as a parallel path next to allauth's
password-based flow. Apart from the views, the rest is pure helpers
plugins can call when they need to issue a one-time code (e.g.
account-recovery, sensitive-action confirmation, B2B invite link).

Callers: use ``from core.auth.services import issue_otp, consume_otp``.
We deliberately avoid re-exporting at the package level — Django's
``apps.populate()`` imports this package before the AppConfig has
registered, and pulling in ``models`` from here would raise
``AppRegistryNotReady`` during collectstatic and worker startup.
"""
