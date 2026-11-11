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

    def test_the_card_compiles(self):
        get_template('admin_dashboard/_updater_card.html')
