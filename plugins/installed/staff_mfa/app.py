"""Staff two-factor (MFA) — a TOTP second factor for staff sign-in.

Email-OTP (``core/auth``) stays factor one. This plugin subscribes to the
``AUTH_SECOND_FACTOR`` filter and, for an enrolled staff user, interposes a
TOTP challenge before the session is established. Disable the plugin → the
filter has no subscriber → sign-in reverts to single-factor email-OTP
(disable-test clean). All MFA logic lives here; core owns only the one hook.
"""

from __future__ import annotations

from morpheus.app import DashboardPage, Plugin, SettingsPanel
from morpheus.core import events


class StaffMfaPlugin(Plugin):
    name = 'staff_mfa'
    label = 'Staff two-factor (MFA)'
    version = '1.0.0'
    description = (
        'TOTP second factor for staff sign-in. Authenticator-app enrollment '
        '(QR + confirm), one-time recovery codes, opt-in or required-for-staff '
        'enforcement, and an audited break-glass reset.'
    )
    has_models = True
    requires = ['customers', 'core.audit']

    def ready(self) -> None:
        # Public challenge URLs — reached during sign-in, before the session
        # exists, so they live at the site root, not under /dashboard/.
        self.register_urls(
            'plugins.installed.staff_mfa.urls',
            prefix='auth/mfa/',
            namespace='staff_mfa',
        )
        self.register_hook(events.AUTH_SECOND_FACTOR, self._on_second_factor, priority=50)

    def _on_second_factor(self, value=None, request=None, user=None, next=None, **_kwargs):
        """AUTH_SECOND_FACTOR filter handler. Respect an upstream response;
        otherwise delegate the staff/enrolled decision to the service layer."""
        if value is not None:
            return value
        from plugins.installed.staff_mfa.services import second_factor_response

        return second_factor_response(self, request, user, next or '/dashboard/')

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Two-factor auth',
                slug='enroll',
                view='plugins.installed.staff_mfa.views.enroll',
                icon='shield-check',
                section='team',
                order=20,
                nav='settings',
                hint='Authenticator-app sign-in for staff',
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Staff two-factor (MFA)',
            description='Require an authenticator-app code for staff sign-in.',
            category='team',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'require_for_staff': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Require MFA for all staff',
                    'description': (
                        'When on, staff without an enrolled device are sent to '
                        'enrollment at sign-in. A first-admin grace keeps the very '
                        'first admin from locking everyone out before anyone enrolls.'
                    ),
                },
                'issuer': {
                    'type': 'string',
                    'default': 'Morpheus',
                    'title': 'Issuer label',
                    'description': 'Shown in the authenticator app next to the account.',
                },
            },
        }
