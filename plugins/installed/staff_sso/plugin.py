"""Staff SSO — federated staff sign-in (OIDC) over the installed allauth.

A thin config+glue plugin: it enables allauth's ``openid_connect`` provider
from a dashboard settings panel, JIT-provisions a ``customers.Customer`` from
the IdP assertion, staff-gates (email-domain allowlist / optional group claim),
and — critically — runs the *same* staff-MFA second factor the email-OTP path
runs, so an SSO login can't bypass TOTP.

OFF by default. Disable it → the SocialApp is removed, no provider button
renders, ``SOCIALACCOUNT_ADAPTER`` reverts to allauth's default, and staff
sign-in is exactly the email-OTP flow it was before (disable-test clean).
"""

from __future__ import annotations

import logging

from morpheus import Plugin, SettingsPanel, StorefrontBlock

logger = logging.getLogger('morpheus.staff_sso')

# Dotted path to our adapter; set as SOCIALACCOUNT_ADAPTER only while enabled.
_ADAPTER = 'plugins.installed.staff_sso.adapters.StaffSsoAdapter'
# allauth's stock adapter — restored on disable so the "disabling reverts the
# adapter" claim in the docstrings is actually true.
_DEFAULT_ADAPTER = 'allauth.socialaccount.adapter.DefaultSocialAccountAdapter'


class StaffSsoPlugin(Plugin):
    name = 'staff_sso'
    label = 'Staff SSO (OIDC)'
    version = '1.0.0'
    description = (
        'Federated staff sign-in via your OIDC identity provider (Okta, '
        'Entra, Google Workspace). JIT-provisions a staff account on first '
        'login, staff-gates by email domain or group claim, and honours the '
        'staff MFA second factor — no SSO bypass.'
    )
    enabled_by_default = False
    has_models = False
    # staff_mfa is a soft dependency: declaring it in requires would block boot
    # when MFA is off, but the MFA gate degrades gracefully (skipped if absent),
    # so we depend only on customers + the audit log here.
    requires = ['customers', 'core.audit']

    def ready(self) -> None:
        from django.conf import settings

        from plugins.installed.staff_sso import services

        cfg = services.get_settings(self)

        # Wire our adapter so JIT/gating/MFA logic runs on the SSO path. Only
        # while enabled — disabling restores allauth's DefaultSocialAccountAdapter.
        settings.SOCIALACCOUNT_ADAPTER = _ADAPTER

        # Mirror the saved config into an allauth SocialApp (or remove it when
        # blank). Safe + idempotent; swallows DB-not-ready at boot (migrations).
        try:
            services.sync_social_app(cfg)
        except Exception as exc:  # noqa: BLE001 — never block boot on provider sync
            logger.warning('staff_sso: provider sync skipped (%s)', exc)

    def on_disable(self) -> None:
        """Tear down the provider AND restore allauth's default adapter so
        login reverts to email-OTP immediately."""
        from django.conf import settings

        from plugins.installed.staff_sso import services

        # Revert SOCIALACCOUNT_ADAPTER so our staff-gate/MFA logic stops running.
        settings.SOCIALACCOUNT_ADAPTER = _DEFAULT_ADAPTER

        try:
            services.sync_social_app({})  # blank config → SocialApp removed
        except Exception as exc:  # noqa: BLE001
            logger.warning('staff_sso: provider teardown skipped (%s)', exc)

    def contribute_storefront_blocks(self) -> list:
        # An "Sign in with SSO" button on the staff sign-in pages. The button
        # template self-gates on enabled+configured via the {% staff_sso_login_url %}
        # tag, so it renders nothing until an IdP is wired up — and disappears
        # entirely when the plugin is disabled (the slot stops being rendered).
        return [
            StorefrontBlock(
                slot='auth_login_extra',
                template='staff_sso/blocks/login_button.html',
                priority=10,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Staff SSO (OIDC)',
            description='Sign staff in through your OIDC identity provider.',
            category='developer',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'oidc_issuer': {
                    'type': 'string',
                    'default': '',
                    'title': 'OIDC issuer / discovery URL',
                    'description': (
                        'The provider .well-known/openid-configuration URL '
                        '(or issuer base — e.g. https://acme.okta.com).'
                    ),
                },
                'oidc_client_id': {
                    'type': 'string',
                    'default': '',
                    'title': 'Client ID',
                },
                'oidc_client_secret': {
                    'type': 'string',
                    'default': '',
                    'format': 'password',
                    'title': 'Client secret',
                    'description': 'Stored server-side and redacted from the assistant.',
                },
                'oidc_scopes': {
                    'type': 'string',
                    'default': 'openid email profile',
                    'title': 'Scopes',
                },
                'allowed_domains': {
                    'type': 'string',
                    'default': '',
                    'title': 'Allowed email domains',
                    'description': 'Comma-separated, e.g. acme.com, acme.co.uk. Gates who may sign in.',
                },
                'staff_groups': {
                    'type': 'string',
                    'default': '',
                    'title': 'Staff group claims (optional)',
                    'description': (
                        'Comma-separated IdP group/role names. A user whose '
                        'groups claim intersects this list is admitted even if '
                        'their domain is not allowlisted.'
                    ),
                },
            },
        }
