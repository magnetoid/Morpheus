"""``StaffSsoAdapter`` — JIT provisioning, staff-gating, and the MFA no-bypass.

allauth completes a social login by calling ``login()`` directly; it never
passes through ``core/auth/otp_verify``, so it would skip the staff TOTP second
factor. This adapter interposes the *same* MFA decision the email-OTP path runs
(``staff_mfa.services.second_factor_response``) inside ``pre_social_login`` —
one decision point, identical for both sign-in paths.

The adapter is only wired in (``SOCIALACCOUNT_ADAPTER``) while the plugin is
enabled; disabling it reverts allauth to its default and login is email-OTP.
"""

from __future__ import annotations

import logging

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.shortcuts import render
from django.utils import timezone

from plugins.installed.staff_sso import services

logger = logging.getLogger('morpheus.staff_sso')


def _get_plugin():
    """Resolve the live staff_sso plugin instance, or None when not active."""
    from plugins.registry import plugin_registry

    if not plugin_registry.is_active('staff_sso'):
        return None
    return plugin_registry.get('staff_sso')


def _verified_email(sociallogin) -> str:
    """The IdP-asserted email, only if the assertion marks it verified.

    Account-takeover guard: never trust an unverified claim to link to (or
    create) an account. Returns '' when no verified email is present.
    """
    for addr in sociallogin.email_addresses or []:
        if getattr(addr, 'verified', False) and getattr(addr, 'email', ''):
            return addr.email.strip().lower()
    return ''


def _claims(sociallogin) -> dict:
    account = getattr(sociallogin, 'account', None)
    return getattr(account, 'extra_data', {}) or {}


def _user_in_db(user) -> bool:
    """True iff ``user`` is a saved row. Customer.id defaults to uuid4 at
    instantiation, so an unsaved user has a non-None ``.pk``; only a DB lookup
    distinguishes 'already linked' from 'about to be JIT-created'."""
    if user is None or getattr(user, 'pk', None) is None:
        return False
    return type(user).objects.filter(pk=user.pk).exists()


def _deny(request, message: str):
    """Render an access-denied page and raise it so allauth aborts the login —
    no account is created and no session is established."""
    resp = render(request, 'staff_sso/access_denied.html', {'message': message}, status=403)
    raise ImmediateHttpResponse(resp)


class StaffSsoAdapter(DefaultSocialAccountAdapter):
    """The process-wide ``SOCIALACCOUNT_ADAPTER`` while staff_sso is enabled.

    Because it is global, it must act ONLY on its own OIDC provider — every
    other (future, customer-facing) social provider passes through untouched
    (no staff gate, no MFA interception).
    """

    def pre_social_login(self, request, sociallogin):
        """Run after the IdP assertion validates, before allauth's ``login()``.

        Order matters: verified-email guard → staff gate → link existing
        Customer → MFA gate. The MFA gate runs LAST, with the resolved user, so
        an enrolled staffer is forced through TOTP before the session exists.
        """
        # Global adapter: only staff-gate / MFA-intercept our own provider.
        if getattr(sociallogin.account, 'provider', '') != services.PROVIDER_ID:
            return super().pre_social_login(request, sociallogin)

        plugin = _get_plugin()
        if plugin is None:
            return  # plugin disabled mid-flow → behave like default allauth

        cfg = services.get_settings(plugin)
        email = _verified_email(sociallogin)

        # Account-takeover guard — refuse to proceed on an unverified email.
        if not email:
            services.audit(
                'sso.gate_reject',
                target='(unverified)',
                metadata={'reason': 'unverified_email'},
                severity='warning',
            )
            _deny(request, 'Your identity provider did not assert a verified email address.')

        # Staff gate — domain allowlist OR group-claim intersection.
        groups = services.claim_groups(_claims(sociallogin))
        if not services.gate_decision(cfg, email=email, groups=groups):
            services.audit(
                'sso.gate_reject',
                target=email,
                metadata={'reason': 'not_staff', 'domain': email.partition('@')[2]},
                severity='warning',
            )
            _deny(request, 'This account is not permitted to sign in here.')

        # Link to an existing Customer by verified email (JIT-link). If absent,
        # allauth proceeds to populate_user()/save_user() for a JIT-create.
        user = self._link_existing(request, sociallogin, email)

        # MFA no-bypass (the headline). Resolve staff_mfa via the registry and
        # run the SAME second-factor decision the email-OTP path runs. If it
        # returns a redirect to the TOTP challenge, raise it so allauth does NOT
        # complete login(); the staff_mfa challenge view logs the user in after
        # TOTP. Skipped cleanly when staff_mfa is disabled/absent. Only a
        # DB-resident user can have a confirmed device, so gate on that.
        if _user_in_db(user):
            response = self._mfa_gate(request, user)
            if response is not None:
                raise ImmediateHttpResponse(response)

    def _link_existing(self, request, sociallogin, email):
        """If a Customer already exists for this verified email, connect the
        SocialAccount to it so allauth links instead of creating a duplicate.

        The gate already passed upstream, so a matched user is staff: promote a
        non-staff Customer to ``is_staff`` here (``populate_user`` only runs on
        the JIT-create path, so a linked customer-account user would otherwise
        never gain dashboard access). We use allauth's documented
        ``sociallogin.connect(request, existing)`` — the canonical
        ``pre_social_login`` "user already exists" linking call — rather than
        only assigning ``sociallogin.user``.

        NB: Customer.id defaults to ``uuid4`` at instantiation, so an *unsaved*
        user already has a non-None ``.pk`` — we must check DB existence, not
        truthiness of ``.pk`` (allauth's own ``SocialLogin.is_existing`` does
        the same), or we'd skip linking and create a duplicate account."""
        if _user_in_db(sociallogin.user):
            return sociallogin.user

        from plugins.installed.customers.models import Customer

        existing = Customer.objects.filter(email__iexact=email).first()
        if existing is not None:
            if not existing.is_staff:
                existing.is_staff = True
                existing.save(update_fields=['is_staff'])
            sociallogin.connect(request, existing)
            services.audit('sso.login', actor=existing, target=email, metadata={'linked': True})
        return existing

    @staticmethod
    def _mfa_gate(request, user):
        """Delegate to staff_mfa's single decision point, if it's active."""
        from plugins.registry import plugin_registry

        if not plugin_registry.is_active('staff_mfa'):
            return None
        mfa = plugin_registry.get('staff_mfa')
        if mfa is None:
            return None
        from plugins.installed.staff_mfa.services import second_factor_response

        nxt = (request.GET.get('next') if request else '') or '/dashboard/'
        return second_factor_response(mfa, request, user, nxt)

    def populate_user(self, request, sociallogin, data):
        """Map IdP claims → Customer on a JIT-create, stamp SSO provenance, and
        set is_staff for a gated-in user (the gate already ran in
        pre_social_login, so reaching here means the identity passed)."""
        user = super().populate_user(request, sociallogin, data)

        email = _verified_email(sociallogin)
        if email:
            user.email = email
        # Gate passed upstream → this is staff.
        user.is_staff = True

        account = getattr(sociallogin, 'account', None)
        meta = dict(getattr(user, 'metadata', {}) or {})
        meta['sso'] = {
            'provider': getattr(account, 'provider', services.PROVIDER),
            'idp_sub': getattr(account, 'uid', '') or (data or {}).get('sub', ''),
            'at': timezone.now().isoformat(),
        }
        user.metadata = meta
        user.source = 'manual'

        services.audit('sso.jit_create', target=email or user.email, metadata={'is_staff': True})
        return user
