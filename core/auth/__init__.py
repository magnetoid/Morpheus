"""Passwordless authentication primitives.

Provides email-OTP login as a parallel path next to allauth's
password-based flow. Apart from the views, the rest is pure helpers
plugins can call when they need to issue a one-time code (e.g.
account-recovery, sensitive-action confirmation, B2B invite link).
"""
from core.auth.services import consume_otp, issue_otp  # noqa: F401
