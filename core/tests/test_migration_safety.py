"""Migrations the previous release can still run on (safe deploys, part 2).

Each test builds a migration and the project state just before it, and asks
core.migration_safety.review what the previous release would trip over.
"""

from __future__ import annotations

from django.db import migrations, models
from django.db.migrations.state import ModelState, ProjectState
from django.test import SimpleTestCase

from core.migration_safety import review


def _state() -> ProjectState:
    state = ProjectState()
    state.add_model(
        ModelState(
            'shop',
            'thing',
            [
                ('id', models.AutoField(primary_key=True)),
                ('note', models.CharField(max_length=10, null=True)),
                ('title', models.CharField(max_length=10)),
            ],
        )
    )
    state.add_model(ModelState('shop', 'tag', [('id', models.AutoField(primary_key=True))]))
    return state


def _migration(*operations, **attrs):
    migration = migrations.Migration('0002_change', 'shop')
    migration.operations = list(operations)
    for name, value in attrs.items():
        setattr(migration, name, value)
    return migration


class UnsafeOperationTests(SimpleTestCase):
    def assert_blocks(self, operation, word):
        result = review(_migration(operation), _state())
        self.assertTrue(result.blocks, result)
        self.assertEqual(result.migration, 'shop.0002_change')
        self.assertIn(word, ' '.join(result.findings))

    def test_removing_a_field(self):
        self.assert_blocks(migrations.RemoveField('thing', 'note'), 'RemoveField thing.note')

    def test_deleting_a_model(self):
        self.assert_blocks(migrations.DeleteModel('tag'), 'DeleteModel tag')

    def test_renaming_a_field(self):
        self.assert_blocks(
            migrations.RenameField('thing', 'note', 'memo'), 'RenameField thing.note'
        )

    def test_renaming_a_model(self):
        self.assert_blocks(migrations.RenameModel('tag', 'label'), 'RenameModel tag')

    def test_renaming_a_table(self):
        self.assert_blocks(migrations.AlterModelTable('tag', 'shop_labels'), 'AlterModelTable tag')

    def test_raw_sql(self):
        self.assert_blocks(migrations.RunSQL('UPDATE shop_thing SET note = NULL'), 'RunSQL')

    def test_a_not_null_field_without_a_database_default(self):
        field = models.BooleanField(default=False)
        self.assert_blocks(migrations.AddField('thing', 'flag', field), 'AddField thing.flag')

    def test_a_nullable_column_made_not_null_even_with_a_default(self):
        field = models.CharField(max_length=10, default='')
        self.assert_blocks(migrations.AlterField('thing', 'note', field), 'AlterField thing.note')


class SafeOperationTests(SimpleTestCase):
    def assert_passes(self, *operations):
        result = review(_migration(*operations), _state())
        self.assertEqual(result.findings, ())
        self.assertFalse(result.blocks)

    def test_a_nullable_field(self):
        self.assert_passes(migrations.AddField('thing', 'flag', models.BooleanField(null=True)))

    def test_a_not_null_field_with_a_database_default(self):
        field = models.BooleanField(default=False, db_default=False)
        self.assert_passes(migrations.AddField('thing', 'flag', field))

    def test_a_many_to_many_field(self):
        self.assert_passes(migrations.AddField('thing', 'tags', models.ManyToManyField('shop.tag')))

    def test_a_new_model(self):
        self.assert_passes(
            migrations.CreateModel('box', [('id', models.AutoField(primary_key=True))])
        )

    def test_a_not_null_column_that_was_already_not_null(self):
        self.assert_passes(migrations.AlterField('thing', 'title', models.CharField(max_length=20)))

    def test_a_column_made_nullable(self):
        field = models.CharField(max_length=10, null=True)
        self.assert_passes(migrations.AlterField('thing', 'title', field))

    def test_python_data_changes(self):
        self.assert_passes(migrations.RunPython(migrations.RunPython.noop))


class SeparateStateTests(SimpleTestCase):
    def test_state_only_operations_are_not_flagged(self):
        move = migrations.SeparateDatabaseAndState(
            state_operations=[migrations.RemoveField('thing', 'note')], database_operations=[]
        )
        self.assertEqual(review(_migration(move), _state()).findings, ())

    def test_a_database_operation_inside_separate_state_is_reviewed(self):
        move = migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RemoveField('thing', 'note')]
        )
        self.assertTrue(review(_migration(move), _state()).blocks)


class ContractTests(SimpleTestCase):
    def test_a_contract_accepts_the_migration(self):
        reason = 'nothing reads thing.note since v0.119.0'
        result = review(
            _migration(migrations.RemoveField('thing', 'note'), morpheus_contract=reason), _state()
        )
        self.assertEqual(result.contract, reason)
        self.assertTrue(result.findings)  # still listed, so the release can show them
        self.assertFalse(result.blocks)

    def test_a_blank_contract_does_not_count(self):
        result = review(
            _migration(migrations.RemoveField('thing', 'note'), morpheus_contract='   '), _state()
        )
        self.assertEqual(result.contract, '')
        self.assertTrue(result.blocks)

    def test_a_squashed_migration_is_not_reviewed(self):
        result = review(
            _migration(
                migrations.RemoveField('thing', 'note'), replaces=[('shop', '0001_initial')]
            ),
            _state(),
        )
        self.assertEqual(result.findings, ())


class OrderTests(SimpleTestCase):
    def test_operations_are_judged_in_order(self):
        # Added as nullable, then made NOT NULL in the same migration: the
        # AlterField must see the nullable field the AddField just created.
        result = review(
            _migration(
                migrations.AddField('thing', 'code', models.CharField(max_length=5, null=True)),
                migrations.AlterField('thing', 'code', models.CharField(max_length=5)),
            ),
            _state(),
        )
        self.assertEqual(len(result.findings), 1)
        self.assertIn('AlterField thing.code', result.findings[0])

    def test_the_callers_state_is_left_alone(self):
        state = _state()
        review(_migration(migrations.RemoveField('thing', 'note')), state)
        self.assertIn('note', state.models['shop', 'thing'].fields)
