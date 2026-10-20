# Safe deploys, release 2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `manage.py release` refuses to cut a release when its new migrations would break the previous release, and CI fails on them. This keeps putting the old code back (release 4 will do it automatically) a safe move.

**Architecture:** A pure module, `core/migration_safety.py`, reviews one migration against the project state just before it runs. It returns its findings unless the migration carries a `morpheus_contract`. `review_files` loads the migration files a release adds, as Django loads them, and reviews each one. It reports the files it cannot load instead of skipping them.

The release command finds the added files with git: committed since the deployed state, staged, or not yet added. It turns findings into problems. `release` refuses before it writes anything, and `release --check` fails. That is the step CI already runs, with `RELEASE_CHECK_BASE` on a push.

**Deviations from the spec, on purpose:**

1. **Mechanism.** The spec names a CI step, `scripts/check_migration_safety.py`. We push straight to `main`, and a push is a deploy. A CI step therefore runs after the deploy has already started and stops nothing. `manage.py release` is the one step every deploy goes through before it is pushed (ADR 0032/0033). `release --check` is already the CI step, with the right base on PRs and pushes. So the check lives in those two commands, with no separate script.
2. **Two additions to the spec's list.**
   - **`AddField` of a NOT NULL column without `db_default`.** The previous release inserts rows without that column. Django adds the column with the Python `default`, then drops that default from the table (`BaseDatabaseSchemaEditor.add_field`: "Django usually does not use in-database defaults"), so those inserts fail. This is the most common way a migration breaks the version before it.
   - **`AlterModelTable`.** This is a table rename by another name.
3. **`AlterField` to NOT NULL is flagged even with a default.** The spec says "without a default". But the previous release's own model still has the field as nullable, so it writes NULL explicitly whenever the value is None. Neither a Python default nor a `db_default` on the new field changes that. The marker is how a migration says the old code never writes NULL there.
4. **Squashed migrations are not reviewed.** A migration that `replaces` others never runs where those migrations already ran.

Not covered, and said so in the docs: column type or length changes, and new unique or check constraints. Both can break old code, but less often. The marker makes the check easy to satisfy wherever it is too strict.

**Tech Stack:** Python 3.12, Django 6.1 migration framework (`MigrationLoader`, `ProjectState`, migration operations), git.

**Spec:** `docs/superpowers/specs/2026-10-19-safe-deploys-design.md`, part 2 ("Migrations the previous version can run on"). This is release 2 of its "Order of delivery". Release 1 shipped as v0.118.0. Releases 3 (restore) and 4 (automatic rollback) get their own plans.

## Global Constraints

- From the spec: the check "fails on any operation the previous release could trip over: `RemoveField`, `DeleteModel`, `RenameField`, `RenameModel`, an `AlterField` that makes a column `NOT NULL` without a default, and raw SQL."
- From the spec: "Such a change ships in two releases: the first stops using the column, the second removes it and says so on the migration (`morpheus_contract = "<why it is safe: nothing reads it since vX.Y.Z>"`), which the check accepts."
- From the spec's testing: "the migration checker on safe, unsafe and marked migrations".
- The marker is exactly the class attribute `morpheus_contract` on the `Migration`. Only a non-empty, non-whitespace string counts.
- A migration file the check cannot load fails the check (fail closed), and the message names the file. A gate that skips what it cannot read passes while checking nothing.
- No new dependency. `core/` imports nothing from `plugins.installed.*`.
- The release is `v0.119.0` (MINOR), made with `manage.py release`. (`v0.118.1`, the dashboard width fix, ships before it.)
- Tests run with `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test <labels>`. The full suite also needs `MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress'`.
- Use ruff 0.15.8 (`.venv/bin/ruff`). Commit messages end with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Work on branch `feat/safe-deploys-2` in `/Users/magnetoid/coding/morph`. Owner rule: no worktree. Push once, in Task 4.

## Review Focus

