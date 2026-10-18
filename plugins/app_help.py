"""An app's guide for store staff: ``plugins/installed/<app>/help.md``.

Shared plugin infrastructure (CLAUDE.md: code that several apps need and core
does not). release_notes reads the guides for the Help area and Linda's help
tools; admin_dashboard reads each guide's summary for the Apps catalogue. A
guide sits in its app's own folder, so deleting the app deletes its help.

A guide looks like::

    ---
    summary: One plain sentence, at most 140 characters.
    ---

    ## What it's for
    ...

Links to the store's own pages are markers, never URLs (``MARKER_RE``);
release_notes resolves them against the live registry.
Spec: docs/superpowers/specs/2026-10-18-help-system-design.md.
"""

from __future__ import annotations

import importlib
import inspect
import re
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

#: The headings a guide may use, in this order; the first is required.
HEADINGS: tuple[str, ...] = ("What it's for", 'Set it up', 'Common tasks', 'Good to know')
SUMMARY_MAX = 140
BODY_WORDS = (60, 400)
#: Words store staff never meet on a screen, matched as whole words ("webhook"
#: passes). They belong in the generated technical details. Slot, migrate,
#: endpoint, GraphQL and manifest are left out: staff see them on screens.
JARGON: tuple[str, ...] = (
    'plugin',
    'plugins',
    'hook',
    'hooks',
    'celery',
    'queryset',
    'querysets',
    'middleware',
)
#: ``[text](kind:target)``: kind is page, settings, field, section or app.
MARKER_RE = re.compile(r'\[([^\]]*)\]\((page|settings|field|section|app):([A-Za-z0-9_./-]+)\)')

_NAME = re.compile(r'[a-z][a-z0-9_]*')
_FRONT = re.compile(r'\A---\n(.*?)\n---\n', re.S)
_HEADING_LINE = re.compile(r'^##\s+(.+?)\s*$', re.M)


@dataclass(frozen=True)
class Guide:
    app: str
    summary: str
    body: str  # the Markdown after the front matter
    headings: tuple[str, ...]  # every ``## `` heading, in order
    keys: tuple[str, ...]  # every front-matter key, in order


def parse(app: str, text: str) -> Guide:
    """A guide from its file's text. Front matter is ``key: value`` lines between ``---``."""
    text = text.lstrip('\ufeff').replace('\r\n', '\n')
    keys: tuple[str, ...] = ()
    summary = ''
    m = _FRONT.match(text)
    if m:
        front: dict[str, str] = {}
        for line in m.group(1).splitlines():
            key, sep, value = line.partition(':')
            if sep:
                front[key.strip()] = value.strip()
        keys = tuple(front)
        summary = front.get('summary', '')
        text = text[m.end() :]
    body = text.strip('\n')
    return Guide(app, summary, body, tuple(_HEADING_LINE.findall(body)), keys)


def markers(body: str) -> list[tuple[str, str, str]]:
    """``(text, kind, target)`` for every marker in a guide's body."""
    return [m.groups() for m in MARKER_RE.finditer(body)]


def tree_apps() -> list[str]:
    """Every app folder in the repository (``plugins/installed/*/app.py``)."""
    return sorted(p.parent.name for p in _tree().glob('*/app.py'))


def app_dir(name: str) -> Path | None:
    """Where an app's code lives: its manifest's folder when this store installs
    it (so an app in ``MORPHEUS_APPS_DIR`` works too), else its folder in the
    repository. Never imports an app the store does not install."""
    from plugins.registry import app_registry

    inst = app_registry.get(name)
    if inst is not None:
        return Path(inspect.getfile(type(inst))).parent
    if not _NAME.fullmatch(name or ''):
        return None
    path = _tree() / name
    return path if (path / 'app.py').is_file() else None


_cache: dict[tuple[str, str], Guide | None] = {}


def guide(name: str) -> Guide | None:
    """The app's parsed ``help.md``, or None when it has none.

    Cached per process and version (a guide changes only with a deploy); under
    DEBUG it is read every time, so a guide edited locally shows at once.
    """
    key = (str(getattr(settings, 'MORPHEUS_VERSION', '')), name)
    if not settings.DEBUG and key in _cache:
        return _cache[key]
    folder = app_dir(name)
    path = folder / 'help.md' if folder is not None else None
    found = None
    if path is not None and path.is_file():
        found = parse(name, path.read_text(encoding='utf-8', errors='replace'))
    _cache[key] = found
    return found


def summary(name: str) -> str:
    """The app's one sentence for staff, or '' when it has no guide."""
    found = guide(name)
    return found.summary if found is not None else ''


def forget() -> None:
    """Drop the cache (tests that point an app at another guide)."""
    _cache.clear()


def load_manifest(name: str):
    """The app's manifest instance, also for an app this store does not install
    (read from the repository). For checks over every guide; a page shows only
    installed apps. None when there is no such app."""
    from plugins.base import MorpheusPlugin
    from plugins.registry import app_registry

    inst = app_registry.get(name)
    if inst is not None:
        return inst
    if not _NAME.fullmatch(name or '') or not (_tree() / name / 'app.py').is_file():
        return None
    try:
        module = importlib.import_module(f'plugins.installed.{name}.app')
    except Exception:  # noqa: BLE001 — an app that cannot import has no manifest
        return None
    for obj in vars(module).values():
        if (
            isinstance(obj, type)
            and issubclass(obj, MorpheusPlugin)
            and obj is not MorpheusPlugin
            and obj.name == name
        ):
            return obj()
    return None


def _tree() -> Path:
    return Path(settings.BASE_DIR) / 'plugins' / 'installed'
