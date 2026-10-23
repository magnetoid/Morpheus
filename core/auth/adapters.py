"""allauth's account adapter: every allauth sign-in runs the second factor.

allauth signs people in itself: email and password at /auth/login/, a code, a sign-up, a
password reset, a social login. Each goes through ``perform_login``, which asks the adapter's
``pre_login`` before anyone is logged in. Core fires ``AUTH_SECOND_FACTOR`` there, as
``otp_verify`` does after the emailed code; a second-factor app (staff_mfa) answers with its
challenge and the sign-in waits for it. If the check itself fails, nobody is logged in.
"""

from __future__ import annotations

import logging

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect

from core.hooks import MorpheusEvents, hook_registry

logger = logging.getLogger(__name__)


class AccountAdapter(DefaultAccountAdapter):
    def pre_login(self, request, user, **kwargs):
        response = super().pre_login(request, user, **kwargs)
        if response:
            return response
        try:
            return hook_registry.filter(
                MorpheusEvents.AUTH_SECOND_FACTOR,
                value=None,
                request=request,
                user=user,
                next=kwargs.get('redirect_url') or settings.LOGIN_REDIRECT_URL,
                raise_errors=True,
            )
        except Exception:
            logger.exception('sign-in: the second factor could not be resolved; login refused')
            messages.error(request, 'We could not verify your second factor. Please try again.')
            return redirect('account_login')