1. **An unsafe operation inside `SeparateDatabaseAndState`.** A `RemoveField` in its `database_operations` must be caught. One in `state_operations` alone changes no table and must not be flagged. Pinned by Task 1 (`test_a_database_operation_inside_separate_state_is_reviewed`, `test_state_only_operations_are_not_flagged`) and Task 2 (`test_a_state_only_move_in_the_repo_passes`, against `agent_core/0004`).
2. **A new migration this process does not load.** An app not installed here, such as `booking_marketplace` without `MORPHEUS_EXTRA_APPS`, or a `migrations/` folder with no `__init__.py`. It must fail the check with the file's name, never pass. Pinned by Task 2, `test_a_file_django_does_not_load_is_not_waved_through`.
3. **A migration that is not committed yet when the release is cut.** A staged or untracked migration still ships with the next push, so it must be checked. Pinned by Task 2, `test_staged_and_untracked_migrations_are_found`.
4. **A blank `morpheus_contract`.** `"   "` must not count as a reason. Pinned by Task 1, `test_a_blank_contract_does_not_count`.
5. **Two operations on one field in the same migration.** For example, `AddField(null=True)` then `AlterField(null=False)`. They must be judged in order, with the state moved forward between them. Pinned by Task 1, `test_operations_are_judged_in_order`.

---

### Task 1: The review rules (`core/migration_safety.py`)

**Files:**
- Create: `core/migration_safety.py`
- Test: `core/tests/test_migration_safety.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces:
  - `core.migration_safety.Review`, a frozen dataclass with:
    - `migration: str` (`"app_label.name"`)
    - `findings: tuple[str, ...]`
    - `contract: str` (`''` when there is none)
    - the property `blocks -> bool`: true when there are findings and no contract
  - `core.migration_safety.review(migration, state_before) -> Review`

- [ ] **Step 1: Branch**

```bash
cd /Users/magnetoid/coding/morph && git checkout -b feat/safe-deploys-2
```

- [ ] **Step 2: Write the failing tests**

Create `core/tests/test_migration_safety.py`:

```python
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
        self.assert_blocks(migrations.RenameField('thing', 'note', 'memo'), 'RenameField thing.note')

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
            _migration(migrations.RemoveField('thing', 'note'), replaces=[('shop', '0001_initial')]),
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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_migration_safety -v 2 2>&1 | tail -8`

Expected: the module fails to import with `ModuleNotFoundError: No module named 'core.migration_safety'`. The exact wording may say `ImportError`; the cause must be that the module is missing.

- [ ] **Step 4: Create `core/migration_safety.py`**

```python
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
        return f'RemoveField {op.model_name}.{op.name}: the previous release still reads that column.'
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_migration_safety -v 2 2>&1 | tail -6`

Expected: `Ran 22 tests` … `OK`.

- [ ] **Step 6: Lint and commit**

```bash
.venv/bin/ruff check core/migration_safety.py core/tests/test_migration_safety.py \
 && .venv/bin/ruff format core/migration_safety.py core/tests/test_migration_safety.py \
 && git add core/migration_safety.py core/tests/test_migration_safety.py \
 && git commit -m "feat(deploys): name the migration operations the previous release would trip over

core.migration_safety.review flags RemoveField, DeleteModel, renames, raw SQL,
a NOT NULL AddField without db_default and an AlterField to NOT NULL, unless
the migration says why it is safe in morpheus_contract.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: The gate in `manage.py release` and `release --check`

**Files:**
- Modify: `core/migration_safety.py`. Add `review_files`.
- Modify: `core/management/commands/release.py`. Add `_MIGRATION_FILE`, `_added_migration_files`, `_migration_report` and `_report_migrations`, and call them from `_release` and `_check`.
- Test: `core/tests/test_migration_gate.py`

