"""A handler registered with ``mode='async'`` runs (v0.200.0).

The Celery task that runs async handlers looked its handler up by a dotted
import path and walked that path from the wrong module, so no async handler
ever ran: the worker logged "cannot resolve" and dropped the event. Nothing in
the tree registered one, and an app could not: ``Plugin.register_hook`` took no
``mode``, though the SDK README shows it. The worker now finds the handler in
its own registry, which also holds an app's bound methods.
"""

from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase

from core.hooks import hook_registry
from core.tasks import run_hook_handler_async

EVENT = 'test.async_hooks.event'


class _Listener:
    def __init__(self):
        self.seen = []

    def on_event(self, **kwargs):
        self.seen.append(kwargs)


def _module_level_handler(**kwargs):
    _module_level_handler.seen.append(kwargs)


_module_level_handler.seen = []


class AsyncHookTests(SimpleTestCase):
    def setUp(self):
        # Put the event's handlers back as they were: the registry is process-wide.
        before = list(hook_registry._handlers.get(EVENT, []))
        self.addCleanup(hook_registry._handlers.__setitem__, EVENT, before)
        self.addCleanup(setattr, hook_registry, '_active_check', hook_registry._active_check)
        _module_level_handler.seen.clear()

    def test_a_function_registered_async_runs_with_json_arguments(self):
        hook_registry.register(EVENT, _module_level_handler, mode='async')

        hook_registry.fire(EVENT, order_id=7, note='hi')

        self.assertEqual(_module_level_handler.seen, [{'order_id': 7, 'note': 'hi'}])

    def test_a_bound_method_registered_async_runs(self):
        listener = _Listener()
        hook_registry.register(EVENT, listener.on_event, mode='async')

        hook_registry.fire(EVENT, order_id=7)

        self.assertEqual(listener.seen, [{'order_id': 7}])

    def test_the_task_runs_nothing_for_a_name_that_is_not_subscribed(self):
        listener = _Listener()
        hook_registry.register(EVENT, listener.on_event, mode='async')

        with self.assertLogs('morpheus.core.webhooks', level='ERROR'):
            run_hook_handler_async.run(EVENT, 'os.system', {'command': 'true'})

        self.assertEqual(listener.seen, [])

    def test_a_sync_handler_is_never_run_by_the_task(self):
        listener = _Listener()
        hook_registry.register(EVENT, listener.on_event)  # sync
        path = hook_registry._handler_path(listener.on_event)

        with self.assertLogs('morpheus.core.webhooks', level='ERROR'):
            run_hook_handler_async.run(EVENT, path, {})

        self.assertEqual(listener.seen, [])

    def test_the_worker_skips_a_handler_whose_app_is_off(self):
        listener = _Listener()
        hook_registry.register(EVENT, listener.on_event, mode='async', plugin='switched_off')
        hook_registry._active_check = lambda name: name != 'switched_off'
        path = hook_registry._handler_path(listener.on_event)

        with self.assertLogs('morpheus.core.webhooks', level='ERROR'):
            run_hook_handler_async.run(EVENT, path, {})

        self.assertEqual(listener.seen, [])


class AppRegisterHookModeTests(SimpleTestCase):
    def test_an_app_can_register_an_async_handler(self):
        from plugins.base import MorpheusPlugin

        app = MorpheusPlugin.__new__(MorpheusPlugin)
        app.name = 'some_app'

        def handler(**_kw):
            return None

        with mock.patch.object(hook_registry, 'register') as register:
            app.register_hook(EVENT, handler, priority=95, mode='async')

        register.assert_called_once_with(
            EVENT, handler, priority=95, mode='async', plugin='some_app'
        )
