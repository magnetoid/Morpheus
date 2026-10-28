"""Stacking, levels, muting, snooze and archive — and the pages and tools on top."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from plugins.installed.notifications_center import services
from plugins.installed.notifications_center.models import Notification


def _staff(name='a', **extra):
    return get_user_model().objects.create_user(
        username=f'{name}@example.com',
        email=f'{name}@example.com',
        password='x',
        is_staff=True,
        **extra,
    )


class StackTests(TestCase):
    def setUp(self):
        self.user = _staff()

    def test_a_repeat_with_the_same_subject_stacks(self):
        services.notify(
            user=self.user, kind='inventory.low_stock', title='Low stock — Orb', subject='variant:1'
        )
        n = services.notify(
            user=self.user,
            kind='inventory.low_stock',
            title='Low stock — Orb (2 left)',
            subject='variant:1',
        )
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)
        self.assertEqual(n.count, 2)
        self.assertEqual(n.title, 'Low stock — Orb (2 left)')
        self.assertEqual(
            [o['title'] for o in n.history], ['Low stock — Orb (2 left)', 'Low stock — Orb']
        )

    def test_another_subject_or_none_never_stacks(self):
        services.notify(user=self.user, kind='inventory.low_stock', title='A', subject='variant:1')
        services.notify(user=self.user, kind='inventory.low_stock', title='B', subject='variant:2')
        services.notify(user=self.user, kind='returns.requested', title='RMA 1')
        services.notify(user=self.user, kind='returns.requested', title='RMA 1')
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 4)

    def test_reading_or_archiving_closes_the_stack(self):
        first = services.notify(
            user=self.user, kind='agents.run_failed', title='x', subject='agent:w'
        )
        services.apply(first, 'read')
        second = services.notify(
            user=self.user, kind='agents.run_failed', title='x', subject='agent:w'
        )
        self.assertNotEqual(first.pk, second.pk)
        services.apply(second, 'archive')
        third = services.notify(
            user=self.user, kind='agents.run_failed', title='x', subject='agent:w'
        )
        self.assertNotIn(third.pk, (first.pk, second.pk))

    def test_a_stack_keeps_its_highest_level_and_the_last_twenty(self):
        for i in range(25):
            n = services.notify(
                user=self.user,
                kind='workflows.fired',
                title=f't{i}',
                level='urgent' if i == 3 else 'info',
                subject='wf:1',
            )
        self.assertEqual(n.count, 25)
        self.assertEqual(n.level, 'urgent')
        self.assertEqual(len(n.history), services.MAX_OCCURRENCES)
        self.assertEqual(n.forgotten, 5)
        self.assertEqual(n.history[0]['title'], 't24')

    def test_the_kind_sets_the_default_level(self):
        out = services.notify(user=self.user, kind='inventory.out_of_stock', title='x')
        low = services.notify(user=self.user, kind='inventory.low_stock', title='x')
        other = services.notify(user=self.user, kind='something.else', title='x')
        self.assertEqual((out.level, low.level, other.level), ('urgent', 'warning', 'info'))

    def test_a_muted_kind_is_not_delivered(self):
        other = _staff('b')
        services.set_muted(self.user, 'inventory.low_stock', True)
        self.assertIsNone(services.notify(user=self.user, kind='inventory.low_stock', title='x'))
        self.assertEqual(services.notify_all_staff(kind='inventory.low_stock', title='x'), 1)
        self.assertEqual(Notification.objects.get().user, other)
        services.set_muted(self.user, 'inventory.low_stock', False)
        self.assertIsNotNone(services.notify(user=self.user, kind='inventory.low_stock', title='x'))

    def test_the_app_events_name_a_subject(self):
        from plugins.installed.notifications_center.app import NotificationsCenterPlugin

        variant = mock.Mock(pk=7, sku='SKU', product=mock.Mock(name='p'))
        variant.product.name = 'Orb'
        level = mock.Mock(variant=variant, available_quantity=2)
        NotificationsCenterPlugin._on_low_stock(stock_level=level)
        NotificationsCenterPlugin._on_low_stock(stock_level=level)
        NotificationsCenterPlugin._on_agent_failed(agent='worker', run_id=None, error='boom')
        NotificationsCenterPlugin._on_agent_failed(agent='worker', run_id=None, error='boom again')
        rows = Notification.objects.filter(user=self.user)
        self.assertEqual(sorted(r.count for r in rows), [2, 2])


class InboxTests(TestCase):
    def setUp(self):
        self.user = _staff()

    def test_unread_counts_skip_archived_and_snoozed_and_count_urgent(self):
        services.notify(user=self.user, kind='inventory.out_of_stock', title='urgent')
        services.notify(user=self.user, kind='returns.requested', title='warning')
        archived = services.notify(user=self.user, kind='returns.requested', title='gone')
        snoozed = services.notify(user=self.user, kind='returns.requested', title='later')
        services.apply(archived, 'archive')
        services.apply(snoozed, 'snooze', until='hour')
        self.assertEqual(services.unread_counts(self.user), {'unread': 2, 'urgent': 1})

    def test_a_snooze_comes_back_unread_at_the_top(self):
        n = services.notify(user=self.user, kind='returns.requested', title='later')
        services.notify(user=self.user, kind='returns.requested', title='newer')
        services.apply(n, 'read')
        line = services.apply(n, 'snooze', until='hour')
        self.assertIn('Snoozed until', line)
        n.refresh_from_db()
        self.assertIsNone(n.read_at)
        self.assertNotIn(n, services.inbox(self.user))
        later = timezone.now() + timedelta(hours=2)
        with mock.patch('django.utils.timezone.now', return_value=later):
            first = services.ordered(services.inbox(self.user)).first()
        self.assertEqual(first.pk, n.pk)

    def test_tomorrow_is_nine_on_the_store_clock(self):
        from zoneinfo import ZoneInfo

        from core.models import StoreSettings

        StoreSettings.objects.create(timezone='America/New_York')
        zone = ZoneInfo('America/New_York')
        # 03:30 UTC on the 28th is still the evening of the 27th in New York.
        now = datetime(2026, 10, 28, 3, 30, tzinfo=UTC)
        wake = services.snooze_until('tomorrow', now=now).astimezone(zone)
        self.assertEqual((wake.date().isoformat(), wake.hour, wake.minute), ('2026-10-28', 9, 0))
        week = services.snooze_until('week', now=now).astimezone(zone)
        self.assertEqual((week.date().isoformat(), week.hour), ('2026-11-03', 9))

    def test_a_repeat_changes_the_revision_but_not_the_count(self):
        services.notify(user=self.user, kind='k', title='x', subject='s')
        before = (services.revision(self.user), services.unread_counts(self.user))
        services.notify(user=self.user, kind='k', title='x again', subject='s')
        self.assertEqual(services.unread_counts(self.user), before[1])
        self.assertNotEqual(services.revision(self.user), before[0])

    def test_postgres_takes_a_lock_per_stack(self):
        cursor = mock.MagicMock()
        with (
            mock.patch.object(services.connection, 'vendor', 'postgresql'),
            mock.patch.object(services.connection, 'cursor', return_value=cursor),
        ):
            services._lock_stack(self.user, 'inventory.low_stock:variant:1')
        sql, params = cursor.__enter__.return_value.execute.call_args.args
        self.assertIn('pg_advisory_xact_lock', sql)
        self.assertIsInstance(params[0], int)

    def test_rows_without_last_at_still_sort_by_creation(self):
        old = Notification.objects.create(user=self.user, kind='k', title='old')
        Notification.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=1))
        new = services.notify(user=self.user, kind='k', title='new')
        self.assertEqual(
            [n.pk for n in services.ordered(services.inbox(self.user))], [new.pk, old.pk]
        )

    def test_unknown_action_or_snooze_is_refused(self):
        n = services.notify(user=self.user, kind='k', title='x')
        with self.assertRaises(ValueError):
            services.apply(n, 'delete')
        with self.assertRaises(ValueError):
            services.apply(n, 'snooze', until='forever')

    def test_a_malformed_id_is_none(self):
        self.assertIsNone(services.own(self.user, 'not-a-uuid'))


class PageTests(TestCase):
    def setUp(self):
        self.user = _staff()
        self.client.force_login(self.user)
        self.n = services.notify(
            user=self.user, kind='inventory.low_stock', title='Low — Orb', subject='v:1'
        )
        services.notify(
            user=self.user, kind='inventory.low_stock', title='Low — Orb', subject='v:1'
        )

    def test_anonymous_is_sent_to_sign_in(self):
        self.client.logout()
        for url in ('/dashboard/notifications/', '/dashboard/notifications/preferences/'):
            self.assertIn(self.client.get(url).status_code, (302, 403))

    def test_every_tab_and_filter_renders(self):
        for query in (
            '',
            '?show=unread',
            '?show=snoozed',
            '?show=archived',
            '?level=warning&kind=inventory.low_stock',
        ):
            r = self.client.get('/dashboard/notifications/' + query)
            self.assertEqual(r.status_code, 200, query)
        r = self.client.get('/dashboard/notifications/')
        self.assertContains(r, '×2')
        self.assertContains(r, 'Show all 2')

    def test_the_bell_api_returns_stacks_and_counts(self):
        data = self.client.get('/dashboard/notifications/api/latest/').json()
        self.assertEqual((data['unread'], data['urgent']), (1, 0))
        self.assertEqual(data['notifications'][0]['count'], 2)
        counts = self.client.get('/dashboard/notifications/api/latest/?counts=1').json()
        self.assertEqual((counts['unread'], counts['urgent']), (1, 0))
        self.assertEqual(counts['rev'], services.revision(self.user))

    def test_act_answers_json_to_the_bell(self):
        r = self.client.post(
            f'/dashboard/notifications/{self.n.pk}/act/',
            {'action': 'archive'},
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['unread'], 0)
        r = self.client.post(
            f'/dashboard/notifications/{self.n.pk}/act/',
            {'action': 'nope'},
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()['ok'])

    def test_act_redirects_a_form_only_inside_the_dashboard(self):
        url = f'/dashboard/notifications/{self.n.pk}/act/'
        r = self.client.post(
            url, {'action': 'read', 'next': '/dashboard/notifications/?show=unread'}
        )
        self.assertEqual(r['Location'], '/dashboard/notifications/?show=unread')
        r = self.client.post(url, {'action': 'unread', 'next': 'https://evil.example/'})
        self.assertEqual(r['Location'], '/dashboard/notifications/')

    def test_another_persons_notification_is_untouched(self):
        other = services.notify(user=_staff('b'), kind='k', title='theirs')
        r = self.client.post(
            f'/dashboard/notifications/{other.pk}/act/',
            {'action': 'archive'},
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(r.status_code, 400)
        other.refresh_from_db()
        self.assertIsNone(other.archived_at)

    def test_settings_mute_the_unticked_kinds(self):
        self.assertEqual(self.client.get('/dashboard/notifications/preferences/').status_code, 200)
        self.client.post('/dashboard/notifications/preferences/', {'kind': ['inventory.low_stock']})
        muted = services.muted_kinds(self.user)
        self.assertNotIn('inventory.low_stock', muted)
        self.assertIn('returns.requested', muted)

    def test_a_malformed_id_on_the_old_bell_post_is_not_an_error(self):
        r = self.client.post('/dashboard/notifications/api/latest/', {'id': 'nope'})
        self.assertEqual(r.status_code, 200)


class ShellSeamTests(TestCase):
    def test_the_app_contributes_its_menu_entry_and_bell_assets(self):
        from plugins.installed.notifications_center.app import NotificationsCenterPlugin

        app = NotificationsCenterPlugin()
        menu = app.on_user_menu([])
        self.assertEqual(menu[0]['url'], '/dashboard/notifications/preferences/')
        self.assertEqual(app.on_body_end([]), ['notifications_center/_bell_assets.html'])

    def test_the_shell_names_none_of_the_apps_files_or_settings(self):
        from pathlib import Path

        from django.conf import settings

        base = Path(
            settings.BASE_DIR,
            'plugins/installed/admin_dashboard/templates/admin_dashboard/base.html',
        )
        text = base.read_text()
        self.assertNotIn('notifications_center/', text)
        self.assertNotIn('/dashboard/notifications/preferences/', text)


class AgentToolTests(TestCase):
    def setUp(self):
        self.user = _staff()
        self.n = services.notify(user=self.user, kind='inventory.out_of_stock', title='Out — Orb')
        self.ctx = {'user': self.user, 'conversation_key': f'user:{self.user.pk}:chat:1'}

    def test_list_reads_the_askers_own_inbox(self):
        from plugins.installed.notifications_center.agent_tools import notifications_list_tool

        services.notify(user=_staff('b'), kind='k', title='theirs')
        out = notifications_list_tool.invoke({'show': 'unread'}, context=self.ctx).output
        self.assertEqual([n['title'] for n in out['notifications']], ['Out — Orb'])
        self.assertEqual(out['urgent'], 1)

    def test_update_is_gated_and_acts(self):
        from plugins.installed.notifications_center.agent_tools import notifications_update_tool

        self.assertTrue(notifications_update_tool.requires_approval)
        self.assertEqual(notifications_update_tool.scopes, ['system.write'])
        out = notifications_update_tool.invoke(
            {'id': str(self.n.pk), 'action': 'archive'}, context=self.ctx
        ).output
        self.assertTrue(out['ok'])
        self.n.refresh_from_db()
        self.assertIsNotNone(self.n.archived_at)

    def test_an_external_agent_is_refused(self):
        from core.agents.tools import ToolError
        from plugins.installed.notifications_center.agent_tools import notifications_list_tool

        with (
            mock.patch('core.assistant.gates.is_external_key', return_value=True),
            self.assertRaises(ToolError),
        ):
            notifications_list_tool.invoke({}, context=self.ctx)
