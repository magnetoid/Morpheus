"""Settings → AI → Janus: the page, and that every field reaches its consumer.

CLAUDE.md: a settings field with no consumer is a lie the merchant cannot see.
Each consumer test sets the stored value and asserts the engine or runtime acts
on it — not merely that the form saved it.
"""

from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

import core.assistant.janus_engine as eng
from core.assistant import janus_settings
from core.assistant.runtime import Assistant
from plugins.models import PluginConfig

URL = '/dashboard/apps/janus/engine/'

_VALID = {
    'action': 'save',
    'enabled': 'on',
    'model_source': 'store',
    'provider': '',
    'model': '',
    'base_url': '',
    'api_key': '',
    'max_tool_turns': '8',
    'turn_timeout_s': '55',
    'extra_instructions': '',
    'bundled_skills': 'on',
    'learning': 'on',
    'reasoning_effort': 'low',
}


def _set(**config):
    PluginConfig.objects.update_or_create(plugin_name='janus', defaults={'config': config})


def _stored() -> dict:
    row = PluginConfig.objects.filter(plugin_name='janus').first()
    return dict(row.config or {}) if row else {}


class JanusPageBoundaryTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.staff = users.objects.create_user(
            username='owner', email='owner@example.com', password='x', is_staff=True
        )
        self.customer = users.objects.create_user(
            username='shopper', email='shopper@example.com', password='x'
        )

    def test_anonymous_blocked(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(URL, response.url.split('?')[0])

    def test_authed_without_staff_blocked(self):
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(URL).status_code, 302)

    def test_staff_allowed(self):
        self.client.force_login(self.staff)
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-janus-form')


class JanusPageSaveTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = get_user_model().objects.create_user(
            username='owner', email='owner@example.com', password='x', is_staff=True
        )
        self.client.force_login(self.staff)

    def _post(self, **overrides):
        return self.client.post(URL, {**_VALID, **overrides})

    def test_save_persists_every_field(self):
        response = self._post(
            max_tool_turns='4',
            turn_timeout_s='30',
            extra_instructions='Prices include VAT.',
            bundled_skills='',
            learning='',
        )
        self.assertEqual(response.status_code, 302)
        stored = _stored()
        self.assertFalse(stored['learning'])
        self.assertEqual(stored['max_tool_turns'], 4)
        self.assertEqual(stored['turn_timeout_s'], 30)
        self.assertEqual(stored['extra_instructions'], 'Prices include VAT.')
        self.assertFalse(stored['bundled_skills'])

    def test_limits_are_enforced(self):
        self.assertEqual(self._post(turn_timeout_s='120').status_code, 200)
        self.assertEqual(self._post(max_tool_turns='50').status_code, 200)
        self.assertNotIn('turn_timeout_s', _stored())

    def test_pinned_provider_needs_provider_model_and_key(self):
        response = self._post(model_source='custom')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter the model Janus should use.')
        self.assertNotIn('model_source', _stored())

    def test_api_key_is_write_only(self):
        self._post(
            model_source='custom',
            provider='deepseek',
            model='deepseek-v4-pro',
            api_key='sk-secret-123',
        )
        self.assertEqual(_stored()['api_key'], 'sk-secret-123')
        page = self.client.get(URL)
        self.assertNotContains(page, 'sk-secret-123')
        self.assertContains(page, 'Saved — leave blank to keep it')
        # A blank key on a later save keeps the stored one.
        self._post(model_source='custom', provider='deepseek', model='deepseek-chat', api_key='')
        self.assertEqual(_stored()['api_key'], 'sk-secret-123')

    def test_saved_key_can_be_removed(self):
        self._post(model_source='custom', provider='deepseek', model='m', api_key='sk-secret-123')
        self._post(clear_api_key='on')
        self.assertEqual(_stored()['api_key'], '')

    def test_base_url_must_be_http(self):
        response = self._post(base_url='file:///etc/passwd')
        self.assertContains(response, 'Use a full http:// or https:// address.')

    def test_change_is_audited_without_values(self):
        from core.audit.models import AuditEvent

        self._post(model_source='custom', provider='deepseek', model='m', api_key='sk-secret-123')
        event = AuditEvent.objects.filter(event_type='janus.settings_changed').latest('created_at')
        self.assertEqual(event.actor, self.staff)
        self.assertIn('api_key', event.metadata['changed'])
        self.assertNotIn('sk-secret-123', str(event.metadata))

    def test_connection_test_reports_the_engine_result(self):
        result = {'text': 'ok', 'error': '', 'duration_ms': 4200}
        with mock.patch.object(eng, 'run_janus_turn', return_value=result) as run:
            response = self.client.post(URL, {'action': 'test'})
        self.assertContains(response, 'Answered in 4.2s')
        self.assertEqual(run.call_args.kwargs['turn_token'], '')

    def test_page_url_is_not_shadowed_by_the_settings_deep_link(self):
        # /dashboard/apps/<app>/settings/ belongs to the legacy settings-panel
        # route, so a contributed page with that slug is never reached.
        from plugins.registry import app_registry

        page = next(p for p in app_registry.dashboard_pages() if p.plugin == 'janus')
        self.assertNotEqual(page.slug, 'settings')
        self.assertEqual(self.client.get(URL).status_code, 200)

    def test_page_is_listed_under_settings_ai(self):
        from plugins.registry import app_registry

        page = next(p for p in app_registry.dashboard_pages() if p.plugin == 'janus')
        self.assertEqual((page.nav, page.section), ('settings', 'ai'))

    def test_app_cannot_be_switched_off(self):
        from core.safety import is_plugin_protected

        self.assertTrue(is_plugin_protected('janus'))


