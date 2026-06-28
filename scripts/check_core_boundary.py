#!/usr/bin/env python3
"""Guard: `core/` must not import `plugins.installed.*` (wrong-direction coupling).

`core/` is the kernel of extension points; features live in plugins and reach core
through the hook bus / contribution APIs — never the reverse (see CLAUDE.md
"Architectural compass"). This script enforces that as a CI gate using a
baseline-and-ratchet model:

  * Today's known violations are recorded in scripts/core_boundary_baseline.json.
  * A NEW core->plugin import (not in the baseline) fails the build.
  * A baseline entry that no longer exists ALSO fails — when a refactor phase
    removes an import, it must remove the baseline entry in the same change, so
    the allowlist can only shrink. That ratchet is the whole point.

Usage:
    python scripts/check_core_boundary.py          # check (CI + pre-commit)
    python scripts/check_core_boundary.py --save    # re-baseline (deliberate only)

Run from the repo root.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = REPO_ROOT / 'core'
BASELINE = Path(__file__).resolve().parent / 'core_boundary_baseline.json'

PREFIX = 'plugins.installed'


def _is_test_path(p: Path) -> bool:
    parts = p.parts
    return 'tests' in parts or p.name.startswith('test_') or p.name == 'tests.py'


def _scan() -> set[tuple[str, str]]:
    """Return {(relative_path, imported_dotted_target)} for every core->plugin import."""
    found: set[tuple[str, str]] = set()
    for path in CORE_DIR.rglob('*.py'):
        if _is_test_path(path):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ''
                if mod == PREFIX or mod.startswith(PREFIX + '.'):
                    found.add((rel, mod))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == PREFIX or alias.name.startswith(PREFIX + '.'):
                        found.add((rel, alias.name))
    return found


def _load_baseline() -> set[tuple[str, str]]:
    if not BASELINE.exists():
        return set()
    raw = json.loads(BASELINE.read_text(encoding='utf-8'))
    return {(e['file'], e['imports']) for e in raw.get('allowed', [])}


def _save_baseline(found: set[tuple[str, str]]) -> None:
    payload = {
        '_comment': (
            'Baseline allowlist for scripts/check_core_boundary.py. These are the '
            'KNOWN core->plugin imports being retired phase by phase. Only ever '
            'remove entries (as the import is removed); never add. Regenerate with '
            '`python scripts/check_core_boundary.py --save` ONLY for a deliberate, '
            'reviewed change.'
        ),
        'allowed': [{'file': f, 'imports': m} for f, m in sorted(found)],
    }
    BASELINE.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')


def main(argv: list[str]) -> int:
    found = _scan()

    if '--save' in argv:
        _save_baseline(found)
        print(f'Wrote baseline with {len(found)} allowed core->plugin import(s).')
        return 0

    baseline = _load_baseline()
    new = found - baseline
    stale = baseline - found

    if not new and not stale:
        print(f'OK: {len(found)} known core->plugin import(s), no new ones. ✓')
        return 0

    if new:
        print('FAIL: new core -> plugins.installed import(s) — core/ must not import plugins.')
        print('      Use the core.hooks event bus or a contribution API instead.')
        for f, m in sorted(new):
            print(f'  + {f}  ->  {m}')
    if stale:
        print('FAIL: baseline entries no longer present — remove them from the allowlist')
        print(f'      ({BASELINE.relative_to(REPO_ROOT)}) so the ratchet keeps shrinking.')
        for f, m in sorted(stale):
            print(f'  - {f}  ->  {m}')
    return 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