**Interfaces:**
- Consumes (Task 1): `review(migration, state_before) -> Review`, and `Review.blocks`, `.findings` and `.contract`.
- Produces:
  - `core.migration_safety.review_files(base_dir: Path, paths: list[str]) -> tuple[list[Review], list[str]]`. The second item lists the paths that could not be reviewed.
  - `core.management.commands.release._added_migration_files(base: str) -> list[str]`
  - `core.management.commands.release._migration_report(base: str) -> tuple[list[str], list[str]]`, returning the problems and the accepted contracts.

- [ ] **Step 1: Write the failing tests**

Create `core/tests/test_migration_gate.py`:

```python
"""The release gate for migrations the previous release would trip over.

`manage.py release` refuses, and `release --check` (CI) fails, when a migration
the release adds would break the version before it (core/migration_safety.py).
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from core.migration_safety import Review, review_files

_BASE = Path(settings.BASE_DIR)
_REMOVES_FIELDS = 'core/migrations/0014_remove_storesettings_guided_ux_mode_and_more.py'
_STATE_ONLY_MOVE = 'plugins/installed/agent_core/migrations/0004_remove_agentapprovalrequest_decided_by_and_more.py'
_NEW_MODEL = 'core/migrations/0024_deployevent.py'
_RELEASE = 'core.management.commands.release'


class ReviewFilesTests(SimpleTestCase):
    def test_a_migration_that_removes_fields_blocks(self):
        reviews, unchecked = review_files(_BASE, [_REMOVES_FIELDS])
        self.assertEqual(unchecked, [])
        [result] = reviews
        self.assertTrue(result.blocks)
        self.assertIn('RemoveField storesettings.', ' '.join(result.findings))

    def test_a_state_only_move_in_the_repo_passes(self):
        reviews, unchecked = review_files(_BASE, [_STATE_ONLY_MOVE])
        self.assertEqual((unchecked, [r.findings for r in reviews]), ([], [()]))

    def test_a_new_model_passes(self):
        reviews, _ = review_files(_BASE, [_NEW_MODEL])
        self.assertFalse(reviews[0].blocks)

    def test_a_file_django_does_not_load_is_not_waved_through(self):
        path = 'plugins/installed/not_an_app/migrations/0001_initial.py'
        reviews, unchecked = review_files(_BASE, [path])
        self.assertEqual((reviews, unchecked), ([], [path]))


class AddedMigrationFilesTests(SimpleTestCase):
    """Against a throwaway repo, so it never depends on this checkout's state."""

    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        self.repo = Path(tmp)
        (self.repo / 'shop' / 'migrations').mkdir(parents=True)
        self.git('init', '-q', '-b', 'main')
        self.write('shop/migrations/0001_initial.py')
        self.git('add', '.')
        self.git('commit', '-qm', 'one')
        self.base = self.git('rev-parse', 'HEAD')
        patcher = mock.patch(f'{_RELEASE}._base_dir', return_value=self.repo)
        patcher.start()
        self.addCleanup(patcher.stop)

    def git(self, *args):
        env = {**os.environ, 'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@t',
               'GIT_COMMITTER_NAME': 't', 'GIT_COMMITTER_EMAIL': 't@t'}  # fmt: skip
        out = subprocess.run(
            ['git', *args], cwd=self.repo, check=True, capture_output=True, text=True, env=env
        )
        return out.stdout.strip()

    def write(self, rel):
        (self.repo / rel).write_text('# a migration\n')

    def test_staged_and_untracked_migrations_are_found(self):
        from core.management.commands.release import _added_migration_files

        self.write('shop/migrations/0002_committed.py')
        self.git('add', '.')
        self.git('commit', '-qm', 'two')
        self.write('shop/migrations/0003_staged.py')
        self.git('add', 'shop/migrations/0003_staged.py')
        self.write('shop/migrations/0004_untracked.py')
        self.write('shop/notes.py')  # not a migration
        self.assertEqual(
            _added_migration_files(self.base),
            [
                'shop/migrations/0002_committed.py',
                'shop/migrations/0003_staged.py',
                'shop/migrations/0004_untracked.py',
            ],
        )


class ReleaseGateTests(SimpleTestCase):
    def setUp(self):
        for target, value in (('_diff_base', 'HEAD'), ('_added_migration_files', [_REMOVES_FIELDS])):
            patcher = mock.patch(f'{_RELEASE}.{target}', return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_release_check_fails_on_an_unsafe_migration(self):
        err = io.StringIO()
        with self.assertRaises(CommandError):
            call_command('release', check=True, stdout=io.StringIO(), stderr=err)
        self.assertIn('core.0014_remove_storesettings_guided_ux_mode_and_more: RemoveField', err.getvalue())
        self.assertIn('morpheus_contract', err.getvalue())

    def test_release_refuses_before_writing_anything(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        settings_copy, notes_copy = tmp / 'settings.py', tmp / 'RELEASE_NOTES.md'
        shutil.copy(_BASE / 'morph/settings.py', settings_copy)
        shutil.copy(_BASE / 'docs/RELEASE_NOTES.md', notes_copy)
        before = (settings_copy.read_text(), notes_copy.read_text())
        with (
            mock.patch(f'{_RELEASE}._settings_path', return_value=settings_copy),
            mock.patch(f'{_RELEASE}._notes_path', return_value=notes_copy),
            self.assertRaises(CommandError),
        ):
            call_command('release', '--patch', 'A change', stdout=io.StringIO(), stderr=io.StringIO())
        self.assertEqual((settings_copy.read_text(), notes_copy.read_text()), before)

    def test_a_contract_lets_the_release_through_and_is_shown(self):
        accepted = Review('core.0099_drop_x', ('RemoveField thing.x: …',), 'nothing reads x since v0.119.0')
        out = io.StringIO()
        with mock.patch('core.migration_safety.review_files', return_value=([accepted], [])):
            call_command('release', check=True, stdout=out, stderr=io.StringIO())
        self.assertIn('core.0099_drop_x: nothing reads x since v0.119.0', out.getvalue())
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_migration_gate -v 2 2>&1 | tail -8`

