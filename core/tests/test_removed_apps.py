"""Apps consolidation (docs/plans/apps-consolidation-2026-10.md): the apps that left the code
are gone. Wave 1's ten held no data and showed nothing; Wave 2 folded save_for_later into
wishlist. Their tables outlive them by one release."""

from __future__ import annotations

import importlib
from pathlib import Path

from django.conf import settings
from django.db import connection, models
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.db.migrations.state import ModelState, ProjectState
from django.test import SimpleTestCase, TransactionTestCase

from plugins.models import PluginConfig
from plugins.registry import app_registry

DROP = importlib.import_module('plugins.migrations.0002_drop_removed_app_tables')

REMOVED = (
    'one_click',
    'rich_post_purchase',
    'smart_shipping',
    'referrals',
    'experiments',
    'functions',
    'environments',
    'journal',
    'brand_kit',
    'lumina',
    # Wave 2: folded into wishlist (v0.123.0).
    'save_for_later',
)


class RemovedAppsTests(SimpleTestCase):
    def test_the_removed_apps_are_not_installed(self):
        installed = set(settings.INSTALLED_APPS) | set(settings.MORPHEUS_DEFAULT_APPS)
        for name in REMOVED:
            self.assertNotIn(f'plugins.installed.{name}', installed)
            self.assertIsNone(app_registry.get(name), name)

    def test_their_code_is_gone(self):
        root = Path(settings.BASE_DIR) / 'plugins' / 'installed'
        left = [
            n for n in REMOVED if (root / n / 'apps.py').exists() or (root / n / 'app.py').exists()
        ]
        self.assertEqual(left, [])


def _experiments_as_left() -> ProjectState:
    """The experiments tables as v0.121.0 left them, cut to the columns that tell its seed."""
    state = ProjectState()
    fields = [
        ('id', models.BigAutoField(primary_key=True)),
        ('key', models.SlugField(max_length=64, unique=True)),
        ('status', models.CharField(max_length=16, default='draft')),
    ]
    state.add_model(ModelState('experiments', 'Experiment', fields, {'db_table': 'experiment'}))
    for name, table in (
        ('Assignment', 'experiment_assignment'),
        ('Exposure', 'experiment_exposure'),
    ):
        fields = [
            ('id', models.BigAutoField(primary_key=True)),
            ('experiment', models.ForeignKey('experiments.Experiment', models.CASCADE)),
        ]
        state.add_model(ModelState('experiments', name, fields, {'db_table': table}))
    return state


class LeftoverTablesMigrationTests(TransactionTestCase):
    """plugins 0002 on an install that ran the experiments app's own migrations, which
    seeded a draft `checkout_flow` experiment everywhere."""

    def setUp(self):
        self.apps = _experiments_as_left().apps
        with connection.schema_editor() as editor:
            for name in ('Experiment', 'Assignment', 'Exposure'):
                editor.create_model(self.apps.get_model('experiments', name))
        self.addCleanup(self._remove)

    def _remove(self):
        names = connection.introspection.table_names()
        with connection.schema_editor() as editor:
            for name in ('Assignment', 'Exposure', 'Experiment'):
                model = self.apps.get_model('experiments', name)
                if model._meta.db_table in names:
                    editor.delete_model(model)

    def _seed(self, status='draft'):
        return self.apps.get_model('experiments', 'Experiment').objects.create(
            key='checkout_flow', status=status
        )

    def _migrate(self):
        state = MigrationLoader(connection).project_state(('plugins', '0001_initial'))
        with connection.schema_editor() as editor:
            for operation in DROP.Migration.operations:
                after = state.clone()
                operation.state_forwards('plugins', after)
                operation.database_forwards('plugins', editor, state, after)
                state = after

    def test_the_untouched_seed_does_not_keep_the_table(self):
        self._seed()
        self._migrate()
        self.assertNotIn('experiment', connection.introspection.table_names())

    def test_a_seed_someone_started_is_kept(self):
        self._seed(status='running')
        with self.assertLogs('morpheus.migrations', 'WARNING'):
            self._migrate()
        self.assertIn('experiment', connection.introspection.table_names())

    def test_a_seed_shown_to_visitors_is_kept(self):
        self.apps.get_model('experiments', 'Exposure').objects.create(experiment=self._seed())
        with self.assertLogs('morpheus.migrations', 'WARNING'):
            self._migrate()
        self.assertIn('experiment', connection.introspection.table_names())


SAVE_FOR_LATER_TABLES = {
    'SavedItem': 'save_for_later_saveditem',
    'PriceSnapshot': 'save_for_later_pricesnapshot',
    'SharedWishlist': 'save_for_later_sharedwishlist',
}


class SaveForLaterTablesTests(TransactionTestCase):
    """plugins 0003 on a store as v0.123.0 left it: save_for_later's three tables, its
    migration row and its switch."""

    def setUp(self):
        state = ProjectState()
        for name, table in SAVE_FOR_LATER_TABLES.items():
            fields = [('id', models.BigAutoField(primary_key=True))]
            state.add_model(ModelState('save_for_later', name, fields, {'db_table': table}))
        self.apps = state.apps
        with connection.schema_editor() as editor:
            for name in SAVE_FOR_LATER_TABLES:
                editor.create_model(self.apps.get_model('save_for_later', name))
        self.addCleanup(self._remove)
        recorder = MigrationRecorder(connection)
        recorder.record_applied('save_for_later', '0001_initial')
        self.addCleanup(recorder.migration_qs.filter(app='save_for_later').delete)
        PluginConfig.objects.create(plugin_name='save_for_later', is_enabled=False)

    def _remove(self):
        names = connection.introspection.table_names()
        with connection.schema_editor() as editor:
            for name, table in SAVE_FOR_LATER_TABLES.items():
                if table in names:
                    editor.delete_model(self.apps.get_model('save_for_later', name))

    def test_its_tables_migration_row_and_switch_go(self):
        drop = importlib.import_module('plugins.migrations.0003_drop_save_for_later_tables')
        state = MigrationLoader(connection).project_state(
            ('plugins', '0002_drop_removed_app_tables')
        )
        with connection.schema_editor() as editor:
            for operation in drop.Migration.operations:
                after = state.clone()
                operation.state_forwards('plugins', after)
                operation.database_forwards('plugins', editor, state, after)
                state = after
        names = connection.introspection.table_names()
        self.assertEqual([t for t in SAVE_FOR_LATER_TABLES.values() if t in names], [])
        self.assertFalse(
            MigrationRecorder(connection).migration_qs.filter(app='save_for_later').exists()
        )
        self.assertFalse(PluginConfig.objects.filter(plugin_name='save_for_later').exists())
