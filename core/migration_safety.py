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

Such a change ships in two releases. The first stops using the column (or
starts always writing it); the second makes the change and says why it is safe
on the migration, ``morpheus_contract = "nothing reads product.legacy_sku since
v0.119.0"``, which ``review`` accepts. A squashed migration (``replaces``) is not
reviewed: it never runs where the migrations it replaces already ran. Column type
or length changes and new unique or check constraints are not checked.

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


def review(migration, state_before) -> Review:
    """What in ``migration`` the previous release would trip over, given the
    project state just before it runs. ``state_before`` is not changed."""
    name = f'{migration.app_label}.{migration.name}'
    contract = str(getattr(migration, 'morpheus_contract', '') or '').strip()
    if migration.replaces:
        return Review(name, (), contract)
    found = _findings(migration.app_label, migration.operations, state_before.clone())
    return Review(name, tuple(found), contract)


def _findings(app_label, operations, state) -> list[str]:
    found = []
    for op in operations:
        if isinstance(op, migrations.SeparateDatabaseAndState):
            # Only database_operations touch the tables; state_operations never do.
            found += _findings(app_label, op.database_operations, state.clone())
        else:
            finding = _finding(app_label, op, state)
            if finding:
                found.append(finding)
        op.state_forwards(app_label, state)
    return found


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
    reviews, unchecked = [], []
    for rel in paths:
        path = (base_dir / rel).resolve()
        key = (labels.get(path.parent.parent), path.stem)
        migration = loader.disk_migrations.get(key)
        if migration is None:
            unchecked.append(rel)
            continue
        try:
            state = loader.project_state(key, at_end=False)
        except NodeNotFoundError:
            unchecked.append(rel)
            continue
        reviews.append(review(migration, state))
    return reviews, unchecked
