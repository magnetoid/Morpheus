"""The Celery worker must know every task the code enqueues.

A worker only executes tasks registered in its own process at boot:
``celery -A morph worker`` imports ``morph.celery``, then
``app.loader.init_worker()`` runs ``django.setup()`` and autodiscovers
``<installed app>.tasks``. A task defined anywhere else is registered in the
*web* process (which imports the module to call ``.delay()``) but never in the
worker, so every message is rejected as ``NotRegistered`` and the work is
silently dropped. ``core.emails.tasks.deliver_email`` shipped that way: every
transactional email and newsletter send was enqueued and discarded.

The suite runs eagerly in-process (where every module is already imported), so
it can never see this. Boot a fresh interpreter the way the worker does instead.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

_TASK_DECORATOR = re.compile(r'^@(shared_task|app\.task)\b', re.MULTILINE)
_MARKER = 'CELERY-WIRING-JSON:'

# Runs in a fresh interpreter. The trailing ``test`` argv selects the test
# settings branch (no broker/cache I/O); nothing here touches a database.
_WORKER_BOOT = f"""
import importlib, json, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'morph.settings')
from morph.celery import app
app.loader.init_worker()  # exactly what the worker does before consuming
late = {{}}
for mod in json.loads(sys.stdin.read()):
    before = set(app.tasks)
    importlib.import_module(mod)
    for name in set(app.tasks) - before:
        late[name] = mod
print({_MARKER!r} + json.dumps({{'late': late}}))
"""


def _task_modules() -> list[str]:
    """Every non-test module that defines a Celery task."""
    base = Path(settings.BASE_DIR)
    mods = []
    for top in ('core', 'plugins', 'api'):
        for path in (base / top).rglob('*.py'):
            rel = path.relative_to(base)
            if 'tests' in rel.parts or 'migrations' in rel.parts or path.name.startswith('test'):
                continue
            if not _TASK_DECORATOR.search(path.read_text(encoding='utf-8')):
                continue
            mod = '.'.join(rel.with_suffix('').parts)
            mods.append(mod.removesuffix('.__init__'))
    return sorted(mods)


def _boot_worker() -> dict:
    env = {**os.environ, 'DATABASE_URL': 'sqlite:///:memory:'}
    proc = subprocess.run(  # noqa: S603 — fixed interpreter + fixed script
        [sys.executable, '-c', _WORKER_BOOT, 'test'],
        input=json.dumps(_task_modules()),
        capture_output=True,
        text=True,
        cwd=settings.BASE_DIR,
        env=env,
        timeout=300,
        check=False,
    )
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith(_MARKER):
            return json.loads(line[len(_MARKER) :])
    raise AssertionError(f'worker boot failed (rc={proc.returncode}):\n{proc.stderr[-4000:]}')


class WorkerTaskRegistrationTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.boot = _boot_worker()

    def test_every_task_is_registered_at_worker_boot(self):
        late = self.boot['late']
        self.assertEqual(
            late,
            {},
            'Tasks the worker never registers (every .delay() is dropped as '
            "NotRegistered) — import their module from the owning app's tasks.py:\n"
            + '\n'.join(f'  {name}  ({mod})' for name, mod in sorted(late.items())),
        )

    def test_transactional_email_task_is_registered(self):
        # The one that silently ate every order email — named explicitly so a
        # future refactor of the generic scan above can't lose it.
        self.assertNotIn('core.emails.tasks.deliver_email', self.boot['late'])
