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

    def test_page_is_the_unified_updater_plus_changelog(self):
        """The two update pages are one: the version page now also renders the
        updater (check for updates + the apply endpoints) alongside the changelog."""
        self.client.force_login(self.staff)
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
    """Help and About live on the project website and open embedded here.

    Written once on morpheus.direct for every store (owner's call, 2026-10-10);
    the dashboard frames the site's embed mode. Only these two pages may frame
    that site — the dashboard's enforced CSP frames nothing else.
    """

    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            username='boss2', email='b2@x.io', password='pw', is_staff=True
        )

    def test_about_and_help_embed_the_website_pages(self):
        self.client.force_login(self.staff)
        for slug, page in (('about', 'about.html'), ('help', 'help.html')):
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
        self.assertIn('href="/dashboard/apps/release_notes/help/"', html)
        self.assertIn('href="/dashboard/apps/release_notes/about/"', html)

    def test_anon_blocked(self):
        for slug in ('about', 'help'):
            resp = self.client.get(f'/dashboard/apps/release_notes/{slug}/')
            self.assertIn(resp.status_code, (302, 301, 403))
