"""Migrations the previous release can still run on (safe deploys, part 2).

Putting the old code back after a deploy is safe only while the old code still
works on the new schema, and release 4 will do it automatically. ``review``
names the operations in a migration that the previous release would trip over:

- RemoveField and DeleteModel: it still reads the column or the table.
- RenameField, RenameModel and AlterModelTable: it still uses the old name.
- AddField of a NOT NULL column without ``db_default``: it inserts rows without
  that column, and Django drops a Python ``default`` from the table once the
  column exists, so those inserts fail.
- AlterField that makes a nullable column NOT NULL: it still writes NULL there,
  whatever default the new field has.
- RunSQL: nothing can tell what raw SQL does.
- RunPython of ``core.migration_ops.forget_apps``: it still records those apps'
  migrations and switches, and would find their tables with no record of them.

Such a change ships in two releases. To remove a column, the first takes the
field off the model in state only (``SeparateDatabaseAndState``, the
``RemoveField`` in ``state_operations``, plus an ``AlterField`` to ``null=True``
in ``database_operations`` when the column is NOT NULL, or the first release's
inserts fail); the second puts it back in state only and removes it with a
plain ``RemoveField`` (Django writes the right DDL for each database; sqlite
refuses a raw ``DROP COLUMN`` on an indexed column), and says why that is safe
on the migration, ``morpheus_contract = "nothing reads product.legacy_sku since
v0.119.0"``, which ``review`` accepts. A new NOT NULL column gets
``db_default``, or is added nullable and made NOT NULL in a later release once
every write fills it. Nothing done to a table the release itself creates is a
finding: the previous release has no such table. A squashed migration
(``replaces``) is not reviewed: it never runs where the migrations it replaces
already ran. Column type or length changes and new unique or check constraints
are not checked.

``manage.py release`` refuses to cut a release whose new migrations have
findings, and ``release --check`` (CI) fails on them. Spec:
docs/superpowers/specs/2026-10-19-safe-deploys-design.md, part 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django.db import migrations
from django.db.models import NOT_PROVIDED


@dataclass(frozen=True)
class Review:
    migration: str  # "app_label.name"
    findings: tuple[str, ...]
    contract: str  # the migration's morpheus_contract; '' when it has none

    @property
    def blocks(self) -> bool:
        return bool(self.findings) and not self.contract


def review(migration, state_before, new_models=None) -> Review:
    """What in ``migration`` the previous release would trip over, given the
    project state just before it runs. ``state_before`` is not changed.

    ``new_models`` holds the ``(app_label, model)`` tables this release creates,
    and the tables ``migration`` creates are added to it. The previous release has
    no such table, so nothing done to one can trip it."""
    name = f'{migration.app_label}.{migration.name}'
    contract = str(getattr(migration, 'morpheus_contract', '') or '').strip()
    if migration.replaces:
        return Review(name, (), contract)
    if new_models is None:
        new_models = set()
    found = _findings(migration.app_label, migration.operations, state_before.clone(), new_models)
    return Review(name, tuple(found), contract)


def _findings(app_label, operations, state, new_models) -> list[str]:
    found = []
    for op in operations:
        if isinstance(op, migrations.SeparateDatabaseAndState):
            # Only database_operations touch the tables; state_operations never do.
            found += _findings(app_label, op.database_operations, state.clone(), new_models)
        elif isinstance(op, migrations.CreateModel):
            new_models.add((app_label, op.name_lower))
        elif (app_label, _model_of(op)) not in new_models:
            finding = _finding(app_label, op, state)
            if finding:
                found.append(finding)
        op.state_forwards(app_label, state)
    return found


def _model_of(op) -> str | None:
    # A field operation names its model in model_name, a model operation in name;
    # RunSQL names none.
    return getattr(op, 'model_name_lower', None) or getattr(op, 'name_lower', None)


def _finding(app_label, op, state) -> str:  # noqa: PLR0911 — one rule per operation
    if isinstance(op, migrations.RemoveField):
        return (
            f'RemoveField {op.model_name}.{op.name}: the previous release still reads that column.'
        )
    if isinstance(op, migrations.DeleteModel):
        return f'DeleteModel {op.name}: the previous release still reads that table.'
    if isinstance(op, migrations.RenameField):
        return (
            f'RenameField {op.model_name}.{op.old_name} to {op.new_name}: '
            'the previous release still uses the old name.'
        )
    if isinstance(op, migrations.RenameModel):
        return (
            f'RenameModel {op.old_name} to {op.new_name}: '
            'the previous release still uses the old name.'
        )
    if isinstance(op, migrations.AlterModelTable):
        return f'AlterModelTable {op.name}: the previous release still uses the old table name.'
    if isinstance(op, migrations.RunSQL):
        return 'RunSQL: raw SQL cannot be checked.'
    if isinstance(op, migrations.RunPython) and getattr(op.code, 'morpheus_forgets', None):
        return (
            f'RunPython forget_apps({", ".join(op.code.morpheus_forgets)}): the previous '
            "release still records those apps' migrations and switches."
        )
    if isinstance(op, migrations.AddField) and _not_null_without_db_default(op.field):
        return (
            f'AddField {op.model_name}.{op.name}: NOT NULL without db_default, so the rows '
            'the previous release inserts fail.'
        )
    if isinstance(op, migrations.AlterField) and _becomes_not_null(app_label, op, state):
        return (
            f'AlterField {op.model_name}.{op.name}: becomes NOT NULL while the previous '
            'release still writes NULL there.'
        )
    return ''


def _not_null_without_db_default(field) -> bool:
    if field.many_to_many:
        return False  # a join table the previous release never touches
    return not field.null and field.db_default is NOT_PROVIDED


def _becomes_not_null(app_label, op, state) -> bool:
    try:
        before = state.models[app_label, op.model_name_lower].fields[op.name]
    except KeyError:
        return False  # not there before this migration: the AddField rule judged it
    return before.null and not op.field.null


def review_files(base_dir: Path, paths: list[str]) -> tuple[list[Review], list[str]]:
    """Review the migration files at ``paths`` (relative to ``base_dir``), as Django
    loads them. Also returns the paths it could not review: an app not installed in
    this process, or a migrations folder without ``__init__.py``. A gate that skipped
    those would pass while checking nothing."""
    from django.apps import apps
    from django.db.migrations.exceptions import NodeNotFoundError
    from django.db.migrations.loader import MigrationLoader

    loader = MigrationLoader(None, ignore_no_migrations=True)
    labels = {Path(config.path).resolve(): config.label for config in apps.get_app_configs()}
    found, unchecked = [], []
    for rel in paths:
        path = (base_dir / rel).resolve()
        key = (labels.get(path.parent.parent), path.stem)
        if key in loader.disk_migrations:
            found.append((key, rel))
        else:
            unchecked.append(rel)
    reviews, new_models = [], set()
    # By name, an app's migrations come in the order they run, so the tables an
    # earlier one creates are known when a later one changes them.
    for key, rel in sorted(found):
        try:
            state = loader.project_state(key, at_end=False)
        except NodeNotFoundError:
            unchecked.append(rel)
            continue
        reviews.append(review(loader.disk_migrations[key], state, new_models))
    return reviews, unchecked
