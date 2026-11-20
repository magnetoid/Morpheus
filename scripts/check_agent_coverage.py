#!/usr/bin/env python3
"""Guard: every change staff can make on a screen, Linda can make too (or says why not).

Janus is the brain of Morpheus (ADR 0039): a merchant action ships with its agent
tool in the same change, or the change says why an agent must not have it. This
script finds the merchant actions — staff-gated views that accept a POST — and
checks each one against the module's own map::

    AGENT_TOOLS = {
        'order_refund': 'orders.refund',          # the tool that does the same
        'staff_mfa_setup': 'none: a second factor is set up by the person',
    }

A key names a view in the same module; its value is a registered tool name, or
``none: <reason>``. The settings panel's save counts as covered by
``settings.set`` (P7's coercer reads the same schema).

What counts as a view: a module-level function under ``plugins/``, ``core/`` or
``api/`` (tests and migrations aside) that is staff-gated —
``@staff_member_required``, ``@staff_required``, ``@require_capability`` or a
``DashboardPage(view='dotted.path')`` the dashboard router serves to staff — and
accepts a POST: ``@require_POST``, ``@require_http_methods([... 'POST' ...])``,
or a body that reads ``request.POST``, ``request.FILES`` or ``request.body``, or
compares ``request.method`` with ``'POST'``.

A tool exists when some module registers it by name: ``@tool(name='x.y')``,
``Tool(name='x.y')`` or ``register_tool(...)`` with that name.

Baseline and ratchet, as ``scripts/check_plugin_boundary.py``:

  * today's uncovered views are in scripts/agent_coverage_baseline.json;
  * a NEW uncovered view fails;
  * a baseline entry that is covered now, or gone, ALSO fails, so the list can
    only shrink (``--save`` rewrites it, in the same change);
  * a map entry that names no view, or a tool that does not exist, fails.

Usage:
    python scripts/check_agent_coverage.py          # check (CI)
    python scripts/check_agent_coverage.py --save   # re-baseline (deliberate)
    python scripts/check_agent_coverage.py --list   # print what is uncovered

Run from the repo root. Under GitHub Actions the count also goes to the step
summary.
"""

from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE = Path(__file__).resolve().parent / 'agent_coverage_baseline.json'
ROOTS = ('plugins', 'core', 'api')
MAP_NAME = 'AGENT_TOOLS'
NONE_PREFIX = 'none:'

STAFF_DECORATORS = frozenset(
    {'staff_member_required', 'staff_required', 'require_capability', 'superuser_required'}
)
TOOL_CALLS = frozenset({'tool', 'Tool', 'register_tool'})
REQUEST_WRITE_ATTRS = frozenset({'POST', 'FILES', 'body'})


def _skip(rel: Path) -> bool:
    parts = rel.parts
    return (
        'tests' in parts
        or 'migrations' in parts
        or rel.name.startswith(('test_', 'tests_'))
        or rel.name == 'tests.py'
    )


def _modules() -> list[tuple[str, Path, ast.Module]]:
    out = []
    for root in ROOTS:
        for path in sorted((REPO_ROOT / root).rglob('*.py')):
            rel = path.relative_to(REPO_ROOT)
            if _skip(rel):
                continue
            try:
                tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(rel))
            except (SyntaxError, UnicodeDecodeError):
                continue
            module = '.'.join(rel.with_suffix('').parts)
            if module.endswith('.__init__'):
                module = module[: -len('.__init__')]
            out.append((module, rel, tree))
    return out


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ''


def _is_str(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _tool_names(modules) -> set[str]:
    names: set[str] = set()
    for _module, _rel, tree in modules:
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and _call_name(node) in TOOL_CALLS):
                continue
            for kw in node.keywords:
                if kw.arg == 'name' and _is_str(kw.value):
                    names.add(kw.value.value)
            if _call_name(node) == 'Tool' and node.args and _is_str(node.args[0]):
                names.add(node.args[0].value)
    return names


def _dashboard_page_views(modules) -> set[str]:
    """Dotted paths the dashboard router serves to staff."""
    paths: set[str] = set()
    for _module, _rel, tree in modules:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_name(node) == 'DashboardPage':
                for kw in node.keywords:
                    if kw.arg == 'view' and _is_str(kw.value):
                        paths.add(kw.value.value)
    return paths


