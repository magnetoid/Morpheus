"""Migration operations for taking apart what an earlier release removed
(apps consolidation, docs/plans/apps-consolidation-2026-10.md).

A removed app's code leaves in one release and its tables in the next, so the release
before still runs on the schema. ``DropLeftoverModel`` is that second step: a
``DeleteModel``, so the migration gate (core/migration_safety.py) asks for a
``morpheus_contract`` as it does for any other table it drops. It leaves a database
alone when the table is not there (a store created after the app left, the test
database) and keeps a table that still holds rows: they belong to someone, and a
person decides what happens to them. A kept table loses its foreign keys.
"""

from __future__ import annotations

import logging

from django.db import migrations, models

logger = logging.getLogger('morpheus.migrations')


class DropLeftoverModel(migrations.DeleteModel):
    reversible = False  # a dropped table comes back from a backup, not from a migration

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = from_state.apps.get_model(app_label, self.name)
        connection = schema_editor.connection
        table = model._meta.db_table
        if table not in connection.introspection.table_names():
            return
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT 1 FROM {schema_editor.quote_name(table)} LIMIT 1')  # noqa: S608  # nosec B608 — the migration's own table name
            if cursor.fetchone() is not None:
                # The rows stay; their links go. No model knows the table now, so nothing
                # deletes its rows first, and a link would stop anyone deleting the customer,
                # order or channel a row names. SQLite cannot drop a constraint in place.
                if connection.vendor != 'sqlite':
                    for name in schema_editor._constraint_names(model, foreign_key=True):
                        schema_editor.execute(schema_editor._delete_fk_sql(model, name))
                logger.warning(
                    'migrations: %s still holds rows, so it is kept; nothing reads it any more',
                    table,
                )
                return
        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def describe(self):
        return f'Drop the leftover table of {self.name} when it is there and empty'


def leftover_table_drops(tables: dict[str, str]) -> list:
    """The operations that drop a removed app's leftover tables, for a ``plugins`` app
    migration: each table enters this migration's state as an id-only model (its own app's
    state left with the app), then ``DropLeftoverModel`` drops it when it is there and
    empty. ``tables`` maps a name in this state to the table; name children first."""
    return [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name=name,
                    fields=[('id', models.BigAutoField(primary_key=True))],
                    options={'db_table': table},
                )
                for name, table in tables.items()
            ],
        ),
        *[DropLeftoverModel(name=name) for name in tables],
    ]


def forget_apps(*labels: str):
    """A ``RunPython`` function that deletes what ``django_migrations`` and ``PluginConfig``
    still hold for apps that left the code: an app given one of these names later starts
    from 0001, and no switch is left for an app that is gone. Use it only in the release
    after the code left: the release before would find the apps' tables but no record of
    creating them, and fail every boot. The migration gate sees it (``morpheus_forgets``)
    and asks for a ``morpheus_contract``, as for a drop."""

    def forget(apps, schema_editor):
        from django.db.migrations.recorder import MigrationRecorder  # noqa: PLC0415

        MigrationRecorder(schema_editor.connection).migration_qs.filter(app__in=labels).delete()
        apps.get_model('plugins', 'PluginConfig').objects.filter(plugin_name__in=labels).delete()

    forget.morpheus_forgets = labels
    return forget
