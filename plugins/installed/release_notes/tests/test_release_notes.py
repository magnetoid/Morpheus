"""Release notes parsing + the Version & updates page."""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.defaultfilters import filesizeformat
from django.test import TestCase

from core.models import DeployEvent
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

    def test_page_is_the_unified_updater_plus_changelog(self):
        """The two update pages are one: the version page now also renders the
        updater (check for updates + the apply endpoints) alongside the changelog."""
        self.client.force_login(self.staff)
        with patch('core.updates.can_self_update', return_value=True):
            html = self.client.get('/dashboard/apps/release_notes/version/').content.decode()
        # Updater surface.
        self.assertIn('Morpheus core', html)
        self.assertIn('Check for updates', html)
        self.assertIn('/dashboard/updates/check/', html)  # admin_dashboard action endpoint
        self.assertIn('App &amp; theme updates', html)
        # Changelog surface.
        self.assertIn('Changelog', html)

    def test_updates_page_redirects_to_the_unified_page(self):
        """/dashboard/updates/ folds into the one page while release_notes is on."""
        self.client.force_login(self.staff)
        resp = self.client.get('/dashboard/updates/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/dashboard/apps/release_notes/version/')


class SitePageTests(TestCase):
    """About lives on the project website and opens embedded here.

    Written once on morpheus.direct for every store (owner's call, 2026-10-10);
    the dashboard frames the site's embed mode. Only these two pages may frame
    that site — the dashboard's enforced CSP frames nothing else.
    """

    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            username='boss2', email='b2@x.io', password='pw', is_staff=True
        )

    def test_about_embeds_the_website_page(self):
        self.client.force_login(self.staff)
        for slug, page in (('about', 'about.html'),):
            with self.subTest(page=slug):
                resp = self.client.get(f'/dashboard/apps/release_notes/{slug}/')
                self.assertEqual(resp.status_code, 200)
                html = resp.content.decode()
                self.assertIn('<iframe', html)
                self.assertIn(f'data-site-page="https://morpheus.direct/{page}"', html)
                self.assertIn(f'href="https://morpheus.direct/{page}"', html)
                csp = resp['Content-Security-Policy']
                self.assertIn("frame-src 'self' https://morpheus.direct", csp)
                self.assertIn("frame-ancestors 'none'", csp)

    def test_the_rest_of_the_dashboard_frames_nothing_external(self):
        self.client.force_login(self.staff)
        resp = self.client.get('/dashboard/apps/release_notes/version/')
        self.assertNotIn('morpheus.direct', resp['Content-Security-Policy'])

    def test_the_account_menu_links_help_and_about(self):
        self.client.force_login(self.staff)
        html = self.client.get('/dashboard/').content.decode()
        self.assertIn('href="/dashboard/help/"', html)
        self.assertIn('href="/dashboard/apps/release_notes/about/"', html)

    def test_anon_blocked(self):
        for slug in ('about', 'help'):
            resp = self.client.get(f'/dashboard/apps/release_notes/{slug}/')
            self.assertIn(resp.status_code, (302, 301, 403))


_NO_GIT = {
    'source': 'git',
    'available': 'unavailable',
    'reason': 'No git metadata in this deployment (built image / non-git install).',
}


class HonestUpdaterTests(TestCase):
    """Safe deploys, part 5: the page says what runs, and offers nothing that cannot work."""

    URL = '/dashboard/apps/release_notes/version/'

    def setUp(self):
        staff = get_user_model().objects.create_user(
            username='ops', email='o@x.io', password='pw', is_staff=True
        )
        self.client.force_login(staff)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.backups = Path(tmp.name)
        env = patch.dict(os.environ, {'MORPHEUS_BACKUP_DIR': tmp.name, 'SOURCE_COMMIT': 'd' * 40})
        env.start()
        self.addCleanup(env.stop)

    def page(self, *, self_update, platform=None):
        # The changelog quotes button names ("Update now", RELEASE_NOTES.md), so
        # read the page without it.
        no_notes = self.backups / 'none.md'
        with (
            patch('core.updates.can_self_update', return_value=self_update),
            patch('core.updates.platform_update_status', return_value=platform or _NO_GIT),
            patch(
                'plugins.installed.release_notes.views._release_notes_path', return_value=no_notes
            ),
        ):
            return self.client.get(self.URL).content.decode()

    def test_a_built_image_gets_one_line_instead_of_buttons(self):
        html = self.page(self_update=False)
        self.assertIn('This store updates when a new version is released.', html)
        for gone in (
            'Check for updates',
            'Update now',
            'data-testid="component-updates"',
            'No git metadata',
        ):
            self.assertNotIn(gone, html)

    def test_it_shows_the_commit_the_install_time_and_the_backup(self):
        DeployEvent.objects.create(
            version=settings.MORPHEUS_VERSION,
            commit='d' * 40,
            deployed_at=datetime(2026, 10, 19, 12, 0, tzinfo=UTC),
        )
        folder = self.backups / 'pre-deploy'
        folder.mkdir()
        name = f'morpheus-backup-20261019T115900Z-{settings.MORPHEUS_VERSION}-ddddddd.tar.gz'
        (folder / name).write_bytes(b'x' * 2048)
        html = self.page(self_update=False)
        self.assertIn('Commit <code>ddddddd</code>', html)
        self.assertIn('Installed 19 Oct 2026', html)
        self.assertIn('Database backup from before the last update', html)
        self.assertIn(filesizeformat(2048), html)

    def test_without_a_backup_it_says_when_one_is_made(self):
        html = self.page(self_update=False)
        self.assertIn(
            'The store makes one automatically before any update that changes the database.', html
        )

    def test_a_git_install_keeps_its_buttons(self):
        status = {
            'source': 'git',
            'available': 'yes',
            'behind': 2,
            'upstream': 'origin/main',
            'current': 'v1',
            'latest': 'v2',
        }
        html = self.page(self_update=True, platform=status)
        self.assertIn('Update now', html)
        self.assertIn('Check for updates', html)
        self.assertNotIn('This store updates when a new version is released.', html)
