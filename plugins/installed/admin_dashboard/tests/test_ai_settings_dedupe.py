"""The AI settings page is the single source of truth — the old schema
duplicate at /dashboard/settings/ai_assistant/ now bounces to it, and saving
from the rich page persists config and returns there (no second page)."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase


class AISettingsDedupeTests(TestCase):
    def setUp(self):
        self.c = Client()
        u = get_user_model().objects.create_user(
            username='staff', email='s@x.test', password='pw', is_staff=True, is_superuser=True
        )
        self.c.force_login(u)

    def test_get_plugin_page_redirects_to_rich_ai_page(self):
        r = self.c.get('/dashboard/settings/ai_assistant/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], '/dashboard/settings/ai/')

    def test_post_saves_and_bounces_back_to_rich_page(self):
        from plugins.registry import plugin_registry

        r = self.c.post(
            '/dashboard/settings/ai_assistant/',
            {'openai_api_key': 'sk-test-xyz', '_next': '/dashboard/settings/ai/'},
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], '/dashboard/settings/ai/')
        # config actually persisted
        plugin_registry.get('ai_assistant').invalidate_config_cache()
        self.assertEqual(
            plugin_registry.get('ai_assistant').get_config_value('openai_api_key'), 'sk-test-xyz'
        )

    def test_rich_ai_page_renders(self):
        r = self.c.get('/dashboard/settings/ai/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'AI providers')
