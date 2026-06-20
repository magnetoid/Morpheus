"""Morpheus Brain — core engine signals/analyst + the protected surface page."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.brain import analyst, signals


class SignalsTests(TestCase):
    def test_gather_all_never_raises(self):
        data = signals.gather_all()
        for key in ('plugins', 'errors', 'code', 'content', 'storefront', 'improvements'):
            self.assertIn(key, data)
            self.assertIsInstance(data[key], dict)

    def test_plugins_health_lists_registry(self):
        out = signals.plugins_health()
        self.assertTrue(out['available'])
        self.assertGreater(out['total'], 0)


class AnalystTests(TestCase):
    def test_unconfigured_ai_degrades_gracefully(self):
        # No real provider in tests → analyze() reports not-configured, no crash.
        out = analyst.analyze(
            {'code': {}, 'errors': {}, 'content': {}, 'storefront': {}, 'plugins': {}}
        )
        self.assertIn('configured', out)
        self.assertIsInstance(out.get('recommendations'), list)

    def test_summarize_signals_compacts(self):
        text = analyst._summarize_signals(
            {
                'errors': {'recent': [{'severity': 80, 'seen_count': 3, 'summary': 'boom'}]},
                'code': {'quality': [{'severity': 50, 'summary': 'big file'}]},
            }
        )
        self.assertIn('boom', text)
        self.assertIn('big file', text)

    def test_parse_json_lenient(self):
        self.assertEqual(analyst._parse_json('```json\n{"a":1}\n```'), {'a': 1})
        self.assertEqual(analyst._parse_json('noise {"a": 2} trailing'), {'a': 2})
        self.assertIsNone(analyst._parse_json('not json at all'))


class BrainPageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            username='boss', email='b@x.io', password='pw', is_staff=True
        )

    def test_renders_for_staff(self):
        self.client.force_login(self.staff)
        resp = self.client.get('/dashboard/apps/morpheus_brain/brain/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Morpheus Brain')
        self.assertContains(resp, 'AI analysis')

    def test_anon_blocked(self):
        resp = self.client.get('/dashboard/apps/morpheus_brain/brain/')
        self.assertIn(resp.status_code, (301, 302, 403))

    def test_protected_from_disable(self):
        from plugins.installed.admin_dashboard.views_split.apps import PROTECTED_PLUGINS

        self.assertIn('morpheus_brain', PROTECTED_PLUGINS)
