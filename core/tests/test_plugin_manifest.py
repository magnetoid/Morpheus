"""An app names the Morpheus it runs on, and upgrades itself once (P6, v0.179.0).

An app's manifest may name the oldest and newest Morpheus it supports
(`min_morpheus` / `max_morpheus`). The registry does not start an app outside
its range, or one whose `requires` names an app that is missing or not running:
it records why in `app_registry.skipped`, which the Apps page and Linda's
`plugins.list` show. Until v0.179.0 an unmet `requires` only logged at ERROR on
every boot and started the app anyway.

`PluginConfig.installed_version` holds the version each app last ran; after a
migrate, `plugins.compat.run_upgrades` runs a moved app's `on_upgrade(previous)`
once, guarded by a compare-and-swap on that column.
"""

from __future__ import annotations

from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from plugins.base import MorpheusPlugin, PluginConfigurationError
from plugins.compat import after_migrate, incompatibility, is_newer_app_version, run_upgrades
from plugins.registry import app_registry
from plugins.testing import follow_app_switches

FIRST = 'zztest_manifest_first'
SECOND = 'zztest_manifest_second'


class _Probe(MorpheusPlugin):
    name = FIRST
    label = 'Manifest probe'
    version = '1.0.0'
    ready_calls = 0
    disable_calls = 0
    fail = False

    def ready(self):
        type(self).ready_calls += 1
        if type(self).fail:
            raise RuntimeError('probe start-up failed')

    def on_disable(self):
        type(self).disable_calls += 1


def install(test, name: str = FIRST, **attrs) -> type[_Probe]:
    """Put a fresh probe app in the live registry, off, and take it out afterwards."""
    cls = type('Probe', (_Probe,), {'name': name, 'ready_calls': 0, 'disable_calls': 0, **attrs})
    instance = cls()
    instance._registry = app_registry
    app_registry._classes[name] = cls
    app_registry._plugins[name] = instance

    def remove():
        app_registry._apply_inactive(name)
        for index in (app_registry._classes, app_registry._plugins, app_registry.skipped):
            index.pop(name, None)
        for names in (app_registry._wired, app_registry._failed):
            names.discard(name)

    test.addCleanup(remove)
    return cls


class ManifestBoundsTests(SimpleTestCase):
    def test_bounds_are_optional_and_take_a_version_or_a_prefix(self):
        for value in ('', '0.179.0', 'v0.179.0', '0.179', 'v1', '1'):
            with self.subTest(value=value):
                type(
                    'Good',
                    (MorpheusPlugin,),
                    {
                        'name': 'zz_good',
                        'label': 'Good',
                        'version': '1.0.0',
                        'min_morpheus': value,
                        'max_morpheus': value,
                    },
                )

    def test_anything_else_is_refused_when_the_class_is_defined(self):
        for value in ('latest', '>=0.179', '0.179.0.1', '0.179.0-beta', 179, None):
            for field in ('min_morpheus', 'max_morpheus'):
                with (
                    self.subTest(field=field, value=value),
                    self.assertRaises(PluginConfigurationError),
                ):
                    type(
                        'Bad',
                        (MorpheusPlugin,),
                        {'name': 'zz_bad', 'label': 'Bad', 'version': '1.0.0', field: value},
                    )

    def test_the_base_class_upgrade_step_does_nothing(self):
        self.assertIsNone(MorpheusPlugin.on_upgrade(object(), '0.1.0'))


