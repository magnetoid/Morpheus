"""core.migration_ops.DropLeftoverModel: a removed app's table goes when it is there and
empty (apps consolidation, Wave 1)."""

from __future__ import annotations

from unittest import skipIf

from django.db import connection, migrations, models
from django.db.migrations.state import ModelState, ProjectState
from django.test import TransactionTestCase

from core import migration_safety
from core.migration_ops import DropLeftoverModel

TABLE = 'wave1_leftover_probe'
PARENT = 'wave1_leftover_parent'
CHILD = 'wave1_leftover_child'


def _state() -> ProjectState:
    state = ProjectState()
    fields = [
        ('id', models.BigAutoField(primary_key=True)),
        ('note', models.CharField(max_length=20, default='')),
    ]
    state.add_model(ModelState('core', 'LeftoverProbe', fields, {'db_table': TABLE}))
    return state


class DropLeftoverModelTests(TransactionTestCase):
    def _create(self, rows=0):
        model = _state().apps.get_model('core', 'LeftoverProbe')
        with connection.schema_editor() as editor:
            editor.create_model(model)
        self.addCleanup(self._remove)
        for i in range(rows):
            model.objects.create(note=str(i))

    def _remove(self):
        if TABLE in connection.introspection.table_names():
            with connection.schema_editor() as editor:
                editor.delete_model(_state().apps.get_model('core', 'LeftoverProbe'))

    def _run(self):
        op = DropLeftoverModel(name='LeftoverProbe')
        before = _state()
        after = before.clone()
        op.state_forwards('core', after)
        with connection.schema_editor() as editor:
            op.database_forwards('core', editor, before, after)

    def test_an_empty_leftover_table_is_dropped(self):
        self._create()
        self._run()
        self.assertNotIn(TABLE, connection.introspection.table_names())

    def test_a_table_that_is_not_there_is_left_alone(self):
        # A store created after the app left, the test database, CI's Postgres job.
        self._run()
        self.assertNotIn(TABLE, connection.introspection.table_names())

    def test_a_table_with_rows_is_kept(self):
        self._create(rows=1)
        with self.assertLogs('morpheus.migrations', 'WARNING'):
            self._run()
        self.assertIn(TABLE, connection.introspection.table_names())

    def test_the_migration_gate_asks_for_a_contract(self):
        migration = migrations.Migration('0099_probe', 'core')
        migration.operations = [DropLeftoverModel(name='LeftoverProbe')]
        review = migration_safety.review(migration, _state())
        self.assertTrue(review.blocks)


def _linked_state(*, child=True) -> ProjectState:
    state = ProjectState()
    parent = [('id', models.BigAutoField(primary_key=True))]
    state.add_model(ModelState('core', 'LeftoverParent', parent, {'db_table': PARENT}))
    if child:
        fields = [
            ('id', models.BigAutoField(primary_key=True)),
            ('parent', models.ForeignKey('core.LeftoverParent', models.CASCADE)),
        ]
        state.add_model(ModelState('core', 'LeftoverChild', fields, {'db_table': CHILD}))
    return state


@skipIf(
    connection.vendor == 'sqlite', 'SQLite cannot drop a constraint in place — postgres-only path'
)
class KeptLeftoverForeignKeyTests(TransactionTestCase):
    """Once its model is gone, nothing deletes a kept table's rows before what they point
    at, so a link it kept would stop anyone deleting that customer, order or channel."""

    def _remove(self):
        names = connection.introspection.table_names()
        state = _linked_state()
        with connection.schema_editor() as editor:
            for name, table in (('LeftoverChild', CHILD), ('LeftoverParent', PARENT)):
                if table in names:
                    editor.delete_model(state.apps.get_model('core', name))

    def test_what_a_kept_row_points_at_can_still_be_deleted(self):
        before = _linked_state()
        parent_model = before.apps.get_model('core', 'LeftoverParent')
        child_model = before.apps.get_model('core', 'LeftoverChild')
        with connection.schema_editor() as editor:
            editor.create_model(parent_model)
            editor.create_model(child_model)
        self.addCleanup(self._remove)
        child_model.objects.create(parent=parent_model.objects.create())
        op = DropLeftoverModel(name='LeftoverChild')
        after = before.clone()
        op.state_forwards('core', after)
        with (
            self.assertLogs('morpheus.migrations', 'WARNING'),
            connection.schema_editor() as editor,
        ):
            op.database_forwards('core', editor, before, after)

        # The release after: no model knows the kept table, so nothing deletes its rows first.
        _linked_state(child=False).apps.get_model('core', 'LeftoverParent').objects.all().delete()

        with connection.cursor() as cursor:
            cursor.execute(f'SELECT count(*) FROM {CHILD}')  # noqa: S608  # nosec B608 — the test's own table
            self.assertEqual(cursor.fetchone()[0], 1)
