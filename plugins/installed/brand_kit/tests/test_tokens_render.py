"""A merchant's design tokens must actually reach the storefront.

The `global_head` token block shipped reading `tokens.colors.primary`, but no
view, tag or context processor ever supplied `tokens` — so every palette and
typeface a merchant configured rendered as the hardcoded default on every page.
The slot itself was wired in v0.37; this pins the data behind it.
"""

from __future__ import annotations

import json

from django.test import TestCase

from plugins.installed.brand_kit.models import DesignTokenSet
from plugins.registry import app_registry

_MARKER = 'id="morpheus-brand-tokens"'


class BrandTokenRenderTests(TestCase):
    def _head(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode().split('</head>')[0]

    def test_active_token_set_reaches_the_page(self):
        DesignTokenSet.objects.create(
            slug='holiday',
            name='Holiday',
            is_active=True,
            tokens_json=json.dumps(
                {'colors': {'primary': '#ff0055', 'accent': '#00d4aa'}, 'radii': {'base': '2px'}}
            ),
        )
        head = self._head()
        self.assertIn('#ff0055', head)
        self.assertIn('#00d4aa', head)
        self.assertIn('2px', head)
        self.assertIn('data-token-set="holiday"', head)

    def test_no_active_set_falls_back_to_defaults(self):
        head = self._head()
        self.assertIn(_MARKER, head)
        self.assertIn('#111', head)  # built-in primary

    def test_unset_group_falls_back_per_token(self):
        # Only colors authored — fonts/radii must still render their defaults.
        DesignTokenSet.objects.create(
            slug='partial',
            name='Partial',
            is_active=True,
            tokens_json=json.dumps({'colors': {'primary': '#123456'}}),
        )
        head = self._head()
        self.assertIn('#123456', head)
        self.assertIn('6px', head)  # default radius
        self.assertIn('#c8a96a', head)  # default accent

    def test_malformed_tokens_json_does_not_break_the_page(self):
        DesignTokenSet.objects.create(
            slug='broken', name='Broken', is_active=True, tokens_json='{not json'
        )
        head = self._head()  # asserts 200
        self.assertIn('#111', head)

    def test_non_dict_group_is_ignored(self):
        DesignTokenSet.objects.create(
            slug='weird', name='Weird', is_active=True, tokens_json=json.dumps({'colors': 'nope'})
        )
        self.assertIn('#111', self._head())

    def test_tokens_vanish_when_the_plugin_is_disabled(self):
        DesignTokenSet.objects.create(
            slug='x',
            name='X',
            is_active=True,
            tokens_json=json.dumps({'colors': {'primary': '#abcdef'}}),
        )
        self.assertIn('#abcdef', self._head())

        app_registry.deactivate('brand_kit')
        try:
            head = self._head()
            self.assertNotIn(_MARKER, head)
            self.assertNotIn('#abcdef', head)
        finally:
            app_registry.activate('brand_kit')
        self.assertIn('#abcdef', self._head())
