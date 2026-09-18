#!/usr/bin/env python3
"""Guard: every app in `plugins/installed/` meets the plugin contract.

The contract is written in docs/PLUGIN_DEVELOPMENT.md and CLAUDE.md; this is
the part of it a machine can check. It exists because the expensive plugin bugs
in this repo's history were never subtle — they were a missing file nobody
looked for:

  * `migrations/` without `__init__.py` is INVISIBLE to Django. Five apps
    shipped that way; their tables were never created on prod while every local
    test passed, because Django syncdb-creates tables for apps it believes have
    no migrations. `makemigrations --check` is clean for the same reason, so
    the usual gate proves nothing (v0.41.1).
  * An `app.py` whose `name` drifts from its directory breaks config lookup,
    the Apps catalogue and the disable path, all silently.
  * `requires` naming an app that does not exist makes the dependency sort
    drop the plugin at boot.

Checked here (AST only — no Django boot, so it runs in a fraction of a second
and cannot be fooled by import side effects):

    structure   __init__.py, apps.py with a matching AppConfig, app.py manifest
    manifest    name == directory, label, semver version, description
    graph       every `requires` entry is a real app, and not itself
    models      models => migrations package + an initial migration + has_models
    settings    listed in MORPHEUS_DEFAULT_APPS
    tests       a tests package with at least one test module

NOT checked here, because no AST can see it — these stay human review, and the
docs say so: whether a surface is *contributed* rather than hard-coded into a
shell, whether a disabled app really leaves no trace, and whether a new concept
should have been a new app at all.

Baseline-and-ratchet, like its two siblings (check_core_boundary.py,
check_plugin_boundary.py): today's violations live in
scripts/plugin_standard_baseline.json, a NEW violation fails, and a baseline
entry that no longer reproduces ALSO fails, so the list can only shrink.

Usage:
    python scripts/check_plugin_standard.py            # check (CI)
    python scripts/check_plugin_standard.py --report   # human summary, never fails
    python scripts/check_plugin_standard.py --save     # re-baseline (deliberate)

Run from the repo root.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALLED = ROOT / 'plugins' / 'installed'
SETTINGS = ROOT / 'morph' / 'settings.py'
BASELINE = Path(__file__).resolve().parent / 'plugin_standard_baseline.json'

SEMVER = re.compile(r'^\d+\.\d+\.\d+([ab]\d+)?$')

# Rule id → one-line description, shown in the report and in failures.
RULES = {
    'structure.init': '__init__.py is missing — the directory is not a Python package',
    'structure.apps': 'apps.py must define an AppConfig',
    'structure.appconfig_name': "AppConfig.name must be 'plugins.installed.<dir>'",
    'structure.manifest': 'app.py must define a MorpheusPlugin subclass',
    'manifest.name': 'manifest `name` must equal the directory name',
    'manifest.label': 'manifest `label` is required (merchant-facing name)',
    'manifest.version': 'manifest `version` must look like 1.2.3',
    'manifest.description': 'manifest `description` is required',
    'graph.requires_unknown': '`requires` names an app that does not exist',
    'graph.requires_self': '`requires` names the app itself',
    'models.migrations_package': 'migrations/ exists without __init__.py — Django cannot see it',
    'models.migrations_missing': 'models are defined but there is no migrations/ package',
    'models.no_initial': 'migrations/ has no initial migration',
    'models.has_models_flag': 'models are defined but the manifest does not set has_models = True',
    'settings.not_registered': 'not listed in morph/settings.py:MORPHEUS_DEFAULT_APPS',
    'tests.missing': 'no tests — at least one test module is required',
}


def _manifest_bases(node: ast.ClassDef) -> list[str]:
    out = []
    for b in node.bases:
        if isinstance(b, ast.Name):
            out.append(b.id)
        elif isinstance(b, ast.Attribute):
            out.append(b.attr)
    return out


def _literal(node: ast.ClassDef, field: str):
    """The literal value assigned to `field` in a class body, or None."""
    for stmt in node.body:
        targets = []
        if isinstance(stmt, ast.Assign):
            targets = stmt.targets
        elif isinstance(stmt, ast.AnnAssign):
            targets = [stmt.target]
        else:
            continue
        for t in targets:
            if isinstance(t, ast.Name) and t.id == field and stmt.value is not None:
                try:
                    return ast.literal_eval(stmt.value)
                except (ValueError, SyntaxError):
                    return None
    return None


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding='utf-8'))
    except (OSError, SyntaxError):
        return None


def _classes(path: Path, base_suffixes: tuple[str, ...]) -> list[ast.ClassDef]:
    tree = _parse(path)
    if tree is None:
        return []
    return [
        n
        for n in tree.body
        if isinstance(n, ast.ClassDef)
        and any(b.endswith(base_suffixes) for b in _manifest_bases(n))
    ]


def registered_apps() -> set[str]:
    """The app names listed in MORPHEUS_DEFAULT_APPS, read without importing."""
    tree = _parse(SETTINGS)
    if tree is None:
        return set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == 'MORPHEUS_DEFAULT_APPS' for t in node.targets
        ):
            try:
                entries = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                return set()
            return {str(e).rsplit('.', 1)[-1] for e in entries}
    return set()


def defines_models(plugin: Path) -> bool:
    """True when models.py declares something that looks like a concrete model.

    Any base whose name ends in `Model` counts — `models.Model`, and the
    abstract bases apps build on. A false positive costs nothing: the rule it
    gates (a migrations package must exist and be importable) is right for any
    app that has models at all.
    """
    models_py = plugin / 'models.py'
    if not models_py.exists():
        return False
    return bool(_classes(models_py, ('Model',)))


def _check_structure(plugin: Path) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if not (plugin / '__init__.py').exists():
        found.append(('structure.init', ''))
    apps_py = plugin / 'apps.py'
    configs = _classes(apps_py, ('AppConfig',)) if apps_py.exists() else []
    if not configs:
        found.append(('structure.apps', ''))
    else:
        dotted = _literal(configs[0], 'name')
        if dotted != f'plugins.installed.{plugin.name}':
            found.append(('structure.appconfig_name', f'{dotted!r}'))
    return found


def _check_manifest(
    plugin: Path, manifest: ast.ClassDef | None, *, known: set[str]
) -> list[tuple[str, str]]:
    if manifest is None:
        return [('structure.manifest', '')]
    name = plugin.name
    found: list[tuple[str, str]] = []
    if _literal(manifest, 'name') != name:
        found.append(('manifest.name', f'{_literal(manifest, "name")!r}'))
    if not _literal(manifest, 'label'):
        found.append(('manifest.label', ''))
    version = _literal(manifest, 'version')
    # Absent is fine — the base class defaults to '1.0.0'. Present and
    # malformed is not: the registry raises on it at boot.
    if version is not None and not (isinstance(version, str) and SEMVER.match(version)):
        found.append(('manifest.version', f'{version!r}'))
    if not _literal(manifest, 'description'):
        found.append(('manifest.description', ''))
    requires = _literal(manifest, 'requires') or []
    if isinstance(requires, list):
        for dep in requires:
            if dep == name:
                found.append(('graph.requires_self', ''))
            # A `core.*` requirement is a core Django app, not a sibling app —
            # the registry satisfies it from INSTALLED_APPS on purpose
            # (plugins/registry.py:validate), so it is not an unknown name.
            elif isinstance(dep, str) and dep not in known and not dep.startswith('core.'):
                found.append(('graph.requires_unknown', dep))
    return found


def _check_models(plugin: Path, manifest: ast.ClassDef | None) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    migrations = plugin / 'migrations'
    if migrations.is_dir() and not (migrations / '__init__.py').exists():
        found.append(('models.migrations_package', ''))
    if not defines_models(plugin):
        return found
    if not migrations.is_dir():
        found.append(('models.migrations_missing', ''))
    elif not any(p.name[:4].isdigit() for p in migrations.glob('*.py') if p.name != '__init__.py'):
        found.append(('models.no_initial', ''))
    # Omitted counts the same as False — the base class defaults it to False,
    # and the flag is what Linda and the Brain read to decide whether an app
    # owns data at all (core/assistant/tools/capabilities.py, core/brain).
    if manifest is not None and _literal(manifest, 'has_models') is not True:
        found.append(('models.has_models_flag', ''))
    return found


def audit_plugin(plugin: Path, *, known: set[str], registered: set[str]) -> list[tuple[str, str]]:
    """Return [(rule_id, detail)] for one app directory."""
    app_py = plugin / 'app.py'
    manifests = _classes(app_py, ('Plugin', 'MorpheusPlugin')) if app_py.exists() else []
    manifest = manifests[0] if manifests else None

    found = _check_structure(plugin)
    found += _check_manifest(plugin, manifest, known=known)
    found += _check_models(plugin, manifest)

    if plugin.name not in registered:
        found.append(('settings.not_registered', ''))

    tests_dir = plugin / 'tests'
    has_tests = (tests_dir.is_dir() and any(tests_dir.glob('test_*.py'))) or (
        plugin / 'tests.py'
    ).exists()
    if not has_tests:
        found.append(('tests.missing', ''))

    return found


def audit_all() -> dict[str, list[tuple[str, str]]]:
    known = {p.name for p in INSTALLED.iterdir() if p.is_dir() and not p.name.startswith('_')}
    registered = registered_apps()
    out: dict[str, list[tuple[str, str]]] = {}
    for plugin in sorted(INSTALLED.iterdir()):
        if not plugin.is_dir() or plugin.name.startswith(('_', '.')):
            continue
        violations = audit_plugin(plugin, known=known, registered=registered)
        if violations:
            out[plugin.name] = violations
    return out


def _flatten(found: dict[str, list[tuple[str, str]]]) -> set[str]:
    """One comparable key per violation: `<app>:<rule>` (the detail is advisory)."""
    return {f'{app}:{rule}' for app, items in found.items() for rule, _ in items}


def load_baseline() -> set[str]:
    if not BASELINE.exists():
        return set()
    data = json.loads(BASELINE.read_text(encoding='utf-8'))
    return set(data.get('violations', []))


def save_baseline(found: dict[str, list[tuple[str, str]]]) -> None:
    BASELINE.write_text(
        json.dumps(
            {
                '_comment': (
                    'Baseline for scripts/check_plugin_standard.py — the KNOWN plugin-contract '
                    'violations, being repaid over time. Fix one and remove its entry in the same '
                    'change. Only ever remove entries; never add. Regenerate deliberately with '
                    '--save.'
                ),
                '_rules': RULES,
                'violations': sorted(_flatten(found)),
            },
            indent=2,
        )
        + '\n',
        encoding='utf-8',
    )


def report(found: dict[str, list[tuple[str, str]]]) -> None:
    total = sum(len(v) for v in found.values())
    apps = len([p for p in INSTALLED.iterdir() if p.is_dir() and not p.name.startswith(('_', '.'))])
    print(f'{apps} apps audited, {len(found)} with findings, {total} findings total.\n')
    by_rule: dict[str, list[str]] = {}
    for app, items in found.items():
        for rule, detail in items:
            by_rule.setdefault(rule, []).append(f'{app}{f" ({detail})" if detail else ""}')
    for rule in sorted(by_rule, key=lambda r: -len(by_rule[r])):
        offenders = by_rule[rule]
        print(f'{rule}  ({len(offenders)})')
        print(f'  {RULES.get(rule, "")}')
        for o in sorted(offenders):
            print(f'    - {o}')
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save', action='store_true', help='rewrite the baseline')
    parser.add_argument('--report', action='store_true', help='human summary; never fails')
    args = parser.parse_args()

    found = audit_all()

    if args.report:
        report(found)
        return 0
    if args.save:
        save_baseline(found)
        print(f'Baseline written: {len(_flatten(found))} known violation(s).')
        return 0

    current = _flatten(found)
    baseline = load_baseline()
    new = sorted(current - baseline)
    fixed = sorted(baseline - current)

    if new:
        print('NEW plugin-contract violation(s):\n')
        for key in new:
            app, rule = key.split(':', 1)
            print(f'  {app}: {RULES.get(rule, rule)}')
        print('\nFix the app, or — if this is deliberate — say why in the PR.')
    if fixed:
        print('\nBaseline entries that no longer reproduce (remove them):\n')
        for key in fixed:
            print(f'  {key}')
        print('\nRun: python scripts/check_plugin_standard.py --save')
    if new or fixed:
        return 1

    print(f'OK: {len(baseline)} known plugin-contract violation(s), no new ones. ✓')
    return 0


if __name__ == '__main__':
    sys.exit(main())
