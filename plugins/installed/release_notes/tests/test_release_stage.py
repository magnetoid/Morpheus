"""Morpheus is marked beta beside its version, never inside it (owner, 2026-11-01).

The version stays vX.Y.Z because the release command, the deploy guard and the update
checks parse nothing else. The stage shows in the sidebar and on Version & updates, and
the release workflow puts it in the GitHub Release title, never as GitHub's pre-release
flag: /releases/latest skips pre-releases, and every store's update check reads it.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings


class ReleaseStageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.boss = get_user_model().objects.create_user(
            username='stage',
            email='stage@example.test',
            password='pw',
            is_staff=True,
            is_superuser=True,
        )

    def setUp(self):
        self.client.force_login(self.boss)

    def _stages(self, url: str) -> int:
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, url)
        return resp.content.decode().count('data-release-stage')

    @override_settings(MORPHEUS_RELEASE_STAGE='beta')
    def test_the_dashboard_says_beta(self):
        self.assertEqual(self._stages('/dashboard/'), 1)
        self.assertEqual(self._stages('/dashboard/apps/release_notes/version/'), 2)

    @override_settings(MORPHEUS_RELEASE_STAGE='')
    def test_a_finalized_release_says_nothing(self):
        self.assertEqual(self._stages('/dashboard/apps/release_notes/version/'), 0)


class ReleaseWorkflowTests(TestCase):
    def test_the_workflow_reads_the_stage_as_settings_writes_it(self):
        root = Path(settings.BASE_DIR)
        workflow = (root / '.github' / 'workflows' / 'release.yml').read_text()
        self.assertIn('MORPHEUS_RELEASE_STAGE', workflow)
        self.assertNotIn('--prerelease', workflow)
        line = re.search(
            r"^MORPHEUS_RELEASE_STAGE = '([a-z]*)'$",
            (root / 'morph' / 'settings.py').read_text(),
            re.MULTILINE,
        )
        self.assertIsNotNone(line, 'the workflow greps this exact line')
        self.assertEqual(line.group(1), settings.MORPHEUS_RELEASE_STAGE)
