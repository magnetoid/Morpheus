"""`enforce(...)` answers with a 403 response; a call that drops it denies nothing.

`core.authz.enforce(request, capability)` returns None when the caller may go on
and the 403 the decorator would send when not, so the call site has to return it:

    if (denied := enforce(request, 'seo.write')) is not None:
        return denied

feedback's `ticket_detail` wrote `enforce(request, 'system.write')` as a statement:
the 403 was built and thrown away, and with rbac enforcing, a role that could only
read system settings still changed every ticket's status (fixed in v0.164.0). The
test suite was green, because enforcement defaults to `log` and denies nothing.

This scans every Python file under core/ and plugins/ (tests excluded) for a call
to `enforce` whose value is discarded, and names the file and line.
"""

from __future__ import annotations

import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

_ROOTS = ('core', 'plugins')


def _is_test_path(path: Path) -> bool:
    return 'tests' in path.parts or path.name.startswith('test') or path.name == 'tests.py'


def _called_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ''


def discarded_enforce_calls(root: Path) -> list[str]:
    """`file:line` for each `enforce(...)` used as a bare statement under ``root``."""
    found = []
    for base in _ROOTS:
        for path in sorted((root / base).rglob('*.py')):
            rel = path.relative_to(root)
            if _is_test_path(rel) or 'migrations' in rel.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(rel))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Expr)
                    and isinstance(node.value, ast.Call)
                    and _called_name(node.value) == 'enforce'
                ):
                    found.append(f'{rel}:{node.lineno}')
    return found


class EnforceReturnUsedTests(SimpleTestCase):
    def test_no_call_to_enforce_discards_its_answer(self):
        found = discarded_enforce_calls(Path(settings.BASE_DIR))
        self.assertEqual(
            found,
            [],
            'enforce() returns the 403 to send; these calls drop it, so they deny '
            'nothing. Write `if (denied := enforce(request, cap)) is not None: return denied`:\n  '
            + '\n  '.join(found),
        )

    def test_the_scan_sees_a_discarded_call(self):
        """The guard reads real code: a bare call in a scratch tree is reported."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / 'plugins' / 'installed' / 'demo'
            app.mkdir(parents=True)
            (app / 'views.py').write_text(
                'from core.authz import enforce\n\n'
                'def view(request):\n'
                "    enforce(request, 'system.write')\n"
                "    if (denied := enforce(request, 'system.write')) is not None:\n"
                '        return denied\n'
            )
            (app / 'tests').mkdir()
            (app / 'tests' / 'test_x.py').write_text("enforce(None, 'x')\n")
            self.assertEqual(discarded_enforce_calls(root), ['plugins/installed/demo/views.py:4'])