class JanusSettingConsumerTests(TestCase):
    """Each stored setting changes what the engine or the turn actually does."""

    def setUp(self):
        cache.clear()

    def test_switched_off_linda_declines_without_starting_the_engine(self):
        _set(enabled=False)
        with mock.patch.object(eng, 'run_janus_turn', side_effect=AssertionError('engine ran')):
            events = list(Assistant().stream(message='hi', conversation_key='t:off'))
        result = events[-1]['result']
        self.assertEqual(result.state, 'completed')
        self.assertIn('turned off', result.text)

    def test_standing_instructions_reach_the_prompt(self):
        _set(extra_instructions='Always quote prices with VAT.')
        prompt = Assistant()._system_prompt(message='hi', context={}, history=[])
        self.assertIn('Always quote prices with VAT.', prompt)

    def test_tool_step_cap_reaches_the_engine_config(self):
        _set(max_tool_turns=3)
        self.assertIn('max_turns: 3', eng._config_text('https://s/mcp/'))

    def test_tool_step_cap_is_clamped(self):
        _set(max_tool_turns=500)
        self.assertIn(
            f'max_turns: {janus_settings.MAX_TOOL_TURNS}', eng._config_text('https://s/mcp/')
        )

    def test_bundled_skills_toggle_reaches_the_engine_config(self):
        _set(bundled_skills=False)
        self.assertNotIn('external_dirs', eng._config_text('https://s/mcp/'))

    def test_thinking_effort_reaches_the_engine_config(self):
        self.assertIn('reasoning_effort: low', eng._config_text('https://s/mcp/'))
        _set(reasoning_effort='high')
        self.assertIn('reasoning_effort: high', eng._config_text('https://s/mcp/'))
        _set(reasoning_effort='xhigh; rm -rf')
        self.assertIn('reasoning_effort: low', eng._config_text('https://s/mcp/'))

    def test_learning_toggle_reaches_the_engine(self):
        self.assertIn('memory', eng.turn_toolsets())
        _set(learning=False)
        self.assertNotIn('memory', eng.turn_toolsets())
        self.assertIn('memory_enabled: false', eng._config_text('https://s/mcp/'))

    def test_time_limit_reaches_the_engine(self):
        _set(turn_timeout_s=20)
        self.assertEqual(eng.turn_timeout_s(), 20)

    def test_time_limit_never_exceeds_the_worker_timeout(self):
        _set(turn_timeout_s=999)
        self.assertEqual(eng.turn_timeout_s(), janus_settings.MAX_TURN_TIMEOUT_S)

    def test_pinned_provider_reaches_the_engine(self):
        _set(model_source='custom', provider='anthropic', model='claude-x', api_key='sk-ant')
        args, env = eng._provider_wiring()
        self.assertEqual(args, ['--provider', 'anthropic', '-m', 'claude-x'])
        self.assertEqual(env['ANTHROPIC_API_KEY'], 'sk-ant')

    def test_incomplete_pin_falls_back_to_the_store_provider(self):
        _set(model_source='custom', provider='anthropic', model='claude-x', api_key='')
        self.assertIsNone(janus_settings.custom_provider())

    def test_unknown_provider_is_never_pinned(self):
        _set(model_source='custom', provider='evil', model='x', api_key='k')
        self.assertIsNone(janus_settings.custom_provider())


