"""Every settings control an app declares is read by some code.

A key in a ``SettingsPanel`` or ``get_config_schema()`` with no reader renders a
control the merchant can change to no effect — "a settings field with no
consumer is a lie" (CLAUDE.md). v0.76.3 found 78 of them across 30 apps; they
were removed in v0.76.4 and this test keeps the count at zero.

The check is textual: the key, quoted, anywhere in non-test Python outside its
own schema declaration, or as a bare word in a template or script. Apps that
build key names at runtime (``get_config_value(f'{provider}_model')``) are
skipped, because the text search cannot see those reads; they are listed in
``DYNAMIC_READERS`` and must stay few.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from django.conf import settings
from django.test import TestCase

SKIP_PARTS = {'tests', 'migrations', 'node_modules', '__pycache__', 'static'}
# Apps whose readers build key names at runtime; the text search cannot judge them.
DYNAMIC_READERS = {
    'admin_dashboard',
    'agent_core',
    'ai_assistant',
    'bookstore_3d',
    'gdpr',
    'seo',
    'staff_sso',
}


def _sources(base: Path, exts: set[str]) -> list[str]:
    texts = []
    for top in ('core', 'plugins', 'themes', 'morph', 'api', 'morpheus'):
        for f in (base / top).rglob('*'):
            if (
                f.suffix in exts
                and not (set(f.parts) & SKIP_PARTS)
                and not f.name.startswith('test')
            ):
                texts.append(f.read_text(encoding='utf-8', errors='replace'))
    return texts


class SettingsKeysHaveReadersTests(TestCase):
    maxDiff = None  # the whole list, not "[2569 chars]"

    def test_every_declared_key_is_read_somewhere(self):
        from plugins.registry import app_registry

        base = Path(settings.BASE_DIR)
        python = '\n'.join(_sources(base, {'.py'}))
        markup = '\n'.join(_sources(base, {'.html', '.js'}))

        declared: dict[str, set[str]] = defaultdict(set)
        for plugin in app_registry.all_plugins():
            name = plugin.name
            try:
                schema = plugin.get_config_schema() if hasattr(plugin, 'get_config_schema') else {}
            except Exception:  # noqa: BLE001 — a schema that can't build is another test's problem
                schema = {}
            declared[name] |= set((schema or {}).get('properties') or {})
        for entry in app_registry.all_settings_panels():
            panel_schema = getattr(entry['panel'], 'schema', None) or {}
            declared[str(entry['plugin'])] |= set(panel_schema.get('properties') or {})

        unread = []
        for plugin, keys in sorted(declared.items()):
            if plugin in DYNAMIC_READERS:
                continue
            for key in sorted(keys):
                # A quoted use that is not the schema declaration ("key": {...}).
                quoted = re.compile(r'[\'"]' + re.escape(key) + r'[\'"](?!\s*:\s*\{)')
                word = re.compile(r'\b' + re.escape(key) + r'\b')
                if not quoted.search(python) and not word.search(markup):
                    unread.append(f'{plugin}.{key}')
        self.assertEqual(
            unread, [], 'settings keys with no reader (wire them or remove the control)'
        )


_TEMPLATE_COMMENTS = re.compile(
    r'\{#.*?#\}|\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}|<!--.*?-->', re.S
)


class ThemeSettingsHaveReadersTests(TestCase):
    """A theme's settings are read by that theme (v0.185.0).

    Settings, Storefront → Theme renders the active theme's schema and Linda's
    ``theme.set`` writes it, so a key the theme never reads is a control that
    changes nothing. Four themes declared brand name, tagline, accent colours and
    a newsletter pitch that no template or Python of theirs read; nobody could
    edit them until the page existed. A word inside a template comment is not a
    read (montenegro's ``product_list.html`` mentions ``brand_name()`` in one).
    """

    maxDiff = None

    def test_every_theme_setting_is_read_by_its_own_theme(self):
        import inspect

        from themes.registry import theme_registry

        unread = []
        for theme in sorted(theme_registry.all_themes(), key=lambda t: t.name):
            keys = sorted(((theme.get_config_schema() or {}).get('properties') or {}).keys())
            if not keys:
                continue
            folder = Path(inspect.getfile(type(theme))).parent
            texts = [
                _TEMPLATE_COMMENTS.sub('', f.read_text(encoding='utf-8', errors='replace'))
                for f in folder.rglob('*')
                if f.suffix in {'.html', '.py', '.js'}
                and f.name != 'theme.py'
                and not f.name.startswith('test')
            ]
            blob = '\n'.join(texts)
            unread += [
                f'{theme.name}.{key}'
                for key in keys
                if not re.search(r'\b' + re.escape(key) + r'\b', blob)
            ]
        self.assertEqual(
            unread, [], 'theme settings no template or code of that theme reads (wire or remove)'
        )
