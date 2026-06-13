"""AI rewrite-description endpoint."""

# ruff: noqa: PLC0415
from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase


class AiRewriteDescriptionTests(TestCase):
    URL = '/dashboard/ai/rewrite-description/'

    def setUp(self):
        u = get_user_model().objects.create_user(
            username='w', email='w@example.test', password='pw', is_staff=True
        )
        self.client.force_login(u)

    def _post(self, payload):
        return self.client.post(self.URL, data=json.dumps(payload), content_type='application/json')

    def test_rewrite_returns_text(self):
        with patch(
            'plugins.installed.admin_dashboard.views_split.ai_writers.call_llm',
            return_value=('Sharper copy.', None),
        ):
            r = self._post({'existing': 'old copy', 'name': 'A Book'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['text'], 'Sharper copy.')

    def test_empty_existing_400(self):
        r = self._post({'existing': '   '})
        self.assertEqual(r.status_code, 400)

    def test_llm_error_502(self):
        with patch(
            'plugins.installed.admin_dashboard.views_split.ai_writers.call_llm',
            return_value=('', 'provider down'),
        ):
            r = self._post({'existing': 'x'})
        self.assertEqual(r.status_code, 502)

    def test_get_rejected(self):
        self.assertEqual(self.client.get(self.URL).status_code, 405)
