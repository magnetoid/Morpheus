"""Newsletter dashboard (subscribers + popup CRUD) + the storefront popup tag."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from plugins.installed.newsletter.models import NewsletterSubscriber, SignupPopup
from plugins.installed.newsletter.templatetags.newsletter_tags import active_signup_popup


def _staff(c):
    c.force_login(
        get_user_model().objects.create_user(
            username='m', email='m@x.test', password='pw', is_staff=True
        )
    )
    return c


class SubscribersDashboardTests(TestCase):
    def test_anonymous_redirected(self):
        self.assertEqual(Client().get('/dashboard/newsletter/').status_code, 302)

    def test_staff_sees_list_with_counts(self):
        NewsletterSubscriber.objects.create(email='a@x.test', status='confirmed')
        NewsletterSubscriber.objects.create(email='b@x.test', status='pending')
        r = _staff(Client()).get('/dashboard/newsletter/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'a@x.test')

    def test_csv_export(self):
        NewsletterSubscriber.objects.create(email='c@x.test', status='confirmed')
        r = _staff(Client()).get('/dashboard/newsletter/?export=csv')
        self.assertEqual(r['Content-Type'], 'text/csv')
        self.assertIn(b'c@x.test', r.content)


class PopupCrudTests(TestCase):
    def test_create_toggle_delete(self):
        c = _staff(Client())
        c.post('/dashboard/newsletter/popups/', {'action': 'create', 'name': 'Welcome'})
        popup = SignupPopup.objects.get(name='Welcome')
        self.assertFalse(popup.enabled)

        c.post('/dashboard/newsletter/popups/', {'action': 'toggle', 'popup_id': str(popup.id)})
        popup.refresh_from_db()
        self.assertTrue(popup.enabled)

        c.post('/dashboard/newsletter/popups/', {'action': 'delete', 'popup_id': str(popup.id)})
        self.assertFalse(SignupPopup.objects.filter(id=popup.id).exists())

    def test_edit_updates_fields(self):
        c = _staff(Client())
        popup = SignupPopup.objects.create(name='P')
        c.post(
            f'/dashboard/newsletter/popups/{popup.id}/',
            {
                'name': 'P2',
                'headline': 'Hi',
                'trigger': 'exit_intent',
                'trigger_value': '50',
                'frequency': 'daily',
                'audience': 'new',
                'button_label': 'Go',
                'success_message': 'Yay',
                'enabled': 'on',
            },
        )
        popup.refresh_from_db()
        self.assertEqual(popup.name, 'P2')
        self.assertEqual(popup.trigger, 'exit_intent')
        self.assertTrue(popup.enabled)


class PopupTagTests(TestCase):
    def test_returns_enabled_popup(self):
        SignupPopup.objects.create(name='off', enabled=False)
        live = SignupPopup.objects.create(name='on', enabled=True)
        self.assertEqual(active_signup_popup(), live)

    def test_none_when_no_enabled_popup(self):
        SignupPopup.objects.create(name='off', enabled=False)
        self.assertIsNone(active_signup_popup())