Expected: the module fails to import with `ImportError: cannot import name 'review_files' from 'core.migration_safety'`.

- [ ] **Step 3: Add `review_files` to `core/migration_safety.py`**

Add `from pathlib import Path` to the imports. Append:

```python
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
```

- [ ] **Step 4: Wire it into `core/management/commands/release.py`**

Add, after `versioned_changes`:

```python
_MIGRATION_FILE = re.compile(r'/migrations/\d{4}_\w+\.py$')


def _added_migration_files(base: str) -> list[str]:
    """Migration files new since ``base``: committed, staged, or not added to git
    yet. One left uncommitted when the release is cut still ships with the next push."""
    outputs = (
        _git('diff', '--name-only', '--diff-filter=AR', f'{base}...HEAD'),
        _git('diff', '--name-only', '--diff-filter=AR', '--cached'),
        _git('ls-files', '--others', '--exclude-standard'),
    )
    names = {name for out in outputs for name in (out or '').splitlines()}
    return sorted(name for name in names if _MIGRATION_FILE.search(name))


def _migration_report(base: str) -> tuple[list[str], list[str]]:
    """The release's new migrations, reviewed (core/migration_safety.py): the
    problems that stop it, and the contracts that let a flagged migration through."""
    from core import migration_safety

    reviews, unchecked = migration_safety.review_files(_base_dir(), _added_migration_files(base))
    problems = [f'{r.migration}: {finding}' for r in reviews if r.blocks for finding in r.findings]
    if problems:
        problems.append(
            'Ship such a change in two releases (first stop using it, then change it), and '
            "mark the second migration with morpheus_contract = '<why it is safe>'."
        )
    problems += [
        f'{path}: not checked, because Django does not load it here (its app is not '
        'installed: set MORPHEUS_EXTRA_APPS; or its migrations folder has no __init__.py).'
        for path in unchecked
    ]
    accepted = [f'{r.migration}: {r.contract}' for r in reviews if r.findings and r.contract]
    return problems, accepted
```

