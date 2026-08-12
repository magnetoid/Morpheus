"""The pluggable update source.

The properties that matter for an updater are all about *not lying*: never
claim "up to date" when we simply could not see the releases, never offer an
update we cannot compare against, and never let a network failure surface as
an error page.
"""

from __future__ import annotations

import urllib.error
from unittest import mock

from django.test import SimpleTestCase, override_settings

from core.update_sources import (
    GitHubReleaseSource,
    check_for_update,
    configured_source,
    is_newer,
    parse_version,
)


class VersionComparisonTests(SimpleTestCase):
    def test_parses_the_numeric_core(self):
        self.assertEqual(parse_version('v1.2.3'), (1, 2, 3))
        self.assertEqual(parse_version('1.2.3'), (1, 2, 3))
        self.assertEqual(parse_version('v0.43.1-rc1'), (0, 43, 1))

    def test_unparseable_is_empty_not_an_error(self):
        self.assertEqual(parse_version('unknown'), ())
        self.assertEqual(parse_version(''), ())

    def test_ordering(self):
        self.assertTrue(is_newer('v0.44.0', 'v0.43.1'))
        self.assertTrue(is_newer('v0.43.2', 'v0.43.1'))
        self.assertFalse(is_newer('v0.43.1', 'v0.43.1'))
        self.assertFalse(is_newer('v0.43.0', 'v0.43.1'))

    def test_never_offers_an_update_it_cannot_compare(self):
        """A dev checkout reporting 'unknown' must not be told to update."""
        self.assertFalse(is_newer('v1.0.0', 'unknown'))
        self.assertFalse(is_newer('garbage', 'v0.43.1'))


class GitHubSourceTests(SimpleTestCase):
    def _source(self, token=''):
        return GitHubReleaseSource('magnetoid/morpheus', token)

    def test_accepts_a_full_url_or_a_slug(self):
        self.assertEqual(GitHubReleaseSource('https://github.com/a/b').repo, 'a/b')
        self.assertEqual(GitHubReleaseSource('a/b').repo, 'a/b')

    def test_reads_the_tag_and_notes(self):
        payload = {
            'tag_name': 'v0.44.0',
            'body': 'notes here',
            'html_url': 'https://example.invalid/r',
            'assets': [{'name': 'morpheus-0.44.0.tar.gz', 'browser_download_url': 'https://x/a'}],
        }
        with mock.patch.object(GitHubReleaseSource, '_get', return_value=payload):
            rel = self._source().latest()
        self.assertEqual(rel.version, 'v0.44.0')
        self.assertEqual(rel.artifact, 'https://x/a')

    def test_a_404_without_a_token_is_unknown_not_up_to_date(self):
        """A private repo 404s anonymously. Reporting that as "no update" would
        tell a merchant they are current when we cannot see the releases at
        all — the worst failure mode an updater has."""
        err = urllib.error.HTTPError('u', 404, 'Not Found', {}, None)
        with mock.patch.object(GitHubReleaseSource, '_get', side_effect=err):
            self.assertIsNone(self._source().latest())

    def test_network_failure_returns_none_never_raises(self):
        with mock.patch.object(GitHubReleaseSource, '_get', side_effect=OSError('dns')):
            self.assertIsNone(self._source().latest())


class CheckForUpdateTests(SimpleTestCase):
    @override_settings(MORPHEUS_UPDATE_REPO='')
    def test_unconfigured_is_unavailable_with_a_reason(self):
        self.assertIsNone(configured_source())
        out = check_for_update('v0.43.1')
        self.assertEqual(out['available'], 'unavailable')
        self.assertIn('MORPHEUS_UPDATE_REPO', out['reason'])

    @override_settings(MORPHEUS_UPDATE_REPO='a/b', MORPHEUS_UPDATE_TOKEN='')
    def test_unreachable_source_is_unknown_not_no(self):
        with mock.patch.object(GitHubReleaseSource, 'latest', return_value=None):
            out = check_for_update('v0.43.1')
        self.assertEqual(out['available'], 'unknown')

    @override_settings(MORPHEUS_UPDATE_REPO='a/b')
    def test_reports_yes_and_no_correctly(self):
        from core.update_sources import ReleaseInfo

        with mock.patch.object(
            GitHubReleaseSource, 'latest', return_value=ReleaseInfo(version='v0.44.0')
        ):
            self.assertEqual(check_for_update('v0.43.1')['available'], 'yes')
        with mock.patch.object(
            GitHubReleaseSource, 'latest', return_value=ReleaseInfo(version='v0.43.1')
        ):
            self.assertEqual(check_for_update('v0.43.1')['available'], 'no')


class GitlessDeploymentTests(SimpleTestCase):
    """The reason this module exists: a container image has no .git."""

    @override_settings(MORPHEUS_UPDATE_REPO='a/b')
    def test_status_falls_back_to_the_release_source_without_git(self):
        from core import updates
        from core.update_sources import ReleaseInfo

        with (
            mock.patch.object(updates, '_repo_root', return_value=_NoGitPath()),
            mock.patch.object(
                GitHubReleaseSource, 'latest', return_value=ReleaseInfo(version='v99.0.0')
            ),
        ):
            out = updates.platform_update_status()
        self.assertEqual(out['source'], 'github')
        self.assertEqual(out['available'], 'yes')

    @override_settings(MORPHEUS_UPDATE_REPO='')
    def test_without_git_and_without_a_source_it_still_says_why(self):
        from core import updates

        with mock.patch.object(updates, '_repo_root', return_value=_NoGitPath()):
            out = updates.platform_update_status()
        self.assertEqual(out['available'], 'unavailable')
        self.assertIn('No git metadata', out['reason'])


class _NoGitPath:
    """Stands in for a deployment root whose `.git` does not exist."""

    def __truediv__(self, other):
        return self

    def exists(self) -> bool:
        return False
