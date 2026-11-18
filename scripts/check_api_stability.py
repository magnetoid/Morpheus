#!/usr/bin/env python3
"""API stability gate — diff the current public surface against a frozen baseline.

Turns ``docs/API_STABILITY.md`` from documentation into a CI check. Run in CI on
every PR; non-zero exit blocks merge when a stable surface changed without an
explicit baseline refresh.

The surfaces gated (a removal or a rename of any entry is a hard block):

  1. The Python SDK's public symbols: the top-level ``morpheus`` package, its
     submodules (``morpheus.events``, ``.hooks``, ``.models``, ``.forms``,
     ``.views``) and the SDK doors an app author imports from
     (``morpheus.app`` and its submodules, ``morpheus.core``,
     ``morpheus.theme``).
  2. ``events``: every ``core.hooks.MorpheusEvents`` constant with its value,
     since an app subscribes by the string (v0.179.0; ``morpheus.events`` only
     re-exports some of them).
  3. ``agent_tools``: every tool name Linda and the agents can be offered.
     Tool names are a stable API: external agents and stored automations call
     them by name (CLAUDE.md, "two plugins registering the same agent-tool
     NAME").
  4. ``contribution_fields``: the fields of each contribution an app returns
     (``StorefrontBlock``, ``DashboardPage``, …).
  5. ``app_manifest``: the public attributes and methods of the app base
     class (``requires``, ``min_morpheus``, ``register_hook``, …).

The snapshot is taken with the default app list only (CI sets no
``MORPHEUS_EXTRA_APPS``), so it does not depend on the store. A release that
deletes an app removes its tools on purpose: refresh the baseline in that
release with ``--save``.

GraphQL schema stability deserves its own diff tool (Strawberry's schema
printer); that's a separate follow-up.

Usage:
    python scripts/check_api_stability.py                  # diff against baseline
    python scripts/check_api_stability.py --save           # write current as baseline
    python scripts/check_api_stability.py --baseline path  # custom baseline

Exit codes:
    0  no changes, or only additions
    2  a stable symbol was removed (the gate)
    3  baseline file missing AND --save not passed
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import os
import sys
from pathlib import Path

# Modules whose public symbols ARE the SDK surface. Order is significant only
# for stable output diffing. Each module's `__all__` (when present) is the
# authority; otherwise we fall back to every non-underscore name.
SDK_MODULES = [
    'morpheus',
    'morpheus.events',
    'morpheus.hooks',
    'morpheus.models',
    'morpheus.forms',
    'morpheus.views',
    'morpheus.app',
    'morpheus.app.forms',
    'morpheus.app.models',
    'morpheus.app.views',
    'morpheus.core',
    'morpheus.theme',
]

#: The surfaces beyond module symbols, each a function returning sorted names.
EXTRA_SURFACES = ('events', 'agent_tools', 'contribution_fields', 'app_manifest')

DEFAULT_BASELINE = Path(__file__).resolve().parent.parent / 'docs' / 'sdk-baseline.json'


def _public_symbols(module_name: str) -> list[str]:
    """Return the sorted list of public symbols a third-party can import."""
    try:
        mod = importlib.import_module(module_name)
    except ImportError as exc:
        print(f'  ! cannot import {module_name}: {exc}', file=sys.stderr)
        return []
    explicit = getattr(mod, '__all__', None)
    if explicit is not None:
        return sorted(set(explicit))
    names = [
        n
        for n in dir(mod)
        if not n.startswith('_')
        # `from __future__ import annotations` leaks a _Feature object into
        # dir(); it was never public API — don't snapshot it.
        and getattr(getattr(mod, n, None), '__module__', None) != '__future__'
    ]
    # Filter out things imported from elsewhere — keep only symbols that
    # were defined in (or explicitly re-exported through) this module.
    out: list[str] = []
    for n in names:
        try:
            obj = getattr(mod, n)
            obj_mod = getattr(obj, '__module__', None) or ''
            if obj_mod == module_name or obj_mod.startswith(module_name + '.'):
                out.append(n)
            elif inspect.ismodule(obj):
                continue  # skip pulled-in submodules
            else:
                # Re-exports: include if listed in __all__-style markers or
                # if the symbol is a primitive type (dataclass, function)
                # someone might subscribe to.
                out.append(n)
        except Exception:  # noqa: BLE001
            out.append(n)
    return sorted(set(out))


def _events() -> list[str]:
    """`NAME=value` for every event constant: a new value is a rename."""
    from core.hooks import MorpheusEvents

    return sorted(
        f'{name}={value}'
        for name, value in vars(MorpheusEvents).items()
        if name.isupper() and isinstance(value, str)
    )


def _agent_tools() -> list[str]:
    """Every tool name: Linda's built-in tools and every tool an app registers."""
    from core.agents import agent_registry
    from core.assistant.tools import get_default_tools

    return sorted({t.name for t in [*get_default_tools(), *agent_registry.platform_tools()]})


