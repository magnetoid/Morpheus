"""IndexNow pings leave the request on a thread — never under the test runner.

A product save and a sitemap change each started a daemon thread that reads
and writes the database (the launch switch, the IndexNow key) while the test
runner may still be creating tables on CI's file-backed SQLite. That was the
"database table is locked" failure in four of the last eight red runs on main.
"""

from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase, override_settings

from plugins.installed.seo.services import indexnow


class BackgroundPingTests(SimpleTestCase):
    def test_no_thread_under_the_test_runner(self):
        with mock.patch.object(indexnow.threading, 'Thread') as thread:
            indexnow.ping_in_background(['https://example.com/products/x/'])
        thread.assert_not_called()

    @override_settings(_RUNNING_TESTS=False)
    def test_a_thread_in_production(self):
        with mock.patch.object(indexnow.threading, 'Thread') as thread:
            indexnow.ping_in_background(['https://example.com/products/x/'])
        thread.assert_called_once()
        self.assertIs(thread.call_args.kwargs['target'], indexnow.ping_indexnow)
        self.assertTrue(thread.call_args.kwargs['daemon'])
        thread.return_value.start.assert_called_once()

    def test_the_two_callers_use_it(self):
        import inspect

        from plugins.installed.seo import app as seo_app
        from plugins.installed.seo import views as seo_views

        for module in (seo_app, seo_views):
            with self.subTest(module=module.__name__):
                self.assertNotIn('threading.Thread(', inspect.getsource(module))
                self.assertIn('ping_in_background', inspect.getsource(module))
