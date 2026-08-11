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

    def tearDown(self):
        # The POST test persists openai_api_key into the ai_assistant plugin's
        # in-memory _config_cache (plugins/base.py). That cache lives on the
        # registry-singleton plugin instance, so it survives this TestCase's DB
        # rollback and would leak 'sk-test-xyz' into later tests (e.g.
        # test_reflection saw it as a configured provider and made a live 401
        # call). Invalidate it so the next test re-reads the rolled-back DB.
        from plugins.registry import app_registry

        p = app_registry.get('ai_assistant')
        if p is not None:
            p.invalidate_config_cache()

    def test_get_plugin_page_redirects_to_rich_ai_page(self):
        r = self.c.get('/dashboard/settings/ai_assistant/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], '/dashboard/settings/ai/')

    def test_post_saves_and_bounces_back_to_rich_page(self):
        from plugins.registry import app_registry

        r = self.c.post(
            '/dashboard/settings/ai_assistant/',
            {'openai_api_key': 'sk-test-xyz', '_next': '/dashboard/settings/ai/'},
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], '/dashboard/settings/ai/')
        # config actually persisted
        app_registry.get('ai_assistant').invalidate_config_cache()
        self.assertEqual(
            app_registry.get('ai_assistant').get_config_value('openai_api_key'), 'sk-test-xyz'
        )

    def test_rich_ai_page_renders(self):
        r = self.c.get('/dashboard/settings/ai/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'AI providers')