def _contribution_fields() -> list[str]:
    import dataclasses

    from plugins import contributions

    return sorted(
        f'{cls.__name__}.{field.name}'
        for cls in vars(contributions).values()
        if dataclasses.is_dataclass(cls)
        and isinstance(cls, type)
        and cls.__module__ == contributions.__name__
        for field in dataclasses.fields(cls)
        if not field.name.startswith('_')
    )


def _app_manifest() -> list[str]:
    from plugins.base import MorpheusPlugin

    return sorted(name for name in vars(MorpheusPlugin) if not name.startswith('_'))


def snapshot() -> dict[str, list[str]]:
    current = {m: _public_symbols(m) for m in SDK_MODULES}
    current['events'] = _events()
    current['agent_tools'] = _agent_tools()
    current['contribution_fields'] = _contribution_fields()
    current['app_manifest'] = _app_manifest()
    return current


def compare(
    baseline: dict[str, list[str]], current: dict[str, list[str]]
) -> tuple[list[str], list[str]]:
    """Return (removals, additions). Empty removals = green."""
    removals: list[str] = []
    additions: list[str] = []
    for surface in [*SDK_MODULES, *EXTRA_SURFACES]:
        base = set(baseline.get(surface, []))
        curr = set(current.get(surface, []))
        for sym in sorted(base - curr):
            removals.append(f'{surface}: {sym}')
        for sym in sorted(curr - base):
            additions.append(f'{surface}: {sym}')
    return removals, additions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--save',
        action='store_true',
        help='Write current snapshot as the new baseline (use after an intentional breaking change + major-version bump).',
    )
    parser.add_argument(
        '--baseline',
        default=str(DEFAULT_BASELINE),
        help=f'Baseline JSON path (default {DEFAULT_BASELINE}).',
    )
    parser.add_argument(
        '--json',
        dest='emit_json',
        action='store_true',
        help='Emit JSON diff to stdout instead of human text.',
    )
    args = parser.parse_args()

    # Bootstrap Django so morpheus.* importers don't crash. When invoked as
    # `python scripts/check_api_stability.py`, sys.path[0] is scripts/ — put
    # the repo root first so `morph.settings` resolves.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'morph.settings')
    os.environ.setdefault('SECRET_KEY', 'check-only')
    os.environ.setdefault('ALLOWED_HOSTS', 'localhost')
    try:
        import django  # noqa: E402

        django.setup()
    except Exception as exc:  # noqa: BLE001
        print(f'! Django setup failed (probably missing deps): {exc}', file=sys.stderr)
        return 3

    current = snapshot()

    if args.save:
        Path(args.baseline).parent.mkdir(parents=True, exist_ok=True)
        with open(args.baseline, 'w') as fh:
            json.dump(current, fh, indent=2, sort_keys=True)
            fh.write('\n')
        print(
            f'Wrote baseline to {args.baseline} ({sum(len(v) for v in current.values())} symbols across {len(current)} modules).'
        )
        return 0

    if not Path(args.baseline).exists():
        print(f'! baseline file missing: {args.baseline}', file=sys.stderr)
        print('  Run `python scripts/check_api_stability.py --save` to seed it.', file=sys.stderr)
        return 3

    with open(args.baseline) as fh:
        baseline = json.load(fh)

    removals, additions = compare(baseline, current)

    if args.emit_json:
        print(json.dumps({'removals': removals, 'additions': additions}, indent=2))
    else:
        print(f'API stability check — baseline: {args.baseline}')
        if not removals and not additions:
            print('  No changes. ✓')
        if additions:
            print(f'  Additions ({len(additions)}) — non-breaking:')
            for a in additions:
                print(f'    + {a}')
        if removals:
            print(f'  REMOVALS ({len(removals)}) — breaking:')
            for r in removals:
                print(f'    - {r}')
            print()
            print('  Stable symbols cannot be removed without a major-version bump.')
            print('  If this removal is intentional and you bumped the major version,')
            print('  run `python scripts/check_api_stability.py --save` to refresh.')

    # Removals block. Additions are always allowed.
    return 2 if removals else 0


if __name__ == '__main__':
    sys.exit(main())
