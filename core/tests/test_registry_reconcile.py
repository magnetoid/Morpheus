"""An app switch flipped in one process reaches every other (P5, v0.172.0).

Each web and Celery worker keeps the apps that are on in memory. Until v0.172.0
a toggle changed only the process that took the click: the other workers kept
the old set until a restart, and Linda's tools changed no process at all. Now
the switch is stored and a token is bumped (`AppRegistry.activate` /
`deactivate`, called by `plugins.services.set_enabled`), and every process
follows the stored switches before its next request or task
(`AppRegistry.reconcile`, from `PluginMiddleware` and Celery's `task_prerun`).

These tests play the second process: they store a switch and bump the token
the way another worker's toggle leaves them, then check that this process
follows, writes nothing, runs no tear-down, and leaves protected apps alone.
"""

from __future__ import annotations

import threading
import uuid
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from plugins.base import MorpheusPlugin
from plugins.registry import _VERSION_KEY, DB_REREAD_S, app_registry
from plugins.testing import follow_app_switches

PROBE = 'zztest_reconcile_probe'


def flipped_elsewhere(name: str, enabled: bool) -> None:
    """What another worker's toggle leaves behind: the stored switch, a new token."""
    from plugins.models import PluginConfig

    PluginConfig.objects.update_or_create(plugin_name=name, defaults={'is_enabled': enabled})
    cache.set(_VERSION_KEY, uuid.uuid4().hex, None)


class _Probe(MorpheusPlugin):
    name = PROBE
    label = 'Reconcile probe'
    version = '0.0.1'
    ready_calls = 0
    fail = False

    def ready(self):
        type(self).ready_calls += 1
        if type(self).fail:
            raise RuntimeError('probe start-up failed')


def install_probe(test, *, fail: bool = False, **attrs) -> type[_Probe]:
    """Put a fresh probe app in the registry, off, and take it out afterwards."""
    cls = type('Probe', (_Probe,), {'ready_calls': 0, 'fail': fail, **attrs})
    instance = cls()
    instance._registry = app_registry
    app_registry._classes[cls.name] = cls
    app_registry._plugins[cls.name] = instance

    def remove():
        app_registry._apply_inactive(cls.name)
        for index in (app_registry._classes, app_registry._plugins):
            index.pop(cls.name, None)
        for names in (app_registry._wired, app_registry._failed):
            names.discard(cls.name)

    test.addCleanup(remove)
    return cls


class ReconcileTestCase(TestCase):
    def setUp(self):
        super().setUp()
        # Under tests a process follows the switches only when asked; this starts
        # in step with the token and puts every app back afterwards.
        follow_app_switches(self)


class FollowTheStoredSwitchesTests(ReconcileTestCase):
    def test_its_hooks_stop_answering_and_answer_again(self):
        from core.hooks import hook_registry

        event = 'zztest.reconcile.probe'
        calls = []
        hook_registry.register(event, lambda **_: calls.append('seo'), plugin='seo')
        self.addCleanup(hook_registry._handlers.pop, event, None)

        flipped_elsewhere('seo', False)
        app_registry.reconcile()
        hook_registry.fire(event)
        self.assertEqual(calls, [])
        self.assertIsNone(app_registry.settings_panel('seo'))

        flipped_elsewhere('seo', True)
        app_registry.reconcile()
        hook_registry.fire(event)
        self.assertEqual(calls, ['seo'])

    def test_following_writes_nothing_bumps_nothing_and_runs_no_tear_down(self):
        from plugins.models import PluginConfig

        flipped_elsewhere('seo', False)
        token = cache.get(_VERSION_KEY)
        rows = list(PluginConfig.objects.order_by('plugin_name').values_list())
        with (
            patch.object(app_registry._plugins['seo'], 'on_disable') as on_disable,
            CaptureQueriesContext(connection) as queries,
        ):
            app_registry.reconcile()

        self.assertFalse(app_registry.is_active('seo'))
        on_disable.assert_not_called()
        self.assertEqual(cache.get(_VERSION_KEY), token)
        self.assertEqual(list(PluginConfig.objects.order_by('plugin_name').values_list()), rows)
        writes = [q['sql'] for q in queries if not q['sql'].lstrip().upper().startswith('SELECT')]
        self.assertEqual(writes, [])

    def test_while_nothing_changed_it_asks_the_database_nothing(self):
        flipped_elsewhere('seo', False)
        app_registry.reconcile()
        with self.assertNumQueries(0):
            app_registry.reconcile()
            app_registry.reconcile()

    def test_a_protected_or_system_app_keeps_running(self):
        self.assertTrue(app_registry._classes['janus'].system)
        flipped_elsewhere('catalog', False)
        flipped_elsewhere('janus', False)
        app_registry.reconcile()
        self.assertTrue(app_registry.is_active('catalog'))
        self.assertTrue(app_registry.is_active('janus'))

    def test_an_app_with_no_stored_switch_is_left_as_it_is(self):
        from plugins.models import PluginConfig

        PluginConfig.objects.filter(plugin_name='seo').delete()
        cache.set(_VERSION_KEY, uuid.uuid4().hex, None)
        app_registry.reconcile()
        self.assertTrue(app_registry.is_active('seo'))


