"""Feedback ticket guards."""

from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.installed.feedback.models import FeedbackTicket

SUBMIT = '/dashboard/apps/feedback/tickets/submit/'
LIST = '/dashboard/apps/feedback/tickets/'

# 1x1 red PNG, already canonical base64.
PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='


def _staff(email='staff@example.com'):
    User = get_user_model()
    return User.objects.create_user(username=email, email=email, password='pw-12345', is_staff=True)


class SubmitTests(TestCase):
    def setUp(self):
        self.user = _staff()

    def _post(self, **payload):
        payload.setdefault('message', 'The save button does nothing.')
        return self.client.post(SUBMIT, data=json.dumps(payload), content_type='application/json')

    def test_anonymous_cannot_submit(self):
        response = self._post()
        # Assert the REDIRECT, not merely "not 200": a routing 404 also satisfies
        # "not 200", which is exactly how the first version of this test passed
        # while the submit URL was being swallowed by the app-discovery router.
        self.assertEqual(response.status_code, 302)
        self.assertEqual(FeedbackTicket.objects.count(), 0)

    def test_staff_submits_message_only(self):
        self.client.force_login(self.user)
        response = self._post(screenshot_skipped_reason='declined', page_url='https://x.test/a/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        ticket = FeedbackTicket.objects.get()
        self.assertEqual(ticket.message, 'The save button does nothing.')
        self.assertEqual(ticket.user, self.user)
        self.assertFalse(ticket.screenshot)
        # WHY there is no image must survive — "declined" and "lost it" differ.
        self.assertEqual(ticket.screenshot_skipped_reason, 'declined')

    def test_empty_message_is_rejected(self):
        self.client.force_login(self.user)
        response = self._post(message='   ')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(FeedbackTicket.objects.count(), 0)

    def test_screenshot_is_stored(self):
        self.client.force_login(self.user)
        response = self._post(screenshot='data:image/png;base64,' + PNG)
        self.assertEqual(response.status_code, 200)
        ticket = FeedbackTicket.objects.get()
        self.assertTrue(ticket.screenshot)
        self.assertEqual(ticket.screenshot_skipped_reason, '')

    def test_garbage_screenshot_does_not_lose_the_ticket(self):
        """A broken image must not cost the report — the message is the point."""
        self.client.force_login(self.user)
        response = self._post(screenshot='data:image/png;base64,@@@not-base64@@@')
        self.assertEqual(response.status_code, 200)
        ticket = FeedbackTicket.objects.get()
        self.assertFalse(ticket.screenshot)
        self.assertEqual(ticket.screenshot_skipped_reason, 'failed')

    def test_client_errors_are_attached(self):
        self.client.force_login(self.user)
        self._post(client_errors=[{'type': 'error', 'message': 'x is not a function'}])
        ticket = FeedbackTicket.objects.get()
        self.assertEqual(ticket.client_errors[0]['message'], 'x is not a function')

    def test_console_log_is_attached_and_sanitised(self):
        self.client.force_login(self.user)
        self._post(
            console_log=[
                {'level': 'warn', 'message': 'cart total recomputed', 'ts': '2026-08-20T10:00:00Z'},
                {'level': 'x' * 99, 'message': 'y' * 9000, 'extra_key': 'dropped'},
                'not-a-dict-line',
            ]
        )
        log = FeedbackTicket.objects.get().context['console_log']
        self.assertEqual(len(log), 2)  # the non-dict line is dropped
        self.assertEqual(log[0]['message'], 'cart total recomputed')
        self.assertEqual(len(log[1]['level']), 10)  # capped
        self.assertEqual(len(log[1]['message']), 500)  # capped
        self.assertNotIn('extra_key', log[1])  # only the known keys survive


class QueueTests(TestCase):
    def setUp(self):
        self.user = _staff()
        self.ticket = FeedbackTicket.objects.create(message='Broken thing', user=self.user)

    def test_anonymous_cannot_read_the_queue(self):
        response = self.client.get(LIST)
        self.assertEqual(response.status_code, 302)

    def test_staff_sees_the_queue_and_detail(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(LIST), 'Broken thing')
        detail = self.client.get(f'/dashboard/apps/feedback/tickets/{self.ticket.pk}/')
        self.assertContains(detail, 'Broken thing')

    def test_status_can_be_updated(self):
        self.client.force_login(self.user)
        self.client.post(
            f'/dashboard/apps/feedback/tickets/{self.ticket.pk}/',
            {'status': FeedbackTicket.STATUS_CLOSED},
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, FeedbackTicket.STATUS_CLOSED)


class ContributionTests(TestCase):
    """The shell must carry the entry and the modal WITHOUT importing this app."""

    def setUp(self):
        self.client.force_login(_staff())

    def test_dropdown_entry_and_modal_render_in_the_shell(self):
        body = self.client.get('/dashboard/').content.decode()
        self.assertIn('data-feedback-open', body)
        self.assertIn('id="feedback-modal"', body)

    def test_surfaces_vanish_when_the_app_is_disabled(self):
        from plugins.registry import app_registry

        app_registry.deactivate('feedback')
        try:
            body = self.client.get('/dashboard/').content.decode()
            self.assertNotIn('data-feedback-open', body)
            self.assertNotIn('id="feedback-modal"', body)
        finally:
            app_registry.activate('feedback')
