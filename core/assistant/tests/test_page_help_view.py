import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()
OK = {'ok': True, 'summary': 'Hi', 'numbers': [], 'actions': ['do x'], 'message': ''}


class PageHelpViewTests(TestCase):
    def setUp(self):
        self.url = reverse('assistant:page_help')

    def _post(self):
        return self.client.post(
            self.url,
            data=json.dumps(
                {'page_title': 'Orders', 'page_url': '/dashboard/orders/', 'page_text': 'x' * 60}
            ),
            content_type='application/json',
        )

    def test_anonymous_blocked(self):
        self.assertIn(self._post().status_code, (302, 403))

    def test_authed_non_staff_blocked(self):
        bob = User.objects.create_user('bob@test.example', 'bob', password='p')
        self.client.force_login(bob)
        self.assertIn(self._post().status_code, (302, 403))

    @patch('core.assistant.views.build_page_help', return_value=OK)
    def test_staff_allowed(self, _m):
        amy = User.objects.create_user('amy@test.example', 'amy', password='p', is_staff=True)
        self.client.force_login(amy)
        r = self._post()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])

    @patch('core.assistant.views.build_page_help', side_effect=RuntimeError('boom'))
    def test_returns_json_on_error(self, _m):
        amy2 = User.objects.create_user('amy2@test.example', 'amy2', password='p', is_staff=True)
        self.client.force_login(amy2)
        r = self._post()
        self.assertEqual(r.status_code, 200)  # JSON contract: never 500
        self.assertFalse(r.json()['ok'])
