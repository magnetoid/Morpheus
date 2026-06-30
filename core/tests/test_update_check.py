"""Daily update check: refresh caches the status, the task degrades on error,
and the dashboard activity feed surfaces "update available" when behind."""

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

from core.tasks import check_for_updates
from core.updates import cached_update_status, refresh_update_status

BEHIND = {'source': 'git', 'available': 'yes', 'behind': 3, 'latest': 'v0.2.12'}
UPTODATE = {'source': 'git', 'available': 'no', 'behind': 0, 'latest': 'v0.2.11'}


class UpdateCheckTests(TestCase):
    def setUp(self):
        cache.delete('morpheus:update_status')

    def test_refresh_caches_status(self):
        with patch('core.updates.platform_update_status', return_value=BEHIND) as m:
            out = refresh_update_status()
        m.assert_called_once_with(fetch=True)
        self.assertEqual(out, BEHIND)
        self.assertEqual(cached_update_status(), BEHIND)

    def test_cached_status_is_none_before_first_check(self):
        self.assertIsNone(cached_update_status())

    def test_task_degrades_on_error(self):
        with patch('core.updates.platform_update_status', side_effect=RuntimeError('boom')):
            out = check_for_updates()
        self.assertEqual(out['available'], 'unknown')


class UpdateActivityFeedTests(TestCase):
    def setUp(self):
        cache.delete('morpheus:update_status')

    def _feed(self):
        from plugins.installed.admin_dashboard.plugin import AdminDashboardPlugin

        return AdminDashboardPlugin().on_activity_feed([])

    def test_item_appears_when_behind(self):
        cache.set('morpheus:update_status', BEHIND, 60)
        items = self._feed()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['kind'], 'update')
        self.assertIn('v0.2.12', items[0]['label'])
        self.assertEqual(items[0]['url'], '/dashboard/updates/')

    def test_no_item_when_up_to_date(self):
        cache.set('morpheus:update_status', UPTODATE, 60)
        self.assertEqual(self._feed(), [])

    def test_no_item_when_never_checked(self):
        self.assertEqual(self._feed(), [])
