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

from django.db import migrations

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