class StartUpHereTests(ReconcileTestCase):
    def test_an_app_switched_on_elsewhere_starts_here_once(self):
        probe = install_probe(self)

        flipped_elsewhere(PROBE, True)
        app_registry.reconcile()
        self.assertTrue(app_registry.is_active(PROBE))
        self.assertEqual(probe.ready_calls, 1)

        flipped_elsewhere(PROBE, False)
        app_registry.reconcile()
        self.assertFalse(app_registry.is_active(PROBE))

        flipped_elsewhere(PROBE, True)
        app_registry.reconcile()
        self.assertTrue(app_registry.is_active(PROBE))
        self.assertEqual(probe.ready_calls, 1)  # ready() wired it once; a re-enable re-collects

    def test_a_start_up_that_fails_stays_off_here_and_is_not_retried(self):
        probe = install_probe(self, fail=True)

        flipped_elsewhere(PROBE, True)
        with self.assertLogs('morpheus.plugins', 'ERROR'):
            app_registry.reconcile()
        self.assertFalse(app_registry.is_active(PROBE))

        flipped_elsewhere(PROBE, True)
        app_registry.reconcile()
        self.assertFalse(app_registry.is_active(PROBE))
        self.assertEqual(probe.ready_calls, 1)


class TimedRereadTests(ReconcileTestCase):
    def test_a_lost_bump_is_caught_by_the_timed_reread_outside_tests(self):
        from plugins.models import PluginConfig

        install_probe(self)
        flipped_elsewhere(PROBE, True)
        app_registry.reconcile()
        self.assertTrue(app_registry.is_active(PROBE))

        # The switch moves but the bump is lost (a cache outage).
        PluginConfig.objects.filter(plugin_name=PROBE).update(is_enabled=False)
        app_registry.reconcile()
        self.assertTrue(app_registry.is_active(PROBE), 'under tests there is no timed re-read')

        with override_settings(_RUNNING_TESTS=False):
            with self.assertNumQueries(0):
                app_registry.reconcile()  # read a moment ago: not due yet
            app_registry._last_db_read -= DB_REREAD_S + 1
            app_registry.reconcile()
        self.assertFalse(app_registry.is_active(PROBE))


class UnderTestsTests(TestCase):
    def test_a_process_follows_only_when_a_test_asks(self):
        # Tests set apps' in-memory state by hand; following would undo it.
        app_registry._active.discard('seo')
        self.addCleanup(app_registry._active.add, 'seo')
        flipped_elsewhere('seo', True)
        app_registry.reconcile()
        self.assertFalse(app_registry.is_active('seo'))


class EveryDoorReconcilesTests(TestCase):
    def test_a_request_follows_before_its_view_runs(self):
        with patch.object(app_registry, 'reconcile') as reconcile:
            self.client.get('/robots.txt')
        reconcile.assert_called()

    def test_a_task_follows_before_it_runs(self):
        from celery.signals import task_prerun

        import morph.celery  # noqa: F401 — connects the receiver

        with patch.object(app_registry, 'reconcile') as reconcile:
            task_prerun.send(sender=None, task_id='t', task=None, args=(), kwargs={})
        reconcile.assert_called_once()


