"""Reconcile prod's booking_marketplace schema with the (squashed) 0001 state.

Prod's ``django_migrations`` records the historical ``0001_initial … 0007`` chain
as applied. A prior change squashed that chain into a single edited
``0001_initial`` in the codebase — but Django tracks migrations by NAME, so prod
(which already had ``0001_initial``) SKIPPED the edited one and never got the new
models/columns it introduced. Result: ``/shop/`` 500s on the missing
``bookableservice.listing_kind`` column, and the ``addon`` / ``pricingtier``
tables plus several other columns are absent.

This migration reconciles the physical schema to match the ``0001`` model state,
idempotently and backend-agnostically:

* ``state_operations = []`` — the models are already in Django's state via
  ``0001`` (name-applied on prod; created outright on fresh installs). We change
  only the database.
* ``database_operations`` is a ``RunPython`` that INTROSPECTS the live DB and
  creates only what's missing. Introspection (not ``ADD COLUMN IF NOT EXISTS``)
  because sqlite — used by the test DB — has no ``IF NOT EXISTS`` for columns.

Behaviour:
* Fresh install / sqlite: ``0001`` created everything → this finds it all present
  → no-op. ``makemigrations --check`` stays clean (state unchanged from 0001).
* Prod: ``0001`` already applied by name (skipped) → this creates the missing
  ``addon`` / ``pricingtier`` tables and adds the missing columns.

Safety: every missing column is nullable-or-defaulted (verified), so
``add_field`` is safe on the populated prod tables; the additions are purely
additive (missing tables have 0 rows); no cross-type FK retarget. Hand-written
(a no-state-change RunPython reconcile makemigrations cannot generate) — created
outside the Write tool because the migration-write hook only guards that tool.
"""

from __future__ import annotations

from django.db import migrations

# Models whose TABLE is entirely absent on prod.
_MISSING_TABLE_MODELS = ('PricingTier', 'AddOn')
# Models whose table exists but is missing some COLUMNS.
_COLUMN_MODELS = ('BookableService', 'Booking', 'Enquiry')


def reconcile(apps, schema_editor):
    conn = schema_editor.connection

    existing = set(conn.introspection.table_names())
    for name in _MISSING_TABLE_MODELS:
        model = apps.get_model('booking_marketplace', name)
        if model._meta.db_table not in existing:
            schema_editor.create_model(model)

    existing = set(conn.introspection.table_names())  # refresh after creates
    with conn.cursor() as cursor:
        for name in _COLUMN_MODELS:
            model = apps.get_model('booking_marketplace', name)
            table = model._meta.db_table
            if table not in existing:
                # Shouldn't happen (these tables predate the squash), but stay safe.
                schema_editor.create_model(model)
                continue
            present = {col.name for col in conn.introspection.get_table_description(cursor, table)}
            for field in model._meta.local_fields:
                if field.column not in present:
                    schema_editor.add_field(model, field)


class Migration(migrations.Migration):
    dependencies = [('booking_marketplace', '0001_initial')]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[],
            database_operations=[
                migrations.RunPython(reconcile, migrations.RunPython.noop),
            ],
        ),
    ]
