"""The one settings coercer (v0.173.0, `plugins/config_schema.py`).

The dashboard save, its panel fields, `Plugin.set_config`, Linda's settings
tools and the MCP argument check each had their own partial reading of an app's
schema. These tests pin the shared one, and that every schema in the tree reads.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from plugins import config_schema as cs
from plugins.contributions import SettingsPanel
from plugins.registry import app_registry

INTS = {'type': 'array', 'items': {'type': 'integer', 'minimum': 1}}


class CoerceTests(SimpleTestCase):
    def test_a_boolean_reads_the_words_a_form_or_an_agent_writes(self):
        for raw in ('on', 'true', 'True', ' 1 ', 'yes'):
            self.assertIs(cs.coerce({'type': 'boolean'}, raw), True, raw)
        for raw in ('off', 'false', 'FALSE', '0', 'no', ''):
            self.assertIs(cs.coerce({'type': 'boolean'}, raw), False, raw)
        with self.assertRaises(cs.SettingError):
            cs.coerce({'type': 'boolean'}, 'maybe')

    def test_numbers(self):
        self.assertEqual(cs.coerce({'type': 'integer'}, ' 12 '), 12)
        self.assertEqual(cs.coerce({'type': 'number'}, '1.5'), 1.5)
        for prop, raw in (
            ({'type': 'integer'}, '1.5'),
            ({'type': 'integer'}, 'abc'),
            ({'type': 'number'}, 'nan'),
            ({'type': 'number'}, 'inf'),
        ):
            with self.assertRaises(cs.SettingError, msg=raw):
                cs.coerce(prop, raw)

    def test_a_list_reads_as_json_or_comma_separated(self):
        self.assertEqual(cs.coerce(INTS, '60, 1440 ,4320'), [60, 1440, 4320])
        # What the panel rendered for a list before v0.173.0.
        self.assertEqual(cs.coerce(INTS, '[60, 1440, 4320]'), [60, 1440, 4320])
        self.assertEqual(cs.coerce(INTS, ''), [])
        self.assertEqual(cs.coerce({'type': 'array'}, 'a, b'), ['a', 'b'])
        self.assertEqual(cs.coerce(INTS, ['7', 8]), [7, 8])
        for raw in ('[1, 2', '{"a": 1}', '1, x'):
            with self.assertRaises(cs.SettingError, msg=raw):
                cs.coerce(INTS, raw)

    def test_a_list_shows_as_text_that_reads_back_as_the_same_list(self):
        self.assertEqual(cs.list_text([60, 1440]), '60, 1440')
        strings = {'type': 'array', 'items': {'type': 'string'}}
        for prop, value in (
            (INTS, [60, 1440]),
            (INTS, []),
            (strings, ['a', 'b']),
            # An item a comma would split, or that reads as JSON, shows as JSON.
            (strings, ['a, b', 'c']),
            (strings, ['[x]']),
            ({'type': 'array', 'items': {'type': 'object'}}, [{'k': 1}]),
        ):
            self.assertEqual(cs.coerce(prop, cs.list_text(value)), value, value)

    def test_an_object_reads_as_json(self):
        self.assertEqual(cs.coerce({'type': 'object'}, '{"a": 1}'), {'a': 1})
        with self.assertRaises(cs.SettingError):
            cs.coerce({'type': 'object'}, '[1]')

    def test_text_and_values_of_their_own_type_pass_as_they_are(self):
        self.assertEqual(cs.coerce({'type': 'string'}, '  spaced '), '  spaced ')
        self.assertEqual(cs.coerce({'type': 'integer'}, 5), 5)
        self.assertIs(cs.coerce({'type': 'boolean'}, True), True)
        self.assertEqual(cs.coerce({}, 'x'), 'x')
        self.assertEqual(cs.coerce({'type': 'mystery'}, 'x'), 'x')


class ValidateTests(SimpleTestCase):
    def test_the_messages_the_mcp_edge_has_always_sent(self):
        self.assertEqual(cs.validate('n', 'x', {'type': 'integer'}), "'n' must be integer")
        self.assertEqual(cs.validate('n', True, {'type': 'number'}), "'n' must be number")
        self.assertEqual(
            cs.validate('n', 'c', {'enum': ['a', 'b']}), "'n' must be one of ['a', 'b']"
        )
        self.assertEqual(cs.validate('n', 0, {'minimum': 1}), "'n' must be >= 1")
        self.assertEqual(cs.validate('n', 9, {'maximum': 5}), "'n' must be <= 5")
        self.assertEqual(cs.validate('n', 'ab', {'minLength': 3}), "'n' is too short")
        self.assertEqual(cs.validate('n', 'abcd', {'maxLength': 3}), "'n' is too long")
        self.assertEqual(cs.validate('n', 3, {'type': 'integer', 'minimum': 1}), '')

    def test_errors_checks_a_lists_items_and_lets_none_clear(self):
        self.assertEqual(cs.errors('d', INTS, [5, 0]), ["'d[1]' must be >= 1"])
        self.assertEqual(cs.errors('d', INTS, None), [])
        self.assertEqual(cs.errors('d', INTS, 'x'), ["'d' must be array"])

    def test_clean_reads_then_checks_and_names_the_setting(self):
        self.assertEqual(cs.clean('t', {'type': 'integer', 'minimum': 10}, '30'), 30)
        with self.assertRaisesMessage(cs.SettingError, "'t' must be >= 10"):
            cs.clean('t', {'type': 'integer', 'minimum': 10}, '5')
        with self.assertRaisesMessage(cs.SettingError, "'t' must be a whole number"):
            cs.clean('t', {'type': 'integer'}, 'ten')


class SecretsAndAgentWritesTests(SimpleTestCase):
    def test_a_secret_is_a_password_field_or_an_api_key(self):
        self.assertTrue(cs.is_secret('push_token', {'type': 'string', 'format': 'password'}))
        self.assertTrue(cs.is_secret('openai_api_key', {'type': 'string'}))
        self.assertFalse(cs.is_secret('token_ttl_hours', {'type': 'integer'}))
        # An undeclared key is judged by its name.
        self.assertTrue(cs.is_secret('oauth_refresh_token', None))
        self.assertFalse(cs.is_secret('rate_source', None))

    def test_a_secret_is_not_agent_writable_unless_its_schema_says_so(self):
        password = {'type': 'string', 'format': 'password'}
        self.assertFalse(cs.agent_writable('k', password))
        self.assertTrue(cs.agent_writable('k', {**password, 'x-agent-writable': True}))
        self.assertFalse(cs.agent_writable('k', {'type': 'string', 'x-agent-writable': False}))
        self.assertTrue(cs.agent_writable('k', {'type': 'string'}))
        self.assertFalse(cs.agent_writable('some_token', None))

    def test_an_undeclared_address_is_the_merchants(self):
        for key in ('gemini_base_url', 'anthropic_base_url', 'push_endpoint', 'smtp_host'):
            self.assertFalse(cs.agent_writable(key, None), key)
        self.assertTrue(cs.agent_writable('rate_source', None))
        # A declared one follows its schema: the checkout's terms link is a page.
        self.assertTrue(cs.agent_writable('checkout_terms_url', {'type': 'string'}))

    def test_redact_hides_nested_secrets(self):
        value = {'label': 'PIM', 'items': [{'token': 'mcp_live_abcdefgh'}]}
        out = cs.redact(value)
        self.assertEqual(out['label'], 'PIM')
        self.assertNotIn('abcdefgh', out['items'][0]['token'])
        self.assertEqual(cs.redact('sk-123456', secret=True), 'sk…(redacted)…56')
        self.assertEqual(cs.redact(7, secret=True), '(redacted)')


class PropertiesTests(SimpleTestCase):
    def _plugin(self, schema):
        return SimpleNamespace(name='probe', get_config_schema=lambda: schema)

    def test_the_config_schema_then_what_the_panel_adds(self):
        plugin = self._plugin({'properties': {'a': {'type': 'string'}}})
        panel = SettingsPanel(
            label='Probe',
            schema={'properties': {'a': {'type': 'integer'}, 'b': {'type': 'boolean'}}},
        )
        with patch.object(app_registry, 'settings_panel', return_value=panel):
            props = cs.properties(plugin)
        self.assertEqual(props, {'a': {'type': 'string'}, 'b': {'type': 'boolean'}})

    def test_a_schema_level_flag_applies_to_each_property_that_sets_none(self):
        plugin = self._plugin(
            {
                'x-agent-writable': False,
                'properties': {
                    'a': {'type': 'string'},
                    'b': {'type': 'string', 'x-agent-writable': True},
                },
            }
        )
        with patch.object(app_registry, 'settings_panel', return_value=None):
            props = cs.properties(plugin)
        self.assertFalse(cs.agent_writable('a', props['a']))
        self.assertTrue(cs.agent_writable('b', props['b']))

    def test_either_schema_can_make_a_shared_key_secret_or_the_merchants(self):
        plugin = self._plugin(
            {
                'properties': {
                    'a': {'type': 'string'},
                    'b': {'type': 'string', 'x-agent-writable': True},
                    'c': {'type': 'string'},
                }
            }
        )
        panel = SettingsPanel(
            label='Probe',
            schema={
                'properties': {
                    'a': {'type': 'string', 'format': 'password'},
                    'b': {'type': 'string', 'x-agent-writable': False},
                }
            },
        )
        with patch.object(app_registry, 'settings_panel', return_value=panel):
            props = cs.properties(plugin)
        self.assertTrue(cs.is_secret('a', props['a']))
        self.assertFalse(cs.agent_writable('b', props['b']))
        self.assertTrue(cs.agent_writable('c', props['c']))


class EveryAppsSchemaTests(SimpleTestCase):
    """The coercer reads every schema in the tree, and its flags are where they belong."""

    def test_every_declared_setting_has_a_known_type_and_a_default_that_fits(self):
        bad = []
        for plugin in app_registry.all_plugins():
            for key, prop in cs.properties(plugin).items():
                if not cs.known_type(prop):
                    bad.append(f'{plugin.name}.{key}: type {prop.get("type")!r}')
                elif problems := cs.errors(key, prop, prop.get('default')):
                    bad.append(f'{plugin.name}.{key}: default {problems[0]}')
        self.assertEqual(bad, [])

    def test_what_decides_where_models_and_credentials_go_is_the_merchants(self):
        def writable(app, key):
            return cs.agent_writable(key, cs.properties(app_registry.get(app))[key])

        janus = ('api_key', 'base_url', 'model_source', 'provider', 'model', 'fallback_providers')
        for key in janus:
            self.assertFalse(writable('janus', key), key)
        self.assertFalse(writable('janus', 'extra_instructions'))
        self.assertTrue(writable('janus', 'web_search'))
        self.assertFalse(writable('openai_shopping', 'push_endpoint'))
        for key in cs.properties(app_registry.get('staff_sso')):
            self.assertFalse(writable('staff_sso', key), key)

    def test_every_ai_providers_address_is_the_merchants_declared_or_not(self):
        from core.agents.provider_registry import _DEFAULT_BASE_URLS

        props = cs.properties(app_registry.get('ai_assistant'))
        for name in _DEFAULT_BASE_URLS:
            key = f'{name}_base_url'
            self.assertFalse(cs.agent_writable(key, props.get(key)), key)

    def test_the_limits_on_agents_and_on_access_are_the_merchants(self):
        for app, keys in (
            (
                'agent_core',
                (
                    'agents_paused',
                    'max_agent_runs_daily',
                    'spend_cap_daily',
                    'max_price_change_pct',
                    'max_refund_value',
                ),
            ),
            ('rbac', ('enforcement_mode',)),
            ('backups', ('backup_dir',)),
        ):
            props = cs.properties(app_registry.get(app))
            for key in keys:
                self.assertFalse(cs.agent_writable(key, props[key]), f'{app}.{key}')

    def test_a_text_setting_named_like_a_secret_is_a_password_field(self):
        bad = [
            f'{plugin.name}.{key}'
            for plugin in app_registry.all_plugins()
            for key, prop in cs.properties(plugin).items()
            if prop.get('type') == 'string' and cs.looks_secret(key) and not cs.is_secret(key, prop)
        ]
        self.assertEqual(bad, [])


class SetConfigReportsTests(TestCase):
    def setUp(self):
        self.plugin = app_registry.get('janus')
        self.addCleanup(self.plugin.invalidate_config_cache)

    def test_a_value_its_setting_would_refuse_is_logged_and_still_stored(self):
        with self.assertLogs('plugins.config_schema', 'WARNING') as logs:
            self.plugin.set_config('turn_timeout_s', 5)
        self.assertIn("janus.turn_timeout_s: 'turn_timeout_s' must be >= 10", logs.output[0])
        self.assertEqual(self.plugin.get_config()['turn_timeout_s'], 5)

    def test_the_value_is_never_logged(self):
        with self.assertLogs('plugins.config_schema', 'WARNING') as logs:
            self.plugin.set_config('api_key', 12345678)
        self.assertNotIn('12345678', ''.join(logs.output))

    def test_a_fitting_value_or_an_undeclared_key_logs_nothing(self):
        with self.assertNoLogs('plugins.config_schema', 'WARNING'):
            self.plugin.set_config('turn_timeout_s', 120)
            self.plugin.set_config('some_internal_state', {'any': 'thing'})