`release.py` already imports `re` (for `_SEMVER_RE`).

In `Command`, add one helper:

```python
    def _report_migrations(self, base: str) -> list[str]:
        problems, accepted = _migration_report(base)
        for line in accepted:
            self.stdout.write(self.style.SUCCESS(f'  ✓ migration contract — {line}'))
        return problems
```

In `_release`, insert right after the `if not summary:` check, before anything is read or written:

```python
        base = _diff_base()
        if base is None:
            self.stdout.write(
                self.style.WARNING('  ! no origin/main to diff — skipped the migration check')
            )
        else:
            problems = self._report_migrations(base)
            if problems:
                for problem in problems:
                    self.stderr.write(self.style.ERROR(f'  ✗ {problem}'))
                raise CommandError(
                    'These migrations would break the previous release; nothing was written.'
                )
```

In `_check`, at the end of the `else:` branch that diffs against `base` (after the missing-bump check), add:

```python
            problems += self._report_migrations(base)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_migration_gate core.tests.test_migration_safety core.tests.test_release_command -v 2 2>&1 | tail -6`

Expected: `OK`, with every existing `test_release_command` test still passing.

Then run the real check on this branch: `DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py release --check 2>&1 | tail -3`

Expected: `✓ version … in sync with RELEASE_NOTES`. This branch adds no migration, so there is nothing to flag.

- [ ] **Step 6: Lint and commit**

```bash
.venv/bin/ruff check core/migration_safety.py core/management/commands/release.py core/tests/test_migration_gate.py \
 && .venv/bin/ruff format core/migration_safety.py core/management/commands/release.py core/tests/test_migration_gate.py \
 && git add core/migration_safety.py core/management/commands/release.py core/tests/test_migration_gate.py \
 && git commit -m "feat(deploys): manage.py release refuses migrations the previous release would trip over

The release gate reviews the migrations a release adds (committed since the
deployed state, staged, or untracked) and refuses before writing anything;
release --check, which CI runs, fails the same way. A file Django does not load
here fails the check instead of passing it, and a migration's morpheus_contract
lets a flagged change through and is printed.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Docs, the full suite and the release commit

**Files:**
- Modify: `CLAUDE.md`. Add a convention after the "a deploy that migrates is backed up first" paragraph.
- Modify: `docs/PLUGIN_DEVELOPMENT.md`, `## 6. Models, migrations, indexes`.
- Modify: `docs/UPDATING.md`, the "Still to come" list in `## Safe deploys (v0.118.0)`.
- Modify (by `manage.py release`): `morph/settings.py`, `docs/RELEASE_NOTES.md`

- [ ] **Step 1: The docs**

In `CLAUDE.md`, insert after the paragraph that begins "**Convention — a deploy that migrates is backed up first (v0.118.0).**":

```markdown
**Convention — a migration leaves the previous release working (v0.119.0).** Putting the
old code back (by hand now, automatically from safe-deploys release 4) is safe only while
the old code still runs on the new schema. `manage.py release` refuses, and `release
--check` (CI) fails, when a migration the release adds would break it
(`core/migration_safety.py`). The flagged operations are:
- `RemoveField` and `DeleteModel`;
- renames, including `AlterModelTable`;
- `RunSQL`;
- an `AlterField` that makes a nullable column NOT NULL (even with a default: the old
  model still writes NULL);
- an `AddField` of a NOT NULL column without `db_default`. Django drops a Python
  `default` from the table once the column exists, so the old code's inserts fail. Add
  booleans as `default=False, db_default=False`.

Such a change ships in two releases: first stop using the column (or start always
writing it), then change it with `morpheus_contract = "<why it is safe>"` on the
migration. A migration file Django does not load fails the check rather than passing
it, so run `release` with `MORPHEUS_EXTRA_APPS` when a release touches an opt-in app.
Guarded by `core/tests/test_migration_safety.py` and `test_migration_gate.py`.
```

