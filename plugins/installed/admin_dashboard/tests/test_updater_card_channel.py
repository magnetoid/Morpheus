"""The updater card says what the signed channel offers and how to take it."""

# ruff: noqa: PLC0415
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.template.loader import get_template
from django.test import TestCase
from django.urls import reverse

from core.update_sources import MIGRATING_URL

SHA = 'a' * 40
IMAGE = 'ghcr.io/magnetoid/morpheus:' + SHA + '@sha256:' + 'd' * 64


def _status(**over):
    status = {
        'source': 'manifest',
        'available': 'yes',
        'current': 'v1.0.0',
        'latest': 'v9.0.0',
        'commit': SHA,
        'image': IMAGE,
        'breaking': False,
        'notes': 'Faster checkout',
        'notes_url': 'https://github.com/magnetoid/Morpheus/releases/tag/v9.0.0',
        'components': [],
        'path': 'manual',
    }
    status.update(over)
    return status


class UpdaterCardChannelTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser(
            username='card', email='card@example.test', password='pw'
        )
        self.client.force_login(user)

    def _page(self, status, can_self_update=False):
        with (
            patch('core.updates.platform_update_status', return_value=status),
            patch('core.updates.can_self_update', return_value=can_self_update),
        ):
            return self.client.get(reverse('admin_dashboard:updates'), follow=True)

    def test_manual_install_shows_the_image_commands(self):
        r = self._page(_status())
        self.assertContains(r, 'v9.0.0 is out')
        self.assertContains(r, 'MORPHEUS_IMAGE=ghcr.io/magnetoid/morpheus:' + SHA)
        self.assertContains(r, 'docker compose pull')
        self.assertContains(r, 'Release notes')

    def test_git_install_offers_update_now(self):
        r = self._page(_status(path='git'), can_self_update=True)
        self.assertContains(r, reverse('admin_dashboard:updates_apply'))

    def test_breaking_release_links_the_upgrade_steps(self):
        r = self._page(_status(breaking=True, migrating_url=MIGRATING_URL))
        self.assertContains(r, MIGRATING_URL)
        self.assertContains(r, 'Has upgrade steps')

    def test_up_to_date_says_so(self):
        r = self._page(_status(available='no'))
        self.assertContains(r, 'Up to date')

    def test_unavailable_shows_the_reason_not_up_to_date(self):
        r = self._page(_status(available='unavailable', reason='Update check is off here.'))
        self.assertContains(r, 'Update check is off here.')
        self.assertNotContains(r, 'Up to date')

    def test_check_button_shows_for_a_manifest_install_without_git(self):
        r = self._page(_status(available='no'), can_self_update=False)
        self.assertContains(r, reverse('admin_dashboard:updates_check'))

    def test_off_shows_the_reason_on_a_built_image(self):
        off = {
            'source': 'none',
            'available': 'unavailable',
            'reason': 'Update checks are switched off <here>.',
            'current': 'v1.0.0',
            'components': [],
            'path': 'manual',
        }
        r = self._page(off)
        self.assertContains(r, 'Update checks are switched off &lt;here&gt;.')
        self.assertNotContains(r, 'updates when a new version is released')

    def test_the_manual_path_offers_no_update_now(self):
        r = self._page(_status(path='manual'))
        self.assertNotContains(r, reverse('admin_dashboard:updates_apply'))
        self.assertNotContains(r, 'Apply update?')

    def test_a_stale_cache_shows_up_to_date_after_the_version_moves(self):
        from django.core.cache import cache
        from django.test import override_settings

        from core.updates import _UPDATE_STATUS_CACHE_KEY

        cache.set(
            _UPDATE_STATUS_CACHE_KEY,
            {'source': 'manifest', 'available': 'yes', 'latest': 'v2.0.0', 'current': 'v1.0.0'},
            60,
        )
        self.addCleanup(cache.delete, _UPDATE_STATUS_CACHE_KEY)
        with (
            override_settings(
                MORPHEUS_UPDATE_MANIFEST_URL='https://updates.example.test/stable.json',
                MORPHEUS_UPDATE_PUBLIC_KEY='AAAA',
                MORPHEUS_VERSION='v2.0.0',
            ),
            patch('core.updates.can_self_update', return_value=False),
        ):
            r = self.client.get(reverse('admin_dashboard:updates'), follow=True)
        self.assertContains(r, 'Up to date')
        self.assertNotContains(r, 'v2.0.0 is out')

    def test_the_card_compiles(self):
        get_template('admin_dashboard/_updater_card.html')


class UpdateFeedTests(TestCase):
    def _feed(self, cached, version='v1.0.0'):
        from django.test import override_settings

        from plugins.installed.admin_dashboard.app import AdminDashboardPlugin

        with (
            override_settings(MORPHEUS_VERSION=version),
            patch('core.updates.cached_update_status', return_value=cached),
        ):
            return AdminDashboardPlugin().on_activity_feed([])

    def test_a_channel_hint_names_the_running_version(self):
        items = self._feed({'source': 'manifest', 'available': 'yes', 'latest': 'v2.0.0'})
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['hint'], 'running v1.0.0')

    def test_a_cache_older_than_the_running_version_adds_nothing(self):
        cached = {'source': 'manifest', 'available': 'yes', 'latest': 'v2.0.0'}
        self.assertEqual(self._feed(cached, version='v2.0.0'), [])

    def test_the_git_hint_is_unchanged(self):
        items = self._feed({'source': 'git', 'available': 'yes', 'latest': 'v2', 'behind': 3})
        self.assertEqual(items[0]['hint'], '3 commit(s) behind upstream')
