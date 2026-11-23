"""C2 — the merchant writes, schedules, cancels and sends a campaign on the dashboard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from django.contrib.auth import get_user_model
from django.template.loader import get_template
from django.test import TestCase
from django.utils import timezone

from plugins.installed.marketing.models import EmailCampaign

User = get_user_model()
BASE = '/dashboard/newsletter/campaigns/'


def _campaign(**kw):
    defaults = {'name': 'Picks', 'subject': 'Five picks', 'html_body': '<p>Hi</p>'}
    defaults.update(kw)
    return EmailCampaign.objects.create(**defaults)


def _post(**kw):
    data = {
        'name': 'December',
        'subject': 'Gifts',
        'preview_text': 'Our picks',
        'html_body': '<p>Hi</p><script>x</script>',
        'audience': 'loyal',
        'action': 'save',
    }
    data.update(kw)
    return data


class ComposerTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('boss', 'boss@example.com', 'x')
        self.client.force_login(self.admin)

    def test_templates_compile(self):
        get_template('newsletter/dashboard/campaign_edit.html')
        get_template('newsletter/dashboard/campaigns.html')

    def test_new_campaign_page_renders(self):
        response = self.client.get(f'{BASE}new/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="html_body"')
        self.assertContains(response, 'value="loyal"')

    def test_saving_creates_a_sanitised_draft(self):
        self.client.post(f'{BASE}new/', _post())
        c = EmailCampaign.objects.get()
        self.assertEqual((c.status, c.audience, c.preview_text), ('draft', 'loyal', 'Our picks'))
        self.assertNotIn('<script', c.html_body)

    def test_missing_subject_is_refused_and_the_form_keeps_the_text(self):
        response = self.client.post(f'{BASE}new/', _post(subject=''))
        self.assertFalse(EmailCampaign.objects.exists())
        self.assertContains(response, 'Name, subject and body are required.')
        self.assertContains(response, 'value="December"')

    def test_editing_a_draft(self):
        c = _campaign()
        self.client.post(f'{BASE}{c.id}/', _post(subject='New subject'))
        c.refresh_from_db()
        self.assertEqual(c.subject, 'New subject')

    def test_schedule_in_store_time_zone(self):
        from core.models import StoreSettings

        StoreSettings.objects.create(timezone='Europe/Belgrade')
        self.client.post(f'{BASE}new/', _post(action='schedule', send_at='2099-12-01T10:00'))
        c = EmailCampaign.objects.get()
        self.assertEqual(c.status, 'scheduled')
        self.assertEqual(c.scheduled_at, datetime(2099, 12, 1, 9, 0, tzinfo=UTC))

    def test_schedule_in_the_past_is_refused(self):
        response = self.client.post(
            f'{BASE}new/', _post(action='schedule', send_at='2001-01-01T10:00')
        )
        self.assertContains(response, 'Pick a time in the future.')
        self.assertFalse(EmailCampaign.objects.filter(status='scheduled').exists())

    def test_editing_a_sent_campaign_is_refused(self):
        c = _campaign(status='sent')
        self.client.post(f'{BASE}{c.id}/', _post(subject='Changed'), follow=True)
        c.refresh_from_db()
        self.assertEqual(c.subject, 'Five picks')

    def test_cancel_schedule(self):
        c = _campaign(status='scheduled', scheduled_at=timezone.now() + timedelta(days=1))
        self.client.post(f'{BASE}{c.id}/cancel/')
        c.refresh_from_db()
        self.assertEqual((c.status, c.scheduled_at), ('draft', None))

    def test_send_now_from_the_list(self):
        from plugins.installed.newsletter.models import NewsletterSubscriber

        NewsletterSubscriber.objects.create(email='r@example.com', status='confirmed')
        c = _campaign()
        with self.settings(
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
            DEFAULT_FROM_EMAIL='shop@example.com',
        ):
            self.client.post(f'{BASE}{c.id}/send/')
        c.refresh_from_db()
        self.assertEqual(c.status, 'sent')

    def test_list_shows_missed_campaigns_and_audience(self):
        _campaign(name='Late', scheduled_at=timezone.now() - timedelta(days=2), audience='lost')
        response = self.client.get(BASE)
        self.assertContains(response, 'missed its send time')
        self.assertContains(response, 'Lost')
        self.assertContains(response, f'{BASE}new/')


class ComposerPermissionTests(TestCase):
    def setUp(self):
        from plugins.installed.rbac.models import Role
        from plugins.registry import app_registry

        Role.ensure_system_roles()
        rbac = app_registry.get('rbac')
        rbac.set_config('enforcement_mode', 'enforce')
        self.addCleanup(rbac.invalidate_config_cache)
        self.addCleanup(rbac.set_config, 'enforcement_mode', 'log')
        self.c = _campaign(status='scheduled', scheduled_at=timezone.now() + timedelta(days=1))

    def _urls(self):
        return [
            f'{BASE}new/',
            f'{BASE}{self.c.id}/',
            f'{BASE}{self.c.id}/send/',
            f'{BASE}{self.c.id}/test/',
            f'{BASE}{self.c.id}/schedule/',
            f'{BASE}{self.c.id}/cancel/',
        ]

    def test_anonymous_is_sent_to_sign_in(self):
        for url in self._urls():
            response = self.client.post(url, _post())
            self.assertEqual(response.status_code, 302, url)
            self.assertIn('login', response['Location'], url)
        self.assertEqual(EmailCampaign.objects.count(), 1)

    def test_staff_without_marketing_write_is_refused(self):
        staff = User.objects.create_user(
            username='no-role', email='no-role@example.com', password='x', is_staff=True
        )
        self.client.force_login(staff)
        for url in self._urls():
            self.assertEqual(self.client.post(url, _post()).status_code, 403, url)
        self.c.refresh_from_db()
        self.assertEqual(self.c.status, 'scheduled')
        self.assertEqual(EmailCampaign.objects.count(), 1)
