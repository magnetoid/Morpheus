"""AI providers panel = connection manager: only connected providers show as
cards; the rest live behind "Add AI"; disconnect clears a provider's keys and
reassigns the active provider."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from plugins.registry import plugin_registry

DISCONNECT_URL = '/dashboard/settings/ai/disconnect/'
AI_URL = '/dashboard/settings/ai/'


def _ai():
    return plugin_registry.get('ai_assistant')


class ConnectionManagerRenderTests(TestCase):
    def setUp(self):
        self.c = Client()
        self.staff = get_user_model().objects.create_user(
            username='staff', email='s@x.test', password='pw', is_staff=True, is_superuser=True
        )
        self.c.force_login(self.staff)
        # The plugin config cache is process-global and survives the per-test DB
        # rollback, so drop it to read each test's clean (rolled-back) state.
        _ai().invalidate_config_cache()

    def test_connected_provider_shows_as_card_unconnected_in_picker(self):
        ai = _ai()
        ai.set_config('openai_api_key', 'sk-test')
        ai.invalidate_config_cache()
        html = self.c.get(AI_URL).content.decode()
        # OpenAI is connected → has a Disconnect button, not a hidden connect card.
        self.assertIn('class="btn ai-disconnect-btn" data-provider="openai"', html)
        self.assertNotIn('data-connect-card="openai"', html)
        # Anthropic has no key → it's an available template, hidden until picked.
        self.assertIn('data-connect-card="anthropic"', html)
        # DeepSeek is offered as a connectable template.
        self.assertIn('data-connect-card="deepseek"', html)
        self.assertIn('Add AI', html)

    def test_no_connected_shows_empty_state(self):
        # Fresh config: nothing connected.
        html = self.c.get(AI_URL).content.decode()
        self.assertIn('data-ai-empty', html)


class DisconnectTests(TestCase):
    def setUp(self):
        self.c = Client()
        self.staff = get_user_model().objects.create_user(
            username='staff2', email='s2@x.test', password='pw', is_staff=True, is_superuser=True
        )
        _ai().invalidate_config_cache()

    def test_disconnect_clears_keys_and_reassigns_active(self):
        self.c.force_login(self.staff)
        ai = _ai()
        ai.set_config('openai_api_key', 'sk-openai')
        ai.set_config('anthropic_api_key', 'sk-anthropic')
        ai.set_config('ai_provider', 'openai')
        ai.invalidate_config_cache()

        r = self.c.post(DISCONNECT_URL, {'provider': 'openai'})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body['ok'])
        # active reassigned to the remaining connected provider
        self.assertEqual(body['active'], 'anthropic')

        ai.invalidate_config_cache()
        self.assertEqual(ai.get_config_value('openai_api_key'), '')
        self.assertEqual(ai.get_config_value('ai_provider'), 'anthropic')

    def test_disconnect_unknown_provider_rejected(self):
        self.c.force_login(self.staff)
        r = self.c.post(DISCONNECT_URL, {'provider': 'not-a-provider'})
        self.assertEqual(r.status_code, 400)

    def test_disconnect_requires_post(self):
        self.c.force_login(self.staff)
        r = self.c.get(DISCONNECT_URL)
        self.assertEqual(r.status_code, 405)


class DisconnectPermissionBoundaryTests(TestCase):
    """The three mandatory permission-boundary tests for the disconnect view."""

    def setUp(self):
        self.c = Client()
        _ai().invalidate_config_cache()

    def test_anonymous_blocked(self):
        r = self.c.post(DISCONNECT_URL, {'provider': 'openai'})
        self.assertIn(r.status_code, (302, 403))

    def test_authed_non_staff_blocked(self):
        u = get_user_model().objects.create_user(
            username='shopper', email='c@x.test', password='pw', is_staff=False
        )
        self.c.force_login(u)
        r = self.c.post(DISCONNECT_URL, {'provider': 'openai'})
        self.assertIn(r.status_code, (302, 403))

    def test_staff_allowed(self):
        u = get_user_model().objects.create_user(
            username='admin', email='a@x.test', password='pw', is_staff=True, is_superuser=True
        )
        self.c.force_login(u)
        r = self.c.post(DISCONNECT_URL, {'provider': 'openai'})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])


class ProviderCatalogUXTests(TestCase):
    """Curated model suggestions + provider blurbs improve the connect flow."""

    def setUp(self):
        self.c = Client()
        self.staff = get_user_model().objects.create_user(
            username='cat', email='cat@x.test', password='pw', is_staff=True, is_superuser=True
        )
        self.c.force_login(self.staff)
        _ai().invalidate_config_cache()

    def test_model_datalist_and_blurb_render(self):
        html = self.c.get(AI_URL).content.decode()
        # Each provider offers a curated <datalist> of models bound to its input.
        self.assertIn('list="models-deepseek"', html)
        self.assertIn('<datalist id="models-deepseek">', html)
        self.assertIn('deepseek-reasoner', html)  # a curated suggestion
        # Provider blurb (what it's for) shows in the Add-AI picker + card.
        self.assertIn('strong coding', html.lower())

    def test_every_provider_has_models(self):
        from plugins.installed.admin_dashboard.views_split.settings import _AI_PROVIDERS

        for p in _AI_PROVIDERS:
            self.assertTrue(p.get('models'), f'{p["slug"]} has no curated models')
            self.assertTrue(p.get('blurb'), f'{p["slug"]} has no blurb')


PROBE_URL = '/dashboard/settings/ai/probe/'


class FetchedModelsPersistenceTests(TestCase):
    """Fetch persists the provider's model list server-side, so the
    'Pick from fetched models' dropdown is permanent + cross-device."""

    def setUp(self):
        self.c = Client()
        self.staff = get_user_model().objects.create_user(
            username='fm', email='fm@x.test', password='pw', is_staff=True, is_superuser=True
        )
        self.c.force_login(self.staff)
        _ai().invalidate_config_cache()

    def test_fetched_models_render_as_permanent_dropdown(self):
        import json

        ai = _ai()
        ai.set_config('openai_api_key', 'sk-test')  # connected → card shows
        ai.set_config('openai_fetched_models', json.dumps(['gpt-4o', 'o3-mini', 'gpt-4o-mini']))
        ai.invalidate_config_cache()

        html = self.c.get(AI_URL).content.decode()
        # The dropdown is populated (not the empty hidden placeholder) and lists
        # each fetched model as an <option>.
        self.assertIn('Pick from fetched models', html)
        self.assertIn('<option value="o3-mini"', html)
        self.assertIn('3 available', html)

    def test_probe_persists_returned_models_to_config(self):
        from unittest.mock import patch

        fake = {'ok': True, 'models': [{'id': 'gpt-4o'}, {'id': 'o1'}, {'id': ''}]}
        with patch('plugins.installed.ai_assistant.services.probe.probe', return_value=fake):
            resp = self.c.post(PROBE_URL, {'provider': 'openai', 'api_key': 'sk-x'})
        self.assertEqual(resp.status_code, 200)

        import json

        ai = _ai()
        ai.invalidate_config_cache()
        saved = json.loads(ai.get_config().get('openai_fetched_models', '[]'))
        # Empty ids are dropped; valid ones persisted.
        self.assertEqual(saved, ['gpt-4o', 'o1'])