In `docs/PLUGIN_DEVELOPMENT.md`, under `## 6. Models, migrations, indexes`, add this bullet after "Run `python manage.py makemigrations --check --dry-run` in CI to catch missing migrations.":

```markdown
* A migration must leave the previous release working, because the store may go back to it. `manage.py release` refuses one that removes or renames a column or table, runs raw SQL, makes a nullable column NOT NULL, or adds a NOT NULL column without `db_default` (`core/migration_safety.py`). Ship such a change in two releases, the second marked `morpheus_contract = "<why it is safe>"`; add a boolean as `models.BooleanField(default=False, db_default=False)`.
```

In `docs/UPDATING.md`, replace the line `- a CI check that a release's migrations are safe for the previous version;` with:

```markdown
- ~~a check that a release's migrations are safe for the previous version~~: shipped in
  v0.119.0. `manage.py release` refuses them and `release --check` fails on them
  (`core/migration_safety.py`), unless the migration says why in `morpheus_contract`;
```

- [ ] **Step 2: The full suite and the CI gates**

```bash
DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress' .venv/bin/python manage.py test > /private/tmp/claude-502/-Users-magnetoid-coding-morph/ea077053-0f76-43ff-a44e-08fa22583365/scratchpad/r2-suite.log 2>&1; grep -E '^Ran |^OK|^FAILED' /private/tmp/claude-502/-Users-magnetoid-coding-morph/ea077053-0f76-43ff-a44e-08fa22583365/scratchpad/r2-suite.log
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/python scripts/check_core_boundary.py && .venv/bin/python scripts/check_plugin_boundary.py && .venv/bin/python scripts/check_plugin_standard.py && DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py check && DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py makemigrations --check --dry-run
```

Expected: `OK` (10 skipped), and every gate passes.

- [ ] **Step 3: Commit the docs and cut the release**

```bash
git add CLAUDE.md docs/PLUGIN_DEVELOPMENT.md docs/UPDATING.md && git commit -m "docs: safe deploys, part 2 (migrations the previous release can run on)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
DATABASE_URL='sqlite:///:memory:' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress' .venv/bin/python manage.py release --minor "Safe deploys, part 2: a release whose database changes would break the version before it is refused" \
  -m "Before a new version is released, its database changes are checked against the version now running: a change that would stop that version working if the store went back to it (a removed or renamed column or table, raw SQL, a column made required) stops the release until it is split in two or marked with the reason it is safe." \
  --commit
git commit --amend -m "chore(release): v0.119.0 — Safe deploys, part 2: a release whose database changes would break the version before it is refused

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py release --check
```

Expected: `v0.118.1 -> v0.119.0`, and `release --check` passes. The new gate runs on this release itself and finds no migration.

---

### Task 4: Ship and confirm (after the final whole-branch review)

**Files:** none changed.

- [ ] **Step 1: Merge and push**

```bash
git checkout main && git merge --ff-only feat/safe-deploys-2 && git push origin main && git branch -d feat/safe-deploys-2
```

- [ ] **Step 2: Wait for the stores and for CI**

Run: `SMOKE_DEADLINE_SECS=2400 scripts/deploy_smoke.sh v0.119.0`

Expected: `SMOKE OK — every store serves v0.119.0`.

Then run: `gh run list --workflow ci.yml --limit 1`

Expected: the push's run is `completed success`. Its `release --check` step ran the new gate with `RELEASE_CHECK_BASE` on the push.

- [ ] **Step 3: Record the outcome in memory**

Update `releases-2026-10-19.md` in the memory folder: v0.119.0 shipped, so releases 3 (restore) and 4 (rollback) remain. Add the rule for writing migrations from now on: add a boolean with `db_default`, and ship removals in two releases.