class MiddlewareOrderTests(SimpleTestCase):
    def test_plugin_middleware_runs_after_the_restore_gate_and_before_any_app(self):
        stack = list(settings.MIDDLEWARE)
        mine = stack.index('plugins.middleware.PluginMiddleware')
        # A reconcile may read the database, which a restore closes first.
        self.assertGreater(mine, stack.index('core.restore.RestoreGateMiddleware'))
        # Every middleware that asks an app for something runs on the followed set.
        for earlier in stack[:mine]:
            self.assertFalse(earlier.startswith(('plugins.', 'themes.', 'api.')), earlier)


class SetEnabledTests(ReconcileTestCase):
    """The one writer: what it refuses, and what it leaves for the others."""

    def switch(self, name, enabled):
        from plugins.services import set_enabled

        return set_enabled(name, enabled, actor='test')

    def assertRefused(self, name, enabled, words):
        from plugins.services import AppSwitchRefused

        with self.assertRaises(AppSwitchRefused) as cm:
            self.switch(name, enabled)
        self.assertIn(words, str(cm.exception))

    def test_a_switch_is_stored_bumped_and_audited(self):
        from core.audit.models import AuditEvent
        from plugins.models import PluginConfig

        install_probe(self)
        token = app_registry._version()
        result = self.switch(PROBE, True)
        self.assertTrue(result.changed)
        self.assertTrue(app_registry.is_active(PROBE))
        self.assertTrue(PluginConfig.objects.get(plugin_name=PROBE).is_enabled)
        self.assertNotEqual(cache.get(_VERSION_KEY), token)
        self.assertTrue(AuditEvent.objects.filter(event_type='app.enabled', target=PROBE).exists())

        self.switch(PROBE, False)
        self.assertFalse(app_registry.is_active(PROBE))
        self.assertFalse(PluginConfig.objects.get(plugin_name=PROBE).is_enabled)

    def test_the_tear_down_runs_where_it_was_switched_off(self):
        install_probe(self)
        self.switch(PROBE, True)
        with patch.object(app_registry._plugins[PROBE], 'on_disable') as on_disable:
            self.switch(PROBE, False)
        on_disable.assert_called_once()

    def test_the_tear_down_still_runs_when_its_start_up_failed_here(self):
        # The store has it on (another worker started it); here ready() failed.
        install_probe(self, fail=True)
        flipped_elsewhere(PROBE, True)
        with self.assertLogs('morpheus.plugins', 'ERROR'):
            app_registry.reconcile()
        self.assertFalse(app_registry.is_active(PROBE))

        with patch.object(app_registry._plugins[PROBE], 'on_disable') as on_disable:
            self.switch(PROBE, False)
        on_disable.assert_called_once()

    def test_a_switch_the_database_did_not_save_changes_nothing(self):
        from core.audit.models import AuditEvent
        from plugins.models import PluginConfig

        install_probe(self)
        token = app_registry._version()
        broken = patch.object(PluginConfig.objects, 'update_or_create', side_effect=DatabaseError)
        with broken, self.assertLogs('morpheus.plugins', 'ERROR'):
            self.assertRefused(PROBE, True, 'did not save the switch')
        self.assertFalse(app_registry.is_active(PROBE), 'switched back off here')
        self.assertEqual(cache.get(_VERSION_KEY), token)

        self.switch(PROBE, True)
        with (
            patch.object(app_registry._plugins[PROBE], 'on_disable') as on_disable,
            broken,
            self.assertLogs('morpheus.plugins', 'ERROR'),
        ):
            self.assertRefused(PROBE, False, 'did not save the switch')
        self.assertTrue(app_registry.is_active(PROBE))
        on_disable.assert_not_called()
        self.assertTrue(PluginConfig.objects.get(plugin_name=PROBE).is_enabled)
        self.assertFalse(
            AuditEvent.objects.filter(event_type='app.disabled', target=PROBE).exists()
        )

    def test_a_start_up_that_fails_stores_nothing(self):
        from plugins.models import PluginConfig

        install_probe(self, fail=True)
        with self.assertLogs('morpheus.plugins', 'ERROR'):
            self.assertRefused(PROBE, True, 'could not start')
        self.assertFalse(PluginConfig.objects.filter(plugin_name=PROBE, is_enabled=True).exists())

    def test_an_unknown_protected_or_system_app(self):
        install_probe(self, system=True)
        self.switch(PROBE, True)
        self.assertRefused('no_such_app', True, 'There is no app named')
        self.assertRefused('catalog', False, 'cannot be switched off')
        self.assertRefused(PROBE, False, 'part of the platform')

    def test_what_it_needs_and_what_needs_it(self):
        # wishlist: nothing installed needs it, with or without the opt-in apps
        # (booking_marketplace needs seo, so the refusal would name it too).
        install_probe(self, requires=['wishlist'])
        self.switch(PROBE, True)
        self.assertRefused(
            'wishlist', False, 'Reconcile probe needs Wishlist; switch it off first.'
        )
        self.switch(PROBE, False)
        self.switch('wishlist', False)
        self.assertRefused(PROBE, True, 'switch that on first')

    def test_an_app_it_conflicts_with(self):
        install_probe(self, conflicts=['seo'])
        self.assertRefused(PROBE, True, 'cannot run beside')