def _accepts_post(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in fn.decorator_list:
        name = _call_name(dec)
        if name == 'require_POST':
            return True
        if name == 'require_http_methods' and "'POST'" in ast.unparse(dec):
            return True
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Attribute)
            and node.attr in REQUEST_WRITE_ATTRS
            and isinstance(node.value, ast.Name)
            and node.value.id == 'request'
        ):
            return True
        if isinstance(node, ast.Compare):
            text = ast.unparse(node)
            if 'request.method' in text and "'POST'" in text:
                return True
    return False


def _agent_map(tree: ast.Module, rel: Path, errors: list[str]) -> dict[str, str] | None:
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        if not any(isinstance(t, ast.Name) and t.id == MAP_NAME for t in targets):
            continue
        try:
            mapping = ast.literal_eval(value)
        except ValueError:
            errors.append(f'{rel}: {MAP_NAME} must be a literal dict of view name to tool')
            return None
        if not isinstance(mapping, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()
        ):
            errors.append(f'{rel}: {MAP_NAME} must map view names (str) to tools (str)')
            return None
        return mapping
    return None


def scan() -> tuple[list[str], list[str], int]:
    """(uncovered 'module:view' entries, errors, covered count)."""
    modules = _modules()
    tools = _tool_names(modules)
    pages = _dashboard_page_views(modules)
    uncovered: list[str] = []
    errors: list[str] = []
    covered = 0
    for module, rel, tree in modules:
        views = []
        for fn in tree.body:
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            staff = {_call_name(d) for d in fn.decorator_list} & STAFF_DECORATORS
            if (staff or f'{module}.{fn.name}' in pages) and _accepts_post(fn):
                views.append(fn.name)
        mapping = _agent_map(tree, rel, errors) or {}
        for key, value in sorted(mapping.items()):
            if key not in views:
                errors.append(f'{rel}: {MAP_NAME}[{key!r}] names no staff view that accepts POST')
            elif value.startswith(NONE_PREFIX):
                if len(value[len(NONE_PREFIX) :].strip()) < 10:
                    errors.append(f'{rel}: {MAP_NAME}[{key!r}] says none without a reason')
            elif value not in tools:
                errors.append(f'{rel}: {MAP_NAME}[{key!r}] names {value!r}, which no app registers')
        for view in views:
            if view in mapping:
                covered += 1
            else:
                uncovered.append(f'{module}:{view}')
    return sorted(uncovered), errors, covered


def _load_baseline() -> set[str]:
    if not BASELINE.exists():
        return set()
    return set(json.loads(BASELINE.read_text(encoding='utf-8')).get('uncovered', []))


def _summary(line: str) -> None:
    target = os.environ.get('GITHUB_STEP_SUMMARY')
    if target:
        with open(target, 'a', encoding='utf-8') as fh:
            fh.write(line + '\n')


def main(argv: list[str]) -> int:
    uncovered, errors, covered = scan()
    if '--list' in argv:
        print('\n'.join(uncovered))
        return 0
    if '--save' in argv:
        if errors:
            print('\n'.join(errors))
            return 1
        BASELINE.write_text(
            json.dumps(
                {
                    '_doc': 'Staff views that accept POST and have no agent tool yet. '
                    'Shrink only: see scripts/check_agent_coverage.py.',
                    'uncovered': uncovered,
                },
                indent=2,
            )
            + '\n',
            encoding='utf-8',
        )
        print(f'saved {len(uncovered)} uncovered staff write view(s) to {BASELINE.name}')
        return 0
    baseline = _load_baseline()
    new = [u for u in uncovered if u not in baseline]
    stale = sorted(baseline - set(uncovered))
    failed = False
    if errors:
        failed = True
        print('Agent coverage map errors:')
        print('\n'.join(f'  {e}' for e in errors))
    if new:
        failed = True
        print(
            'New staff views that accept POST with no agent tool. Give Linda the tool, '
            f"or add the view to the module's {MAP_NAME} with 'none: <reason>':"
        )
        print('\n'.join(f'  {u}' for u in new))
    if stale:
        failed = True
        print(
            'Baseline entries that are covered or gone now; remove them '
            '(python scripts/check_agent_coverage.py --save):'
        )
        print('\n'.join(f'  {s}' for s in stale))
    line = (
        f'Agent coverage: {covered} staff write view(s) covered, '
        f'{len(uncovered)} known without a tool (baseline shrinks only).'
    )
    _summary(line)
    if failed:
        return 1
    print(f'OK: {len(uncovered)} known uncovered staff write view(s), no new ones. ✓')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
