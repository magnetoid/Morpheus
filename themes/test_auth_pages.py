"""Sign-in pages belong to the store (v0.80.0).

On every store whose theme had not copied each auth template (only montenegro
had), `/auth/login/` was a standalone page titled "Sign in · Morpheus" with the
platform's name where the store's logo belongs — the first thing a returning
customer saw. The shared frame now renders inside the active theme.
"""

from __future__ import annotations

import re

from django.test import TestCase

from themes.test_head_contract import _activate_theme, _contract_themes

_TITLE = re.compile(r'<title[^>]*>(.*?)</title>', re.S)


class AuthPagesInTheStoreFrameTests(TestCase):
    def test_sign_in_renders_in_every_themes_own_frame(self):
        checked = []
        for name in _contract_themes():
            _activate_theme(self, name)
            for path, title in (('/auth/login/', 'Sign in'), ('/auth/otp/', 'Sign in with a code')):
                with self.subTest(theme=name, path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    body = response.content.decode()
                    self.assertNotIn('· Morpheus', body)
                    page_title = _TITLE.search(body).group(1)
                    self.assertTrue(page_title.startswith(title), page_title)
                    # The theme's own document, not a standalone frame.
                    self.assertIn('<main', body)
                    self.assertEqual(body.count('<title'), 1)
            checked.append(name)
        self.assertGreater(len(checked), 1)

    def test_allauths_own_pages_are_framed_too(self):
        _activate_theme(self, 'dot_books')
        response = self.client.get('/auth/password/reset/done/')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('<main', body)
        self.assertNotIn('<strong>Menu:</strong>', body)  # allauth's stock layout
