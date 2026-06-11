"""Tests for the plugin engine: base class validation + scaffolder."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from plugins.base import MorpheusPlugin, PluginConfigurationError


class PluginMetadataValidationTests(SimpleTestCase):
    def test_valid_plugin_subclass(self):
        class Good(MorpheusPlugin):
            name = 'good_plug'
            label = 'Good Plug'
            version = '1.2.3'

        self.assertEqual(Good.name, 'good_plug')

    def test_invalid_name_camel_case(self):
        with self.assertRaises(PluginConfigurationError):

            class Bad(MorpheusPlugin):
                name = 'BadName'
                label = 'Bad'
                version = '1.0.0'

    def test_missing_label(self):
        with self.assertRaises(PluginConfigurationError):

            class NoLabel(MorpheusPlugin):
                name = 'no_label_plug'
                label = ''
                version = '1.0.0'

    def test_invalid_version(self):
        with self.assertRaises(PluginConfigurationError):

            class BadVer(MorpheusPlugin):
                name = 'bad_ver_plug'
                label = 'Bad Ver'
                version = 'oops'

    def test_requires_must_be_list_of_strings(self):
        with self.assertRaises(PluginConfigurationError):

            class BadReq(MorpheusPlugin):
                name = 'bad_req_plug'
                label = 'Bad Requires'
                version = '1.0.0'
                requires = ['ok', 123]  # type: ignore

    def test_register_hook_validates_handler(self):
        class P(MorpheusPlugin):
            name = 'register_validator'
            label = 'Register Validator'
            version = '0.1.0'

        with self.assertRaises(TypeError):
            P().register_hook('order.placed', 'not callable')

    def test_register_urls_outside_ready_raises(self):
        class P(MorpheusPlugin):
            name = 'urls_validator'
            label = 'URLs Validator'
            version = '0.1.0'

        with self.assertRaises(RuntimeError):
            P().register_urls('something.urls')


class MorphCreatePluginTests(SimpleTestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix='morph-scaffold-'))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _scaffold(self, name: str, **flags) -> Path:
        call_command(
            'morph_create_plugin',
            name,
            target=str(self.tmp),
            **flags,
        )
        return self.tmp / name

    def test_scaffold_minimal(self):
        out = self._scaffold('hello_scaffold')
        self.assertTrue((out / '__init__.py').exists())
        self.assertTrue((out / 'apps.py').exists())
        self.assertTrue((out / 'plugin.py').exists())
        self.assertTrue((out / 'tests/test_smoke.py').exists())
        self.assertFalse((out / 'models.py').exists())
        self.assertFalse((out / 'urls.py').exists())

    def test_scaffold_with_models(self):
        out = self._scaffold('with_models_scaffold', with_models=True)
        self.assertTrue((out / 'models.py').exists())
        self.assertTrue((out / 'migrations/__init__.py').exists())

    def test_scaffold_with_graphql_urls_tasks(self):
        out = self._scaffold(
            'full_kit_scaffold',
            with_graphql=True,
            with_urls=True,
            with_tasks=True,
        )
        self.assertTrue((out / 'graphql/queries.py').exists())
        self.assertTrue((out / 'urls.py').exists())
        self.assertTrue((out / 'views.py').exists())
        self.assertTrue((out / 'tasks.py').exists())

    def test_scaffold_rejects_bad_name(self):
        with self.assertRaises(CommandError):
            call_command(
                'morph_create_plugin',
                'BadName',
                target=str(self.tmp),
            )

    def test_plugin_py_compiles(self):
        out = self._scaffold(
            'compile_scaffold',
            with_models=True,
            with_graphql=True,
        )
        plugin_py = (out / 'plugin.py').read_text()
        compile(plugin_py, str(out / 'plugin.py'), 'exec')
        graphql_py = (out / 'graphql/queries.py').read_text()
        compile(graphql_py, str(out / 'graphql/queries.py'), 'exec')


class PluginContributionTests(SimpleTestCase):
    """Verify plugin contribution surfaces flow through the registry."""

    def test_plugin_can_contribute_storefront_block(self):
        from plugins.contributions import StorefrontBlock
        from plugins.registry import PluginRegistry

        class P(MorpheusPlugin):
            name = 'sf_block_test'
            label = 'SF Block Test'
            version = '0.1.0'

            def contribute_storefront_blocks(self):
                return [StorefrontBlock(slot='home_below_grid', template='x.html', priority=10)]

        reg = PluginRegistry()
        instance = P()
        reg._collect_contributions(instance)
        blocks = reg.storefront_blocks_for('home_below_grid')
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].plugin, 'sf_block_test')
        self.assertEqual(blocks[0].priority, 10)

    def test_plugin_can_contribute_dashboard_page(self):
        from plugins.contributions import DashboardPage
        from plugins.registry import PluginRegistry

        class P(MorpheusPlugin):
            name = 'dash_page_test'
            label = 'Dash Page Test'
            version = '0.1.0'

            def contribute_dashboard_pages(self):
                return [DashboardPage(label='Bulk Edit', slug='bulk', view='x.y.z', icon='edit')]

        reg = PluginRegistry()
        reg._collect_contributions(P())
        pages = reg.dashboard_pages()
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].plugin, 'dash_page_test')
        self.assertEqual(pages[0].slug, 'bulk')

    def test_plugin_can_contribute_settings_panel(self):
        from plugins.contributions import SettingsPanel
        from plugins.registry import PluginRegistry

        class P(MorpheusPlugin):
            name = 'settings_panel_test'
            label = 'Settings Panel Test'
            version = '0.1.0'

            def get_config_schema(self):
                return {
                    'type': 'object',
                    'properties': {'enabled': {'type': 'boolean', 'default': True}},
                }

            def contribute_settings_panel(self):
                return SettingsPanel(label='Settings', schema=self.get_config_schema())

        reg = PluginRegistry()
        reg._collect_contributions(P())
        panel = reg.settings_panel('settings_panel_test')
        self.assertIsNotNone(panel)
        self.assertEqual(panel.plugin, 'settings_panel_test')

    def test_drop_contributions_removes_them(self):
        from plugins.contributions import StorefrontBlock
        from plugins.registry import PluginRegistry

        class P(MorpheusPlugin):
            name = 'drop_test'
            label = 'Drop Test'
            version = '0.1.0'

            def contribute_storefront_blocks(self):
                return [StorefrontBlock(slot='s', template='t.html')]

        reg = PluginRegistry()
        reg._collect_contributions(P())
        self.assertEqual(len(reg.storefront_blocks_for('s')), 1)
        reg._drop_contributions('drop_test')
        self.assertEqual(len(reg.storefront_blocks_for('s')), 0)


class StorefrontBlocksTagTests(SimpleTestCase):
    """The {% storefront_blocks 'slot' %} tag renders contributed templates."""

    def test_tag_renders_nothing_when_no_blocks(self):
        from django.template import Context, Template

        out = Template("{% load morph %}{% storefront_blocks 'no_such_slot' %}").render(Context({}))
        self.assertEqual(out.strip(), '')
