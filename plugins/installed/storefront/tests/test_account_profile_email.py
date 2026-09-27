"""Changing the profile email to one another account holds must not 500.

`Customer.email` is unique. `account_profile` lower-cased the submitted email
and saved it straight onto the user, so a shopper who typed an address that is
already registered (their other account, a partner's) got an IntegrityError —
a server error page — instead of a message, and lost the name change they made
in the same form.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase


class ProfileEmailTakenTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.me = User.objects.create_user(
            username='me@example.com', email='me@example.com', password='pw-12345!'
        )
        User.objects.create_user(
            username='taken@example.com', email='taken@example.com', password='pw-12345!'
        )
        self.client.force_login(self.me)

    def test_email_owned_by_another_account_is_refused_not_a_server_error(self):
        resp = self.client.post(
            '/account/profile/',
            {'first_name': 'Mara', 'last_name': 'Ivic', 'email': 'Taken@Example.com'},
        )
        self.assertEqual(resp.status_code, 302)
        self.me.refresh_from_db()
        self.assertEqual(self.me.email, 'me@example.com')
        self.assertEqual(self.me.first_name, 'Mara')

    def test_a_free_email_still_changes(self):
        self.client.post(
            '/account/profile/',
            {'first_name': 'Mara', 'last_name': 'Ivic', 'email': 'New@Example.com'},
        )
        self.me.refresh_from_db()
        self.assertEqual(self.me.email, 'new@example.com')