class IncompatibilityTests(SimpleTestCase):
    def probe(self, **bounds):
        return type(
            'P',
            (MorpheusPlugin,),
            {'name': 'zz_bounds', 'label': 'Gift notes', 'version': '1.0.0', **bounds},
        )

    def test_no_bounds_runs_everywhere(self):
        self.assertEqual(incompatibility(self.probe(), 'v0.179.0'), '')

    def test_below_the_minimum_says_what_it_needs(self):
        cls = self.probe(min_morpheus='0.179.2')
        self.assertEqual(
            incompatibility(cls, 'v0.179.1'),
            'Gift notes needs Morpheus 0.179.2 or newer, and this store runs v0.179.1.',
        )
        self.assertEqual(incompatibility(cls, 'v0.179.2'), '')
        self.assertEqual(incompatibility(cls, 'v1.0.0'), '')

    def test_above_the_maximum_says_how_far_it_goes(self):
        cls = self.probe(max_morpheus='0.179')
        self.assertEqual(incompatibility(cls, 'v0.179.0'), '')
        self.assertEqual(incompatibility(cls, 'v0.179.9'), '', 'a prefix covers every patch')
        self.assertEqual(
            incompatibility(cls, 'v0.180.0'),
            'Gift notes runs on Morpheus up to 0.179, and this store runs v0.180.0.',
        )

    def test_a_store_that_cannot_read_its_own_version_runs_every_app(self):
        cls = self.probe(min_morpheus='99.0.0')
        for running in ('', 'unknown', 'dev'):
            with self.subTest(running=running):
                self.assertEqual(incompatibility(cls, running), '')

    def test_it_reads_the_running_version_by_default(self):
        cls = self.probe(min_morpheus='0.179.0')
        with override_settings(MORPHEUS_VERSION='v0.178.9'):
            self.assertIn('needs Morpheus 0.179.0', incompatibility(cls))
        with override_settings(MORPHEUS_VERSION='v0.179.0'):
            self.assertEqual(incompatibility(cls), '')

    def test_every_app_in_the_tree_runs_on_this_release(self):
        """A release never ships an app its own version would not start."""
        stuck = {
            name: incompatibility(cls)
            for name, cls in app_registry._classes.items()
            if incompatibility(cls)
        }
        self.assertEqual(stuck, {})


class PlatformVersionTests(SimpleTestCase):
    def test_the_sdk_reports_the_running_release(self):
        import morpheus

        self.assertEqual(morpheus.__version__, settings.MORPHEUS_VERSION.removeprefix('v'))
        with override_settings(MORPHEUS_VERSION='v9.8.7'):
            self.assertEqual(morpheus.__version__, '9.8.7')
        with override_settings(MORPHEUS_VERSION=''):
            self.assertEqual(morpheus.__version__, 'unknown')

    def test_other_missing_names_still_raise(self):
        import morpheus

        with self.assertRaises(AttributeError):
            morpheus.no_such_name  # noqa: B018


