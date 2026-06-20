"""Release notes parsing + the Version & updates page."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.installed.release_notes.views import parse_releases

_SAMPLE = """# Morpheus OS — Release Notes

intro text

## v0.2.0 — 2026-07-01

### Added
- A thing
- Another thing

## v0.1.0 — 2026-06-20

First release.
"""


class ParseReleasesTests(TestCase):
    def test_splits_versions_newest_first(self):
        rel = parse_releases(_SAMPLE)
        self.assertEqual([r['version'] for r in rel], ['v0.2.0', 'v0.1.0'])
        self.assertEqual(rel[0]['date'], '2026-07-01')
        self.assertIn('<li>A thing</li>', rel[0]['html'])

    def test_empty_doc(self):
        self.assertEqual(parse_releases('# Title only\n\nno releases'), [])


class VersionPageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            username='boss', email='b@x.io', password='pw', is_staff=True
        )

    def test_page_renders_for_staff(self):
        self.client.force_login(self.staff)
        resp = self.client.get('/dashboard/apps/release_notes/version/')
        # The page resolves and renders (200) with the version chip.
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Version')

    def test_anon_blocked(self):
        resp = self.client.get('/dashboard/apps/release_notes/version/')
        self.assertIn(resp.status_code, (302, 301, 403))
