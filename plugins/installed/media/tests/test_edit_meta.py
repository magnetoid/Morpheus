"""Asset metadata editor — auth boundary + the AJAX JSON contract.

The library's inline SEO modal submits over ``fetch`` and trusts a JSON
``{ok: …}`` body. If the view ever answered an AJAX POST with an HTML
redirect, the client would read "200" and flash a false "Saved" — the
``dashboard-ajax-json-contract`` landmine. These tests pin the contract.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from plugins.installed.media.models import MediaAsset


class EditMetaTests(TestCase):
    def setUp(self):
        self.asset = MediaAsset.objects.create(
            filename='cover.jpg',
            kind='image',
            mime_type='image/jpeg',
        )
        self.url = reverse('media:edit_meta', args=[self.asset.id])

    def _staff(self, username):
        user = get_user_model().objects.create_user(
            username=username,
            email=f'{username}@example.test',
            password='pw',
        )
        user.is_staff = True
        user.save(update_fields=['is_staff'])
        return user

    def test_anonymous_post_blocked_and_no_write(self):
        resp = self.client.post(self.url, {'title': 'Hack'})
        self.assertEqual(resp.status_code, 302)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.title, '')

    def test_ajax_post_returns_json_and_persists(self):
        self.client.force_login(self._staff('editor'))
        resp = self.client.post(
            self.url,
            {
                'title': 'Hero cover',
                'alt_text': 'A book',
                'description': 'Long desc',
                'tags': 'hero, book',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/json')
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['asset']['title'], 'Hero cover')
        self.assertEqual(data['asset']['display'], 'Hero cover')
        self.assertEqual(data['asset']['tags'], ['hero', 'book'])
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.alt_text, 'A book')
        self.assertEqual(self.asset.description, 'Long desc')
        self.assertEqual(self.asset.tags, ['hero', 'book'])

    def test_non_ajax_post_redirects_to_library(self):
        self.client.force_login(self._staff('editor2'))
        resp = self.client.post(self.url, {'title': 'Plain'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], reverse('media:library'))
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.title, 'Plain')

    def test_display_falls_back_to_filename_when_title_blank(self):
        self.client.force_login(self._staff('editor3'))
        resp = self.client.post(
            self.url,
            {'title': '', 'alt_text': 'x'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.json()['asset']['display'], 'cover.jpg')