class SkippedAppTests(TestCase):
    """The registry does not start an app that cannot run, and says why."""

    def setUp(self):
        super().setUp()
        follow_app_switches(self)

    def test_an_app_outside_its_range_is_not_started(self):
        cls = install(self, min_morpheus='99.0.0')
        with self.assertLogs('morpheus.plugins', 'WARNING'):
            self.assertFalse(app_registry._apply_active(FIRST))
        self.assertFalse(app_registry.is_active(FIRST))
        self.assertEqual(cls.ready_calls, 0, 'its ready() never ran')
        self.assertIn('needs Morpheus 99.0.0 or newer', app_registry.skipped[FIRST])

    def test_it_starts_once_the_store_runs_a_version_it_supports(self):
        install(self, min_morpheus='99.0.0')
        with self.assertLogs('morpheus.plugins', 'WARNING'):
            app_registry._apply_active(FIRST)
        with override_settings(MORPHEUS_VERSION='v99.0.0'):
            self.assertTrue(app_registry._apply_active(FIRST))
        self.assertNotIn(FIRST, app_registry.skipped)

    def test_a_requirement_the_store_does_not_have(self):
        install(self, requires=['zz_not_installed'])
        with self.assertLogs('morpheus.plugins', 'WARNING'):
            self.assertFalse(app_registry._apply_active(FIRST))
        self.assertEqual(
            app_registry.skipped[FIRST],
            'Manifest probe needs zz_not_installed, which this store does not have.',
        )

    def test_a_core_requirement_the_store_does_not_have(self):
        install(self, requires=['core.zz_not_installed'])
        with self.assertLogs('morpheus.plugins', 'WARNING'):
            self.assertFalse(app_registry._apply_active(FIRST))
        self.assertIn('core.zz_not_installed', app_registry.skipped[FIRST])

    def test_a_requirement_that_is_not_running(self):
        install(self, SECOND, label='Second probe')
        install(self, requires=[SECOND])
        with self.assertLogs('morpheus.plugins', 'WARNING'):
            self.assertFalse(app_registry._apply_active(FIRST))
        self.assertEqual(
            app_registry.skipped[FIRST], 'Manifest probe needs Second probe, which is not running.'
        )

    def test_a_requirement_that_crashed_does_not_take_its_dependents_down(self):
        """One app's failed start-up stays its own: the storefront must not
        404 in a worker because orders' ready() raised there."""
        install(self, SECOND, label='Second probe', fail=True)
        install(self, requires=[SECOND])
        with self.assertLogs('morpheus.plugins', 'ERROR'):
            self.assertFalse(app_registry._apply_active(SECOND))
        self.assertTrue(app_registry._apply_active(FIRST))
        self.assertNotIn(FIRST, app_registry.skipped)

    def test_an_app_waiting_for_its_requirement_starts_after_it(self):
        """The order can put an app before what it needs (a dependency cycle
        falls back to alphabetical): it gets another pass once that started."""
        install(self, SECOND, label='Second probe')
        install(self, requires=[SECOND])
        started = app_registry._start_in_order([FIRST, SECOND])
        self.assertEqual(started, [SECOND, FIRST])
        self.assertNotIn(FIRST, app_registry.skipped)

    def test_a_protected_app_always_starts(self):
        install(self, min_morpheus='99.0.0')
        real = app_registry._keeps_running
        with (
            patch.object(app_registry, '_keeps_running', lambda n: n == FIRST or real(n)),
            self.assertLogs('morpheus.plugins', 'ERROR') as logs,
        ):
            self.assertTrue(app_registry._apply_active(FIRST))
        self.assertIn('starts anyway', logs.output[0])
        self.assertNotIn(FIRST, app_registry.skipped)

    def test_switching_it_off_clears_the_reason(self):
        install(self, min_morpheus='99.0.0')
        with self.assertLogs('morpheus.plugins', 'WARNING'):
            app_registry._apply_active(FIRST)
        app_registry.deactivate(FIRST)
        self.assertNotIn(FIRST, app_registry.skipped)

    def test_a_switch_off_from_another_worker_clears_the_reason(self):
        from core.tests.test_registry_reconcile import flipped_elsewhere

        install(self, min_morpheus='99.0.0')
        with self.assertLogs('morpheus.plugins', 'WARNING'):
            app_registry._apply_active(FIRST)
        flipped_elsewhere(FIRST, False)
        app_registry.reconcile()
        self.assertNotIn(FIRST, app_registry.skipped)

    def test_reconcile_starts_an_app_with_what_it_needs(self):
        from core.tests.test_registry_reconcile import flipped_elsewhere
        from plugins.models import PluginConfig

        install(self, SECOND, label='Second probe')
        install(self, requires=[SECOND])
        PluginConfig.objects.create(plugin_name=SECOND, is_enabled=True)
        flipped_elsewhere(FIRST, True)
        app_registry.reconcile()
        self.assertTrue(app_registry.is_active(SECOND))
        self.assertTrue(app_registry.is_active(FIRST))


