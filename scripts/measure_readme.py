"""Measure the figures in README's "By the numbers" table.

The table is never edited by hand: run this, then copy the printed rows. It boots
Django on an in-memory database with every opt-in app switched on, so the opt-in
verticals and suppliers are counted, and reads the registries as the running store
would see them.

    python scripts/measure_readme.py
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

OPT_IN = [
    'plugins.installed.booking_marketplace',
    'plugins.installed.dsers',
    'plugins.installed.zendrop',
    'plugins.installed.cjdropshipping',
    'plugins.installed.aliexpress',
    'plugins.installed.demo_data',
]
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['MORPHEUS_EXTRA_APPS'] = ','.join(OPT_IN)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'morph.settings')

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.core.management import get_commands  # noqa: E402
from django.urls import URLPattern, URLResolver, get_resolver  # noqa: E402

CODE_DIRS = ['core', 'plugins', 'themes', 'api', 'morph', 'morpheus', 'scripts']


def tree_files(suffixes: tuple[str, ...]) -> list[Path]:
    out = []
    for d in CODE_DIRS:
        for p in (ROOT / d).rglob('*'):
            if p.is_file() and p.suffix in suffixes and 'node_modules' not in p.parts:
                out.append(p)
    return out


def lines(paths: list[Path]) -> int:
    total = 0
    for p in paths:
        with contextlib.suppress(OSError):
            total += p.read_bytes().count(b'\n')
    return total


def walk(patterns, prefix=''):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from walk(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern)


def main() -> None:
    from api.schema import get_schema
    from core.agents.registry import agent_registry
    from core.hooks import MorpheusEvents, hook_registry
    from plugins.installed.agent_mcp.scopes import AVAILABLE_SCOPES
    from plugins.installed.payments.gateway import gateway_registry
    from plugins.installed.rbac.models import _DEFAULT_TEMPLATES
    from plugins.registry import app_registry

    default_apps = [a for a in settings.MORPHEUS_DEFAULT_APPS if a.startswith('plugins.installed.')]
    tree_apps = sorted(p.parent.name for p in (ROOT / 'plugins/installed').glob('*/app.py'))
    events = [v for k, v in vars(MorpheusEvents).items() if k.isupper() and isinstance(v, str)]
    subscriptions = sum(len(h) for h in hook_registry._handlers.values())
    tools = agent_registry.platform_tools()
    gated = sum(1 for t in tools if getattr(t, 'requires_approval', False))
    capabilities = {c for caps in _DEFAULT_TEMPLATES.values() for c in caps}
    py = tree_files(('.py',))
    gated_views = sum(p.read_text(errors='ignore').count('@require_capability') for p in py)

    schema = get_schema()._schema
    query = schema.query_type.fields if schema.query_type else {}
    mutation = schema.mutation_type.fields if schema.mutation_type else {}
    types = [n for n in schema.type_map if not n.startswith('__')]

    routes = list(walk(get_resolver().url_patterns))
    dashboard_routes = [r for r in routes if 'dashboard/' in r]
    blocks = app_registry._storefront_blocks
    slots = {b.slot for b in blocks}

    tests = sum(
        len(re.findall(r'^\s*(?:async\s+)?def test_', p.read_text(errors='ignore'), re.M))
        for p in py
    )
    test_py = [p for p in py if 'tests' in p.parts or p.name.startswith('test')]
    templates = tree_files(('.html',))
    front = templates + tree_files(('.css', '.js'))
    migrations = [p for p in (ROOT / 'plugins').rglob('migrations/[0-9]*.py')] + [
        p for p in (ROOT / 'core').rglob('migrations/[0-9]*.py')
    ]
    adrs = list((ROOT / '.torsor/architecture/decisions').glob('*.md'))

    notes = (ROOT / 'docs/RELEASE_NOTES.md').read_text()
    releases = re.findall(r'^## v\d+\.\d+\.\d+ — (\d{4}-\d{2}-\d{2})', notes, re.M)
    first = date(2026, 6, 20)
    newest = max(date.fromisoformat(d) for d in releases)

    core_baseline = json.loads((ROOT / 'scripts/core_boundary_baseline.json').read_text())
    ours = ('core', 'plugins', 'morph', 'api', 'morpheus')
    commands = [n for n, app in get_commands().items() if app.split('.')[0] in ours]

    rows = [
        ('Version', settings.MORPHEUS_VERSION),
        (
            'Apps in the tree',
            f'{len(tree_apps)} ({len(default_apps)} default + {len(tree_apps) - len(default_apps)} opt-in)',
        ),
        ('Events', f'{len(events)}, {subscriptions} subscriptions'),
        ('Agent tools', f'{len(tools)}, {gated} require approval'),
        ('MCP scopes', len(AVAILABLE_SCOPES)),
        ('RBAC capabilities', f'{len(capabilities)}, gating {gated_views} views'),
        ('GraphQL', f'{len(query)} queries, {len(mutation)} mutations, {len(types)} types'),
        ('URL routes', f'{len(routes)}, {len(dashboard_routes)} dashboard'),
        (
            'Dashboard pages, settings panels, storefront blocks',
            f'{len(app_registry.dashboard_pages())}, {len(app_registry.all_settings_panels())}, '
            f'{len(blocks)} across {len(slots)} slots',
        ),
        (
            'Scheduled jobs, management commands',
            f'{len(settings.CELERY_BEAT_SCHEDULE)}, {len(commands)}',
        ),
        ('Payment gateways', ', '.join(sorted(g.slug for g in gateway_registry.all()))),
        ('Releases', f'{len(releases)} in {(newest - first).days} days (newest {newest})'),
        ('Tests', f'{tests} test functions'),
        ('Python lines', f'{lines(py):,} ({lines(test_py):,} tests)'),
        ('Templates, CSS and JS', f'{len(templates)} templates, {lines(front):,} lines'),
        ('Migrations', len(migrations)),
        ('ADRs', len(adrs)),
        ('core/ boundary baseline', 'empty' if not core_baseline.get('allowed') else 'NOT empty'),
    ]
    width = max(len(k) for k, _ in rows)
    for key, value in rows:
        print(f'{key:<{width}}  {value}')
    print(f'{"Measured on":<{width}}  {date.today()}')


if __name__ == '__main__':
    main()
