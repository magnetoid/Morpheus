#!/usr/bin/env python3
"""Guard: a plugin may only import another plugin it *declares* in `requires`.

Cross-plugin coupling is allowed — Morpheus is a serious commerce engine and a
vertical genuinely extends a base (book_product → catalog, agentic_checkout →
orders). But the coupling must be *declared*: `plugins/installed/<X>/app.py`
lists `requires = ['<Y>', ...]` for every sibling plugin X imports. An import of
a sibling that is NOT in `requires` is an **undeclared** coupling — the class of
bug the Charter warns about (a hidden dependency that breaks on disable/reorder,
a base plugin reaching *up* into a vertical, one concept silently owned by two
plugins). See CLAUDE.md "Plugin contract" + "Architectural compass".

This is the plugin-graph sibling of scripts/check_core_boundary.py, using the
same baseline-and-ratchet model:

  * Today's undeclared (importer → target) pairs are recorded in
    scripts/plugin_boundary_baseline.json.
  * A NEW undeclared cross-plugin import (pair not in the baseline) fails.
  * A baseline pair that no longer exists ALSO fails — when a coupling is
    repaid (moved to a hook/contribution, or the dep declared in `requires`),
    its baseline entry must be removed in the same change, so the allowlist can
    only shrink. That ratchet is the whole point.

Repay a pair either by (a) declaring the target in the importer's `requires`
(when it's a genuine, intended dependency), or (b) inverting the coupling
through the core.hooks event bus / a contribution API (when it isn't). Both
shrink the baseline.

Usage:
    python scripts/check_plugin_boundary.py           # check (CI)
    python scripts/check_plugin_boundary.py --save     # re-baseline (deliberate)

Run from the repo root.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = REPO_ROOT / 'plugins' / 'installed'
BASELINE = Path(__file__).resolve().parent / 'plugin_boundary_baseline.json'

PREFIX = 'plugins.installed'


def _is_test_path(p: Path) -> bool:
    parts = p.parts
    return 'tests' in parts or p.name.startswith('test_') or p.name == 'tests.py'


def _plugin_names() -> set[str]:
    return {p.name for p in PLUGINS_DIR.iterdir() if p.is_dir() and (p / '__init__.py').exists()}


def _requires_of(name: str) -> set[str]:
    """Parse the `requires = [...]` class attribute from a plugin's app.py."""
    f = PLUGINS_DIR / name / 'app.py'
    if not f.exists():
        return set()
    try:
        tree = ast.parse(f.read_text(encoding='utf-8'))
    except SyntaxError:
        return set()
    for node in ast.walk(tree):
        target = value = None
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == 'requires':
                    target, value = t.id, node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == 'requires'
        ):
            target, value = node.target.id, node.value
        if target and value is not None:
            try:
                return {str(x) for x in ast.literal_eval(value)}
            except (ValueError, SyntaxError):
                return set()
    return set()


def _target_plugin(module: str, plugins: set[str]) -> str | None:
    """`plugins.installed.orders.models` -> `orders` (if it's a real plugin)."""
    if module != PREFIX and not module.startswith(PREFIX + '.'):
        return None
    tail = module[len(PREFIX) + 1 :]
    head = tail.split('.', 1)[0] if tail else ''
    return head if head in plugins else None


def _scan() -> set[tuple[str, str]]:
    """Return {(importer_plugin, target_plugin)} for every UNDECLARED cross-plugin import."""
    plugins = _plugin_names()
    requires = {name: _requires_of(name) for name in plugins}
    found: set[tuple[str, str]] = set()
    for path in PLUGINS_DIR.rglob('*.py'):
        if _is_test_path(path):
            continue
        owner = path.relative_to(PLUGINS_DIR).parts[0]
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.ImportFrom):
                # Skip relative imports (node.level > 0) — those stay in-plugin.
                if node.level == 0 and node.module:
                    modules = [node.module]
            elif isinstance(node, ast.Import):
                modules = [a.name for a in node.names]
            for mod in modules:
                target = _target_plugin(mod, plugins)
                if target and target != owner and target not in requires.get(owner, set()):
                    found.add((owner, target))
    return found


def _load_baseline() -> set[tuple[str, str]]:
    if not BASELINE.exists():
        return set()
    raw = json.loads(BASELINE.read_text(encoding='utf-8'))
    return {(e['importer'], e['target']) for e in raw.get('allowed', [])}


def _save_baseline(found: set[tuple[str, str]]) -> None:
    payload = {
        '_comment': (
            'Baseline allowlist for scripts/check_plugin_boundary.py. These are the '
            'KNOWN undeclared plugin -> plugin imports being repaid over time. Repay a '
            'pair by declaring the target in the importer app.py `requires` (genuine '
            'dependency) OR inverting it through core.hooks / a contribution (it should '
            'not be a dependency); then remove the entry here. Only ever remove entries; '
            'never add. Regenerate with `python scripts/check_plugin_boundary.py --save` '
            'ONLY for a deliberate, reviewed change.'
        ),
        'allowed': [{'importer': i, 'target': t} for i, t in sorted(found)],
    }
    BASELINE.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')


def main(argv: list[str]) -> int:
    found = _scan()

    if '--save' in argv:
        _save_baseline(found)
        print(f'Wrote baseline with {len(found)} allowed undeclared plugin->plugin pair(s).')
        return 0

    baseline = _load_baseline()
    new = found - baseline
    stale = baseline - found

    if not new and not stale:
        print(f'OK: {len(found)} known undeclared plugin->plugin pair(s), no new ones. ✓')
        return 0

    if new:
        print('FAIL: new undeclared plugin -> plugin import(s).')
        print('      Declare the target in the importer app.py `requires`, or invert')
        print('      the coupling through core.hooks / a contribution API.')
        for i, t in sorted(new):
            print(f'  + {i}  ->  {t}')
    if stale:
        print('FAIL: baseline pairs no longer present — remove them from the allowlist')
        print(f'      ({BASELINE.relative_to(REPO_ROOT)}) so the ratchet keeps shrinking.')
        for i, t in sorted(stale):
            print(f'  - {i}  ->  {t}')
    return 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