class SwitchingOnTests(TestCase):
    """The merchant's switch refuses an app that cannot run, with the reason."""

    def setUp(self):
        super().setUp()
        follow_app_switches(self)

    def test_an_app_outside_its_range_is_refused(self):
        from plugins.services import AppSwitchRefused, set_enabled

        install(self, min_morpheus='99.0.0')
        with self.assertRaises(AppSwitchRefused) as refused:
            set_enabled(FIRST, True, actor='test')
        self.assertIn('needs Morpheus 99.0.0 or newer', str(refused.exception))
        self.assertFalse(app_registry.is_active(FIRST))

    def test_an_app_whose_requirement_is_on_but_not_running_is_refused(self):
        from plugins.models import PluginConfig
        from plugins.services import AppSwitchRefused, set_enabled

        install(self, SECOND, label='Second probe', min_morpheus='99.0.0')
        install(self, requires=[SECOND])
        PluginConfig.objects.create(plugin_name=SECOND, is_enabled=True)
        PluginConfig.objects.create(plugin_name=FIRST, is_enabled=False)
        with self.assertLogs('morpheus.plugins', 'WARNING'):
            app_registry._apply_active(SECOND)  # on for the store, skipped here

        with (
            self.assertLogs('morpheus.plugins', 'WARNING'),
            self.assertRaises(AppSwitchRefused) as refused,
        ):
            set_enabled(FIRST, True, actor='test')
        self.assertEqual(
            str(refused.exception), 'Manifest probe needs Second probe, which is not running.'
        )
        self.assertFalse(PluginConfig.objects.get(plugin_name=FIRST).is_enabled)
        self.assertNotIn(FIRST, app_registry.skipped, 'it stays off, so nothing to explain')


class SwitchingOffTests(TestCase):
    def setUp(self):
        super().setUp()
        follow_app_switches(self)

    def test_an_app_that_never_started_runs_no_tear_down(self):
        from plugins.models import PluginConfig
        from plugins.services import set_enabled

        cls = install(self, min_morpheus='99.0.0')
        PluginConfig.objects.create(plugin_name=FIRST, is_enabled=True)
        with self.assertLogs('morpheus.plugins', 'WARNING'):
            app_registry._apply_active(FIRST)
        set_enabled(FIRST, False, actor='test')
        self.assertEqual(cls.disable_calls, 0)
        self.assertFalse(PluginConfig.objects.get(plugin_name=FIRST).is_enabled)
        self.assertNotIn(FIRST, app_registry.skipped)