class OneSwitchAtATimeTests(ReconcileTestCase):
    """Threads of one worker never switch the same app at once.

    A gunicorn worker serves several requests on threads. Were a reconcile and a
    click, or two reconciles, to start the same app together, its ready() would
    run twice and its hooks would answer twice for the life of the worker (two
    emails, two point awards, a cart step applied twice); and a thread arriving
    while a reconcile is half done must wait rather than serve on the half.
    """

    def blocking_probe(self):
        entered, release = threading.Event(), threading.Event()

        def ready(probe):
            type(probe).ready_calls += 1
            entered.set()
            release.wait(5)

        probe = install_probe(self, ready=ready)
        self.addCleanup(release.set)
        return probe, entered, release

    def run_in_thread(self, target):
        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        return thread

    def test_a_reconcile_waits_for_a_click_in_flight(self):
        probe, entered, release = self.blocking_probe()
        cache.set(_VERSION_KEY, uuid.uuid4().hex, None)  # another worker switched it on
        with (
            patch.object(app_registry, '_store_switch'),
            patch.object(app_registry, '_stored_switches', return_value={PROBE: True}),
        ):
            click = self.run_in_thread(lambda: app_registry.activate(PROBE))
            self.assertTrue(entered.wait(5))
            follow = self.run_in_thread(app_registry.reconcile)
            follow.join(0.2)
            self.assertTrue(follow.is_alive(), 'the reconcile waits for the switch in flight')
            release.set()
            click.join(5)
            follow.join(5)
        self.assertEqual(probe.ready_calls, 1)
        self.assertTrue(app_registry.is_active(PROBE))

    def test_a_request_waits_for_a_reconcile_half_done(self):
        probe, entered, release = self.blocking_probe()
        cache.set(_VERSION_KEY, uuid.uuid4().hex, None)
        with patch.object(app_registry, '_stored_switches', return_value={PROBE: True}):
            first = self.run_in_thread(app_registry.reconcile)
            self.assertTrue(entered.wait(5))
            second = self.run_in_thread(app_registry.reconcile)
            second.join(0.2)
            self.assertTrue(second.is_alive(), 'the second request waits for the first to finish')
            release.set()
            first.join(5)
            second.join(5)
        self.assertEqual(probe.ready_calls, 1)
        self.assertTrue(app_registry.is_active(PROBE))


class HandlerListsAreSwappedTests(TestCase):
    def test_registering_a_handler_never_changes_the_list_a_reader_holds(self):
        # list.sort() empties a list while it runs: a thread firing the event
        # then found no handlers. Registering builds a new list instead.
        from core.hooks import hook_registry

        event = 'zztest.reconcile.swap'
        self.addCleanup(hook_registry._handlers.pop, event, None)
        hook_registry.register(event, lambda **_: 'b', priority=20)
        held = hook_registry._handlers[event]
        hook_registry.register(event, lambda **_: 'a', priority=10)
        self.assertIsNot(hook_registry._handlers[event], held)
        self.assertEqual(len(held), 1)
        self.assertEqual(hook_registry.fire(event), ['a', 'b'])