class JanusLearningReviewTests(TestCase):
    """The merchant can see and delete everything Linda learned."""

    def setUp(self):
        from core.assistant import janus_learning as jl
        from core.assistant.models import JanusLearning

        users = get_user_model()
        self.staff = users.objects.create_user(
            username='owner', email='owner@example.com', password='x', is_staff=True
        )
        self.colleague = users.objects.create_user(
            username='colleague', email='c@example.com', password='x', is_staff=True
        )
        self.jl = jl
        self.rows = JanusLearning.objects
        self.rows.create(
            path=jl.MEMORY_FILE,
            kind='memory',
            content=f'Ships from Belgrade{jl.ENTRY_DELIMITER}Closed Sundays',
        )
        self.rows.create(
            scope=jl.user_scope(self.colleague),
            path=jl.USER_FILE,
            kind='memory',
            content='Colleague likes emoji',
        )
        self.rows.create(
            path='skills/ops/restock/SKILL.md',
            kind='skill',
            content='---\nname: restock\ndescription: Reorder low stock\n---\nSteps.\n',
        )
        self.rows.create(
            path=jl.LESSONS_FILE, kind='lesson', content='[{"id": "a", "lesson": "x"}]'
        )
        self.client.force_login(self.staff)

    def test_page_lists_what_linda_learned(self):
        page = self.client.get(URL)
        self.assertContains(page, 'data-janus-learned')
        self.assertContains(page, 'Ships from Belgrade')
        self.assertContains(page, 'restock')
        self.assertContains(page, 'Reorder low stock')
        self.assertContains(page, '1 lesson from past work')

    def test_notes_about_a_colleague_are_not_shown(self):
        self.assertNotContains(self.client.get(URL), 'Colleague likes emoji')

    def test_deleting_a_note_removes_only_that_note_and_is_audited(self):
        from core.audit.models import AuditEvent

        note = next(n for n in self.jl.notes()['store'] if n['text'] == 'Closed Sundays')
        response = self.client.post(
            URL, {'action': 'forget_note', 'which': 'store', 'note': note['id']}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.rows.get(path=self.jl.MEMORY_FILE).content, 'Ships from Belgrade')
        event = AuditEvent.objects.get(event_type='janus.learning_forgotten')
        self.assertEqual(event.actor, self.staff)

    def test_a_colleagues_note_cannot_be_deleted_from_here(self):
        self.client.post(
            URL,
            {
                'action': 'forget_note',
                'which': 'user',
                'note': self.jl.note_id('Colleague likes emoji'),
            },
        )
        self.assertTrue(self.rows.filter(path=self.jl.USER_FILE).exists())

    def test_deleting_a_skill_and_lessons(self):
        self.client.post(URL, {'action': 'delete_skill', 'skill': 'skills/ops/restock'})
        self.assertFalse(self.rows.filter(kind='skill').exists())
        self.client.post(URL, {'action': 'clear_lessons'})
        self.assertFalse(self.rows.filter(kind='lesson').exists())

    def test_an_unknown_skill_path_deletes_nothing(self):
        self.client.post(URL, {'action': 'delete_skill', 'skill': 'skills'})
        self.assertTrue(self.rows.filter(kind='skill').exists())