class ShownToStaffTests(TestCase):
    def setUp(self):
        super().setUp()
        follow_app_switches(self)
        install(self, min_morpheus='99.0.0')
        with self.assertLogs('morpheus.plugins', 'WARNING'):
            app_registry._apply_active(FIRST)

    def test_plugins_list_names_the_reason(self):
        from core.assistant.tools.plugins import list_plugins_tool

        result = list_plugins_tool.invoke({})
        row = next(r for r in result.output['plugins'] if r['name'] == FIRST)
        self.assertEqual(row['min_morpheus'], '99.0.0')
        self.assertIn('needs Morpheus 99.0.0', row['not_running'])
        self.assertIn('switched on but not running', result.display)

    def test_the_apps_page_names_the_reason(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse

        from plugins.models import PluginConfig

        PluginConfig.objects.create(plugin_name=FIRST, is_enabled=True)
        owner = get_user_model().objects.create_superuser(
            username='owner@example.com', email='owner@example.com', password='x'
        )
        self.client.force_login(owner)
        resp = self.client.get(reverse('admin_dashboard:apps'))
        self.assertContains(resp, 'data-app-not-running')
        self.assertContains(resp, 'Manifest probe needs Morpheus 99.0.0 or newer')

    def test_the_apps_page_says_nothing_for_an_app_switched_off(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse

        from plugins.models import PluginConfig

        PluginConfig.objects.create(plugin_name=FIRST, is_enabled=False)
        owner = get_user_model().objects.create_superuser(
            username='owner@example.com', email='owner@example.com', password='x'
        )
        self.client.force_login(owner)
        resp = self.client.get(reverse('admin_dashboard:apps'))
        self.assertNotContains(resp, 'data-app-not-running')


class _Registry:
    """The part of the registry `run_upgrades` reads: the apps that are on."""

    def __init__(self, *plugins, before=None):
        self.plugins = list(plugins)
        self.before = before

    def active_plugins(self):
        if self.before:
            self.before()
        return self.plugins


class _ReadsFromAReplica:
    """A router that sends every read to a replica this test database lacks, so
    a read that follows the router fails."""

    def db_for_read(self, model, **hints):
        return 'replica'


def upgrading(version='2.0.0', fail=False):
    calls = []

    class Upgrading(MorpheusPlugin):
        name = FIRST
        label = 'Upgrading probe'

        def on_upgrade(self, previous):
            calls.append(previous)
            if fail:
                from plugins.models import PluginConfig

                PluginConfig.objects.create(plugin_name='zz_written_by_a_failed_step')
                raise RuntimeError('the step failed')

    Upgrading.version = version
    return Upgrading(), calls


class AppVersionOrderTests(SimpleTestCase):
    def test_versions_compare_part_by_part(self):
        self.assertTrue(is_newer_app_version('10.0.0', '9.9.9'))
        self.assertTrue(is_newer_app_version('1.2.10', '1.2.9'))
        self.assertFalse(is_newer_app_version('1.0.0', '1.0'), "'1.0' is '1.0.0'")
        self.assertFalse(is_newer_app_version('1.0', '1.0.0'))

    def test_a_pre_release_comes_before_its_release(self):
        self.assertTrue(is_newer_app_version('2.0.0', '2.0.0b1'))
        self.assertTrue(is_newer_app_version('2.0.0b2', '2.0.0b1'))
        self.assertTrue(is_newer_app_version('2.0.0b1', '2.0.0a3'))
        self.assertTrue(is_newer_app_version('2.0.0b1', '1.9.9'))
        self.assertFalse(is_newer_app_version('2.0.0b1', '2.0.0'))

    def test_an_unreadable_version_is_never_newer(self):
        for a, b in (('latest', '1.0.0'), ('1.0.0', ''), ('1.0.0', 'v1'), ('', '')):
            with self.subTest(a=a, b=b):
                self.assertFalse(is_newer_app_version(a, b))


class UpgradeStepTests(TestCase):
    def recorded(self):
        from plugins.models import PluginConfig

        return PluginConfig.objects.get(plugin_name=FIRST).installed_version

    def row(self, version):
        from plugins.models import PluginConfig

        PluginConfig.objects.create(plugin_name=FIRST, installed_version=version)

    def test_a_moved_version_runs_the_step_once(self):
        self.row('1.0.0')
        plugin, calls = upgrading('2.0.0')
        self.assertEqual(run_upgrades(_Registry(plugin)), [FIRST])
        self.assertEqual(calls, ['1.0.0'])
        self.assertEqual(self.recorded(), '2.0.0')

        self.assertEqual(run_upgrades(_Registry(plugin)), [], 'the next deploy does nothing')
        self.assertEqual(calls, ['1.0.0'])

    def test_a_store_with_no_recorded_version_runs_it_with_nothing(self):
        self.row('')
        plugin, calls = upgrading('2.0.0')
        run_upgrades(_Registry(plugin))
        self.assertEqual(calls, [''])
        self.assertEqual(self.recorded(), '2.0.0')

    def test_another_process_that_moved_the_row_first_runs_it_instead(self):
        from plugins.models import PluginConfig

        self.row('1.0.0')
        plugin, calls = upgrading('2.0.0')

        def another_worker():
            PluginConfig.objects.filter(plugin_name=FIRST).update(installed_version='2.0.0')

        self.assertEqual(run_upgrades(_Registry(plugin, before=another_worker)), [])
        self.assertEqual(calls, [])

    def test_a_failed_step_rolls_back_and_runs_again_next_time(self):
        from plugins.models import PluginConfig

        self.row('1.0.0')
        plugin, calls = upgrading('2.0.0', fail=True)
        with self.assertLogs('morpheus.plugins', 'ERROR'):
            self.assertEqual(run_upgrades(_Registry(plugin)), [])
        self.assertEqual(calls, ['1.0.0'])
        self.assertEqual(self.recorded(), '1.0.0', 'the old version is back')
        self.assertFalse(
            PluginConfig.objects.filter(plugin_name='zz_written_by_a_failed_step').exists()
        )

        with self.assertLogs('morpheus.plugins', 'ERROR'):
            run_upgrades(_Registry(plugin))
        self.assertEqual(calls, ['1.0.0', '1.0.0'])

    def test_a_release_put_back_records_the_lower_version_and_runs_nothing(self):
        self.row('2.0.0')
        plugin, calls = upgrading('1.0.0')
        self.assertEqual(run_upgrades(_Registry(plugin)), [])
        self.assertEqual(calls, [])
        self.assertEqual(self.recorded(), '1.0.0')

        forward, forward_calls = upgrading('2.0.0')
        run_upgrades(_Registry(forward))
        self.assertEqual(forward_calls, ['1.0.0'], 'moving forward again runs the step again')

    def test_the_same_version_written_differently_runs_nothing(self):
        self.row('2.0')
        plugin, calls = upgrading('2.0.0')
        self.assertEqual(run_upgrades(_Registry(plugin)), [])
        self.assertEqual(calls, [])
        self.assertEqual(self.recorded(), '2.0.0')

    def test_a_release_after_its_pre_release_runs_the_step(self):
        self.row('2.0.0b1')
        plugin, calls = upgrading('2.0.0')
        run_upgrades(_Registry(plugin))
        self.assertEqual(calls, ['2.0.0b1'])

    def test_the_new_version_is_written_with_the_step_not_before(self):
        """A step that dies on the database leaves the old version, with no
        second write to put it back (that write can fail the same way)."""
        from django.db import DatabaseError

        self.row('1.0.0')
        plugin, _calls = upgrading('2.0.0')
        with (
            patch.object(type(plugin), 'on_upgrade', side_effect=DatabaseError('gone')),
            self.assertLogs('morpheus.plugins', 'ERROR'),
        ):
            self.assertEqual(run_upgrades(_Registry(plugin)), [])
        self.assertEqual(self.recorded(), '1.0.0')

    def test_a_fresh_database_gets_its_rows_and_runs_the_steps(self):
        """Boot found no table, so it wrote no rows: the first deploy writes
        them as the next boot would, records the version and runs the step."""
        from plugins.models import PluginConfig

        plugin, calls = upgrading('2.0.0')
        self.assertEqual(run_upgrades(_Registry(plugin)), [FIRST])
        self.assertEqual(calls, [''])
        row = PluginConfig.objects.get(plugin_name=FIRST)
        self.assertTrue(row.is_enabled)
        self.assertEqual(row.installed_version, '2.0.0')

        self.assertEqual(run_upgrades(_Registry(plugin)), [], 'the next deploy does nothing')

    def test_an_app_that_starts_off_waits_for_boot_to_write_its_row(self):
        from plugins.models import PluginConfig

        plugin, calls = upgrading('2.0.0')
        with patch.object(type(plugin), 'enabled_by_default', False):
            self.assertEqual(run_upgrades(_Registry(plugin)), [])
        self.assertEqual(calls, [])
        self.assertFalse(PluginConfig.objects.filter(plugin_name=FIRST).exists())

    def test_the_versions_are_read_from_the_primary(self):
        """With a replica, the router sends reads there; the compare-and-swap
        writes to the primary, so a lagging replica would hold the step back."""
        self.row('1.0.0')
        plugin, calls = upgrading('2.0.0')
        with self.settings(DATABASE_ROUTERS=[_ReadsFromAReplica()]):
            self.assertEqual(run_upgrades(_Registry(plugin)), [FIRST])
        self.assertEqual(calls, ['1.0.0'])
        self.assertEqual(self.recorded(), '2.0.0')

    def test_only_the_default_database_runs_upgrades(self):
        with patch('plugins.compat.run_upgrades') as run:
            after_migrate(sender=None, using='replica')
            run.assert_not_called()
            after_migrate(sender=None, using='default')
            run.assert_called_once_with()

    def test_every_migrate_runs_them(self):
        from django.db.models.signals import post_migrate

        uids = [key[0][0] for key in post_migrate.receivers]
        self.assertIn('plugins.run_upgrades', uids)
