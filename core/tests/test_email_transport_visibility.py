"""A store that cannot send email must be told so.

`MorpheusEmailBackend` falls back to the console backend when no SMTP host is
configured, which in production means every sign-in code, order confirmation
and newsletter confirmation is printed to the log and never delivered — two of
the three live stores ran that way unnoticed. The dashboard's setup step
"Set a sending email" reported done whenever DEFAULT_FROM_EMAIL was set, and
that setting always has a default, so the checklist said email worked.
"""

from __future__ import annotations

from django.test import TestCase, override_settings

from core.models import StoreSettings


def _email_step() -> dict:
    from plugins.installed.admin_dashboard.views_split.home import _compute_setup_steps

    return next(s for s in _compute_setup_steps() if s['key'] == 'email')


@override_settings(EMAIL_HOST='', DEFAULT_FROM_EMAIL='noreply@example.com')
class EmailTransportVisibilityTests(TestCase):
    def test_setup_step_is_open_until_an_smtp_server_is_configured(self):
        self.assertFalse(_email_step()['done'])

        settings_row = StoreSettings.objects.first() or StoreSettings.objects.create()
        settings_row.smtp_host = 'smtp.example.com'
        settings_row.save()
        self.assertTrue(_email_step()['done'])

    def test_setup_step_points_at_the_smtp_settings(self):
        self.assertEqual(_email_step()['url'], '/dashboard/settings/notifications/')

    @override_settings(DEBUG=False)
    def test_an_undeliverable_send_is_logged(self):
        from core.email import MorpheusEmailBackend

        with self.assertLogs('morpheus.email', level='WARNING') as logs:
            MorpheusEmailBackend()
        self.assertIn('not delivered', ' '.join(logs.output))
