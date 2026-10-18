# Help Inside the Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/dashboard/help/` explains every app to store staff from a `help.md` in each app's folder plus facts read live from the code, and CI fails when a guide is missing or links a place that no longer exists.

**Architecture:**
- **Reader.** `plugins/app_help.py` reads and parses guides. It is shared plugin infrastructure.
- **Help area.** `release_notes` serves the Help area: it resolves link markers against the live registry, renders guides, gathers the generated facts, searches, answers the dashboard shell's new `DASHBOARD_PAGE_HELP` filter and gives Linda two read-only tools.
- **Shell links.** The shell links no app page; it asks the filter.

**Tech Stack:** Django 6 templates and views, the Morpheus hook bus (`core/hooks.py`), the app registry (`plugins/registry.py`), `admin_dashboard/navigation.py`, the agent tool decorator (`morpheus.core.tool`). No new dependency.

**Spec:** `docs/superpowers/specs/2026-10-18-help-system-design.md`

## Global Constraints

- **Working folder.** Work on `main` in `/Users/magnetoid/coding/morph`: one working folder, no worktrees (owner's rule). Commit at the end of every task, and push only in Task 12. A push to `main` deploys all four stores.
- **Test command `T`:**
  ```
  DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress' .venv/bin/python manage.py test
  ```
  CI uses this app list. A shorter list gives false failures.
- **Lint** each changed Python file with `.venv/bin/ruff check <files>` and `.venv/bin/ruff format <files>` (the CI version).
- **No new dependency.** The renderer is built from the subset `release_notes` already renders.
- **Imports.** `core/` imports nothing from `plugins.installed.*` (ratchet at 0). `plugins/app_help.py` sits at the `plugins/` root. `release_notes` declares `requires = ['admin_dashboard']` before it imports `admin_dashboard`.
- **Guide format** (spec):
  - front matter is exactly one key, `summary`: one plain sentence of at most 140 characters;
  - headings come from "What it's for" (required), "Set it up", "Common tasks", "Good to know", in that order;
  - the body is 60 to 400 words;
  - links to the store's pages are markers only (`page:`, `settings:`, `field:`, `section:`, `app:`).
- **Staff-facing name.** Every page and guide calls the assistant **Linda**, the name staff see in the sidebar. Janus appears only as the label of its own settings page.
- **Dashboard templates.**
  - Colour tokens only (`var(--text-muted)`, `var(--brand)`, `var(--surface-2)`, …).
  - Icons are only names already in `base.html`'s glyph map: `help-circle`, `search`, `info`, `git-commit-horizontal`.
  - Never write `*/` inside a CSS comment.
  - Compile every changed template with `get_template()` before committing.
- **Release.** One MINOR release at the end through `manage.py release --minor` (merge = deploy).

## Rulings against the spec

Each is a deliberate change from the spec, with its reason and its cost if wrong.

1. **The assistant is "Linda" on staff-facing text** (the section is "What Linda can do here").
   - **Why:** the spec said "What Janus can do here", but staff know the assistant as Linda.
   - **Cost if wrong:** renaming one heading.
2. **Narrower developer-words list.** The test flags plugin(s), hook(s), Celery, queryset(s) and middleware.
   - **Why:** the spec's slot, migration, endpoint, GraphQL and manifest are words staff see on screens: the gallery's "Slot 1", the importers' "Migrate", the webhooks page's endpoints and the API tokens page's GraphQL.
   - **Cost if wrong:** a guide could carry one of those words.
3. **Linda's Insights tab links `ai_assistant`.** Chat, Chats and Proposals link `agent_core`, as the spec says.
   - **Why:** the spec put every Linda tab under `agent_core`, but Insights is Pulse, which `ai_assistant` owns.
   - **Cost if wrong:** one `CoreTab.app` value.
4. **Linda's one help line is appended by `release_notes` through `AGENT_SYSTEM_PROMPT`,** not written into core's `LINDA_BASE_PROMPT`.
   - **Why:** a core line would name `help.read` while `release_notes` is off. A subscriber is skipped while its app is off.
   - **Cost if wrong:** none known.
5. **Storefront agents never receive a scope-less platform tool.**
   - **Why:** `MorpheusAgent.get_tools()` hands every agent each platform tool with no scopes. The spec checked only the MCP doors. No storefront agent exists today, and the help tools are the first scope-less platform tools, so Task 8 adds one condition in `core/agents/base.py`.
   - **Cost if wrong:** a storefront agent written later could call help.
6. **The "every app, on and off" page test** requests every installed app's page with the app on, and a fixed sample of eight with the app off.
   - **Why:** toggling 112 apps one by one in a test runs every app's `on_disable` and rebuilds the URLconf 224 times. The off path differs only in empty URLs, which the sample covers.
   - **Cost if wrong:** an app whose page breaks only when off.
7. **A `DASHBOARD_USER_MENU` item may carry a `badge`.**
   - **Why:** the Version & updates entry keeps its version pill when it moves out of `base.html`.
   - **Cost if wrong:** none.

## Review Focus

1. **A manifest whose `contribute_*` method raises:** the app's help page still renders, with what could be read. Pinned in Task 4 (`test_an_app_whose_pages_raise_still_has_facts`) and Task 5 (`test_a_broken_manifest_still_has_a_page`).
2. **A search of punctuation or regex characters (`(`, `*`, `?`, `[`):** no error, and the "No help mentions" message. Pinned in Task 6 (`test_punctuation_is_just_text`).
3. **A guide saved with a byte-order mark or Windows line endings:** it reads exactly like the plain file. Pinned in Task 1 (`test_windows_line_endings_and_a_bom_read_the_same`).
4. **An app label or guide text containing `<`, `&` or quotes:** escaped on the index, the app page and in rendered guides. Pinned in Task 3 (`test_everything_else_is_escaped`) and Task 5 (`test_a_label_with_markup_is_escaped`).
5. **A malformed app name in the URL (`REVIEWS`, `no_such_app`, `../etc`):** 404, never a file read. Pinned in Task 5 (`test_an_unknown_app_is_404`).

**Prose accuracy is not testable.** A guide sentence that describes a feature that doesn't work is caught by Task 10's evidence review instead: every drafting agent reports three code-backed claims per app, and the executor opens them.

---

### Task 1: The guide reader (`plugins/app_help.py`)

**Files:**
- Create: `plugins/app_help.py`
- Test: `plugins/installed/release_notes/tests/test_app_help.py`
- Test: `plugins/installed/release_notes/tests/test_help_files.py`

**Interfaces:**
- Produces:
  - `app_help.HEADINGS: tuple[str, ...]`, `SUMMARY_MAX = 140`, `BODY_WORDS = (60, 400)`, `JARGON: tuple[str, ...]`, `MARKER_RE`;
  - `Guide(app, summary, body, headings, keys)`, a frozen dataclass;
  - `parse(app, text) -> Guide`;
  - `markers(body) -> list[tuple[str, str, str]]`, giving `(text, kind, target)`;
  - `tree_apps() -> list[str]`;
  - `app_dir(name) -> Path | None`;
  - `guide(name) -> Guide | None`;
  - `summary(name) -> str`;
  - `forget() -> None`;
  - `load_manifest(name)`, a plugin instance or None.
- Produces: `_AWAITING_A_GUIDE` in `test_help_files.py`. Later tasks remove names from it, and Task 11 deletes it.

- [ ] **Step 1: Write the failing reader tests**

`plugins/installed/release_notes/tests/test_app_help.py`:

```python
"""The guide reader (plugins/app_help.py): format, location, cache."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from plugins import app_help

GUIDE = """---
summary: Shoppers rate products; you approve or hide what they write.
---

## What it's for

Reviews show on [the product page](section:products).

## Common tasks

- Approve a review on [](page:reviews).
"""


class ParseTests(SimpleTestCase):
    def test_front_matter_body_and_headings(self):
        g = app_help.parse('reviews', GUIDE)
        self.assertEqual(g.summary, 'Shoppers rate products; you approve or hide what they write.')
        self.assertEqual(g.keys, ('summary',))
        self.assertEqual(g.headings, ("What it's for", 'Common tasks'))
        self.assertTrue(g.body.startswith("## What it's for"))

    def test_windows_line_endings_and_a_bom_read_the_same(self):
        plain = app_help.parse('reviews', GUIDE)
        self.assertEqual(app_help.parse('reviews', GUIDE.replace('\n', '\r\n')), plain)
        self.assertEqual(app_help.parse('reviews', '\ufeff' + GUIDE), plain)

    def test_no_front_matter_means_no_summary(self):
        g = app_help.parse('reviews', "## What it's for\n\nText.\n")
        self.assertEqual((g.summary, g.keys), ('', ()))

    def test_markers_are_listed_with_their_text(self):
        self.assertEqual(
            app_help.markers(app_help.parse('reviews', GUIDE).body),
            [('the product page', 'section', 'products'), ('', 'page', 'reviews')],
        )


class LocationTests(TestCase):
    def test_every_app_folder_is_listed(self):
        apps = app_help.tree_apps()
        self.assertIn('reviews', apps)
        self.assertIn('demo_data', apps)  # opt-in: in the tree, not installed in CI
        tree = Path(settings.BASE_DIR) / 'plugins' / 'installed'
        self.assertEqual(len(apps), len(list(tree.glob('*/app.py'))))

    def test_an_installed_app_lives_in_its_manifests_folder(self):
        self.assertEqual(
            app_help.app_dir('reviews'), Path(settings.BASE_DIR) / 'plugins' / 'installed' / 'reviews'
        )

    def test_an_app_the_store_does_not_install_is_found_in_the_tree(self):
        self.assertEqual(
            app_help.app_dir('demo_data'),
            Path(settings.BASE_DIR) / 'plugins' / 'installed' / 'demo_data',
        )

    def test_no_such_app_has_no_folder(self):
        for name in ('no_such_app', '../etc', '', 'REVIEWS'):
            with self.subTest(name=name):
                self.assertIsNone(app_help.app_dir(name))

    def test_a_manifest_is_loaded_for_an_app_not_installed(self):
        from plugins.registry import app_registry

        self.assertEqual(app_help.load_manifest('demo_data').name, 'demo_data')
        self.assertIs(app_help.load_manifest('reviews'), app_registry.get('reviews'))
        self.assertIsNone(app_help.load_manifest('no_such_app'))


class GuideTests(SimpleTestCase):
    def setUp(self):
        app_help.forget()
        self.addCleanup(app_help.forget)

    def test_a_guide_is_read_from_the_apps_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'help.md').write_text(GUIDE, encoding='utf-8')
            with mock.patch.object(app_help, 'app_dir', return_value=Path(tmp)):
                self.assertEqual(
                    app_help.summary('reviews'),
                    'Shoppers rate products; you approve or hide what they write.',
                )

    def test_an_app_without_a_guide_reads_as_none(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(app_help, 'app_dir', return_value=Path(tmp)),
        ):
            self.assertIsNone(app_help.guide('reviews'))
            self.assertEqual(app_help.summary('reviews'), '')
```

- [ ] **Step 2: Run them and watch them fail**

Run: `T plugins.installed.release_notes.tests.test_app_help`
Expected: ERROR, `ImportError: cannot import name 'app_help' from 'plugins'`.

- [ ] **Step 3: Write the reader**

`plugins/app_help.py`:

```python
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
```

- [ ] **Step 4: Run the reader tests and watch them pass**

Run: `T plugins.installed.release_notes.tests.test_app_help`
Expected: `OK` (10 tests).

- [ ] **Step 5: Write the guide file tests, with every app still waiting**

`plugins/installed/release_notes/tests/test_help_files.py`:

```python
"""Every app ships a guide for store staff, in one shape.

A guide is plugins/installed/<app>/help.md, read by the Help area, Linda's help
tools and the Apps catalogue (plugins/app_help.py). These tests keep the guides
present and in one shape; test_help_markers.py keeps their links true.
Spec: docs/superpowers/specs/2026-10-18-help-system-design.md.
"""

from __future__ import annotations

import re

from django.test import SimpleTestCase

from plugins import app_help

#: Apps whose guide is still being written. Every guide removes its app; Task 11
#: of the plan deletes the set, and from then on every app must have a guide.
_AWAITING_A_GUIDE = frozenset(
    {
        'admin_dashboard', 'advanced_ecommerce', 'advanced_payments', 'affiliates',
        'agent_core', 'agent_mcp', 'agentic_checkout', 'ai_assistant', 'ai_content',
        'ai_stylist', 'aliexpress', 'amazon_ads', 'analytics', 'audiobooks', 'b2b',
        'backups', 'book_product', 'booking_marketplace', 'bookstore_3d', 'bookvault',
        'brand_kit', 'cart_abandonment', 'catalog', 'channels', 'cjdropshipping',
        'cloudflare', 'cms', 'consent', 'crm', 'customers', 'demo_data',
        'digital_products', 'discovery_quiz', 'draft_orders', 'drops', 'dsers',
        'dynamics', 'eco_impact', 'environments', 'experiments', 'feature_adoption',
        'feedback', 'flipbook', 'fraud_rules', 'functions', 'gdpr', 'gift_cards',
        'google_shopping', 'immersive_pdp', 'importers', 'inventory', 'janus',
        'journal', 'live_commerce', 'localization', 'lookbook', 'loyalty_points',
        'lumina', 'marketing', 'marketplace', 'markets', 'media', 'media_3d',
        'meta_commerce', 'metafields', 'microsoft_commerce', 'morpheus_brain',
        'motion', 'newsletter', 'notifications_center', 'observability', 'one_click',
        'openai_shopping', 'orders', 'payments', 'personalisation',
        'pinterest_commerce', 'post_checkout_upsell', 'post_purchase',
        'product_gallery', 'product_stories', 'product_videos', 'promotions', 'pwa',
        'rails', 'rbac', 'reddit_ads', 'referrals', 'release_notes', 'returns_portal',
        'reviews', 'rich_post_purchase', 'richtext', 'save_for_later', 'seo',
        'shipping', 'smart_shipping', 'snapchat_commerce', 'staff_mfa', 'staff_sso',
        'store_bootstrap', 'storefront', 'subscriptions', 'tax', 'tiktok_commerce',
        'tracking', 'trust_signals', 'ugc_reviews', 'webhooks_ui', 'webstories',
        'wishlist', 'workflows', 'zendrop',
    }
)

_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_SENTENCE_END = re.compile(r'[.!?](\s|$)')


def _guides():
    for app in app_help.tree_apps():
        found = app_help.guide(app)
        if found is not None:
            yield found


def _prose(body: str) -> str:
    """The guide as a reader reads it: marker targets and URLs taken out."""
    body = app_help.MARKER_RE.sub(lambda m: m.group(1), body)
    return re.sub(r'\(https://[^)\s]+\)', '', body)


class GuideCoverageTests(SimpleTestCase):
    def test_every_app_has_a_guide(self):
        missing = [
            a
            for a in app_help.tree_apps()
            if a not in _AWAITING_A_GUIDE and app_help.guide(a) is None
        ]
        self.assertEqual(missing, [], 'apps without plugins/installed/<app>/help.md')

    def test_an_app_with_a_guide_is_not_still_awaiting_one(self):
        stale = sorted(a for a in _AWAITING_A_GUIDE if app_help.guide(a) is not None)
        self.assertEqual(stale, [], 'remove these from _AWAITING_A_GUIDE')

    def test_every_awaiting_app_exists(self):
        self.assertEqual(sorted(_AWAITING_A_GUIDE - set(app_help.tree_apps())), [])


class GuideFormatTests(SimpleTestCase):
    def test_the_front_matter_is_one_summary_sentence(self):
        for g in _guides():
            with self.subTest(app=g.app):
                self.assertEqual(g.keys, ('summary',))
                self.assertTrue(g.summary, 'summary is empty')
                self.assertLessEqual(len(g.summary), app_help.SUMMARY_MAX)
                self.assertRegex(g.summary, r'[.!?]$', 'the summary ends a sentence')
                self.assertEqual(len(_SENTENCE_END.findall(g.summary)), 1, 'one sentence')
                self.assertNotRegex(g.summary, r'[*`\[\]<>#]', 'the summary is plain text')

    def test_headings_come_from_the_set_in_order(self):
        for g in _guides():
            with self.subTest(app=g.app):
                self.assertTrue(g.headings, 'a guide has headings')
                self.assertEqual(g.headings[0], app_help.HEADINGS[0])
                self.assertLessEqual(set(g.headings), set(app_help.HEADINGS), g.headings)
                order = [app_help.HEADINGS.index(h) for h in g.headings]
                self.assertEqual(order, sorted(set(order)), 'each heading once, in order')
                self.assertNotRegex(g.body, r'(?m)^#\s', 'no top-level heading')

    def test_the_body_is_60_to_400_words(self):
        low, high = app_help.BODY_WORDS
        for g in _guides():
            with self.subTest(app=g.app):
                words = len(_WORD.findall(_prose(g.body)))
                self.assertGreaterEqual(words, low)
                self.assertLessEqual(words, high)

    def test_no_developer_words(self):
        jargon = re.compile(r'\b(' + '|'.join(app_help.JARGON) + r')\b', re.I)
        for g in _guides():
            with self.subTest(app=g.app):
                self.assertEqual(jargon.findall(_prose(g.body)), [])

    def test_no_link_to_the_stores_own_pages(self):
        for g in _guides():
            with self.subTest(app=g.app):
                self.assertNotRegex(g.body, r'\]\((/|http://)', 'link with a marker, not a URL')
```

- [ ] **Step 6: Run the file tests**

Run: `T plugins.installed.release_notes.tests.test_help_files`
Expected: `OK` (8 tests). Every app is still waiting and no guide exists yet.

- [ ] **Step 7: Lint and commit**

```bash
.venv/bin/ruff check plugins/app_help.py plugins/installed/release_notes/tests/test_app_help.py plugins/installed/release_notes/tests/test_help_files.py
.venv/bin/ruff format plugins/app_help.py plugins/installed/release_notes/tests/test_app_help.py plugins/installed/release_notes/tests/test_help_files.py
git add plugins/app_help.py plugins/installed/release_notes/tests/test_app_help.py plugins/installed/release_notes/tests/test_help_files.py
git commit -m "feat(help): read each app's help.md guide (plugins/app_help.py)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Markers resolve against the live registry

**Files:**
- Create: `plugins/installed/release_notes/help_markers.py`
- Modify: `plugins/installed/release_notes/app.py` (add `requires`)
- Test: `plugins/installed/release_notes/tests/test_help_markers.py`

**Interfaces:**
- Consumes: `app_help.load_manifest`, `app_help.markers`, `app_help.tree_apps`, `app_help.guide`.
- Produces:
  - `Link(label: str, url: str, off: bool = False)`, a frozen dataclass;
  - `resolve(kind, target, *, app, find=None, active=None) -> Link | None`;
  - `ask_list(inst, method) -> list`;
  - `pages_of(inst) -> list`;
  - `panel_of(inst)`;
  - `page_link(page, owner, active) -> Link`;
  - `settings_link(inst, active) -> Link | None`.

- [ ] **Step 1: Write the failing tests**

`plugins/installed/release_notes/tests/test_help_markers.py`:

```python
"""Markers in guides resolve against the live registry (release_notes/help_markers.py).

ResolveTests pin each kind against real apps. GuideMarkerTests walks every guide
in the tree and fails on a marker that names nothing: the check that keeps a
guide's links true when a page moves or a setting is renamed.
"""

from __future__ import annotations

from django.test import TestCase

from plugins import app_help
from plugins.installed.release_notes.help_markers import Link, resolve
from plugins.registry import app_registry


class ResolveTests(TestCase):
    def test_a_page_of_the_guides_own_app(self):
        self.assertEqual(
            resolve('page', 'reviews', app='reviews'),
            Link('Products › Reviews', '/dashboard/reviews/'),
        )

    def test_a_page_of_another_app(self):
        self.assertEqual(
            resolve('page', 'release_notes/version', app='reviews'),
            Link(
                'Settings › Developer › Version & updates',
                '/dashboard/apps/release_notes/version/',
            ),
        )

    def test_an_apps_settings(self):
        self.assertEqual(
            resolve('settings', 'newsletter', app='reviews'),
            Link('Settings › Marketing › Newsletter', '/dashboard/settings/newsletter/'),
        )

    def test_a_settings_field_shows_its_live_label(self):
        self.assertEqual(
            resolve('field', 'newsletter.winback_enabled', app='newsletter'),
            Link('Send win-back emails', '/dashboard/settings/newsletter/'),
        )

    def test_a_sidebar_section(self):
        self.assertEqual(
            resolve('section', 'orders', app='reviews'), Link('Orders', '/dashboard/orders/')
        )

    def test_another_apps_help(self):
        self.assertEqual(
            resolve('app', 'orders', app='reviews'), Link('Orders', '/dashboard/help/orders/')
        )

    def test_a_marker_that_names_nothing(self):
        for kind, target in (
            ('page', 'no_such_page'),
            ('page', 'no_such_app/x'),
            ('settings', 'reviews'),  # reviews has no settings
            ('field', 'newsletter.no_such_key'),
            ('field', 'newsletter'),
            ('section', 'no_such_section'),
            ('app', 'no_such_app'),
            ('nope', 'reviews'),
        ):
            with self.subTest(kind=kind, target=target):
                self.assertIsNone(resolve(kind, target, app='reviews'))

    def test_a_place_in_an_app_that_is_off_has_no_link(self):
        app_registry.deactivate('reviews')
        self.addCleanup(app_registry.activate, 'reviews')
        self.assertEqual(
            resolve('page', 'reviews', app='reviews'), Link('Products › Reviews', '', off=True)
        )


class GuideMarkerTests(TestCase):
    def test_every_marker_in_every_guide_names_something(self):
        broken = []
        for app in app_help.tree_apps():
            found = app_help.guide(app)
            if found is None:
                continue
            for text, kind, target in app_help.markers(found.body):
                link = resolve(
                    kind, target, app=app, find=app_help.load_manifest, active=lambda _n: True
                )
                if link is None:
                    broken.append(f'{app}: [{text}]({kind}:{target})')
        self.assertEqual(broken, [])
```

- [ ] **Step 2: Run them and watch them fail**

Run: `T plugins.installed.release_notes.tests.test_help_markers`
Expected: ERROR, `ModuleNotFoundError: No module named 'plugins.installed.release_notes.help_markers'`.

- [ ] **Step 3: Write the resolver, and declare the dependency it brings**

`plugins/installed/release_notes/help_markers.py`:

```python
"""A guide's markers, resolved against the live registry.

``[text](kind:target)`` in a guide (plugins/app_help.py) names a place instead of
writing its URL, so a moved or renamed page never leaves a dead link:

* ``page:<slug>``: one of the guide's app's dashboard pages; ``page:<app>/<slug>``
  another app's;
* ``settings:<app>``: the app's settings;
* ``field:<app>.<key>``: one field of those settings, by its live label;
* ``section:<key>``: a sidebar section;
* ``app:<name>``: another app's help.

A marker that names nothing resolves to None: the page shows its text without a
link, and tests/test_help_markers.py fails in CI. Everything is asked of the app
itself, so an app that is off still says where its places are.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Link:
    label: str  # the live name, e.g. "Products › Reviews"
    url: str  # '' when the place cannot be opened now
    off: bool = False  # the place exists, but its app is switched off


def ask_list(inst, method: str) -> list:
    """One of an app's ``contribute_*`` lists; a method that raises gives nothing."""
    try:
        return list(getattr(inst, method)() or [])
    except Exception:  # noqa: BLE001 — help describes an app, it never breaks on one
        return []


def pages_of(inst) -> list:
    return ask_list(inst, 'contribute_dashboard_pages')


def panel_of(inst):
    try:
        return inst.contribute_settings_panel()
    except Exception:  # noqa: BLE001
        return None


def page_link(page, owner: str, active: bool) -> Link:
    """Where a dashboard page is, in the dashboard's own words."""
    from plugins.installed.admin_dashboard import navigation

    page.plugin = owner
    url = navigation.page_url(page) if active else ''
    return Link(f'{navigation.page_section_label(page)} › {page.label}', url, off=not active)


def settings_link(inst, active: bool) -> Link | None:
    """Where an app's settings are: its settings panel, else its first settings page."""
    from plugins.installed.admin_dashboard import navigation
    from plugins.installed.admin_dashboard.settings_categories import get_category

    panel = panel_of(inst)
    if panel is not None:
        cat = get_category(navigation.settings_category_key(panel.category) or 'apps')
        label = f'Settings › {cat.label if cat else "Settings"} › {panel.label or inst.label}'
        url = f'/dashboard/settings/{inst.name}/' if active else ''
        return Link(label, url, off=not active)
    for page in pages_of(inst):
        if page.nav == 'settings':
            return page_link(page, inst.name, active)
    return None


def _registry_find(name: str):
    from plugins.registry import app_registry

    return app_registry.get(name)


def _registry_active(name: str) -> bool:
    from plugins.registry import app_registry

    return app_registry.is_active(name)


def _section(key: str) -> Link | None:
    from plugins.installed.admin_dashboard import navigation

    sec = navigation.section(key)
    if sec is None:
        return None
    url = sec.url or next(
        (t.url for t in navigation.tabs() if t.section == key and t.nav == 'main'), ''
    )
    return Link(sec.label, url)


def resolve(
    kind: str,
    target: str,
    *,
    app: str,
    find: Callable | None = None,
    active: Callable | None = None,
) -> Link | None:
    """The place a marker names, or None. ``find`` and ``active`` default to the
    live registry; the guide checks pass ``app_help.load_manifest`` so a guide of
    an app this store does not install is checked too."""
    find = find or _registry_find
    active = active or _registry_active
    if kind == 'page':
        owner, _sep, slug = target.rpartition('/')
        owner = owner or app
        inst = find(owner)
        page = next((p for p in pages_of(inst) if p.slug == slug), None) if inst else None
        return page_link(page, owner, active(owner)) if page is not None else None
    if kind == 'settings':
        inst = find(target)
        return settings_link(inst, active(target)) if inst is not None else None
    if kind == 'field':
        owner, _sep, key = target.partition('.')
        inst = find(owner) if key else None
        panel = panel_of(inst) if inst is not None else None
        prop = ((panel.schema or {}).get('properties') or {}).get(key) if panel else None
        if prop is None:
            return None
        where = settings_link(inst, active(owner))
        # The settings form's own label rule (admin_dashboard/urls.py).
        label = prop.get('title') or key.replace('_', ' ').title()
        return Link(label, where.url, off=where.off)
    if kind == 'section':
        return _section(target)
    if kind == 'app':
        inst = find(target)
        return Link(inst.label or target, f'/dashboard/help/{target}/') if inst else None
    return None
```

In `plugins/installed/release_notes/app.py`, add the dependency after `has_models = False`:

```python
    has_models = False
    # Help reads the dashboard's sections, tabs and the Apps catalogue's areas.
    requires = ['admin_dashboard']
```

- [ ] **Step 4: Run the tests and the boundary check**

Run: `T plugins.installed.release_notes.tests.test_help_markers`
Expected: `OK` (9 tests).

Run: `.venv/bin/python scripts/check_plugin_boundary.py`
Expected: `OK: 113 known undeclared plugin->plugin pair(s), no new ones.` The new import is declared in `requires`.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check plugins/installed/release_notes/help_markers.py plugins/installed/release_notes/app.py plugins/installed/release_notes/tests/test_help_markers.py
.venv/bin/ruff format plugins/installed/release_notes/help_markers.py plugins/installed/release_notes/app.py plugins/installed/release_notes/tests/test_help_markers.py
git add plugins/installed/release_notes/help_markers.py plugins/installed/release_notes/app.py plugins/installed/release_notes/tests/test_help_markers.py
git commit -m "feat(help): guide markers resolve to live pages, settings, fields and sections

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Render a guide, and give it to Linda as text

**Files:**
- Create: `plugins/installed/release_notes/help_render.py`
- Test: `plugins/installed/release_notes/tests/test_help_render.py`

**Interfaces:**
- Consumes: `app_help.MARKER_RE`, `help_markers.resolve`.
- Produces:
  - `render(body, *, app) -> SafeString`;
  - `plain(body, *, app) -> str`: markers become their name plus path, for Linda;
  - `readable(body, *, app) -> str`: words only, for search.

- [ ] **Step 1: Write the failing tests**

`plugins/installed/release_notes/tests/test_help_render.py`:

```python
"""A guide's Markdown as safe HTML, and as text for Linda and search."""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.release_notes.help_render import plain, readable, render
from plugins.registry import app_registry


class RenderTests(TestCase):
    def _html(self, body: str) -> str:
        return str(render(body, app='reviews'))

    def test_headings_paragraphs_and_lists(self):
        html = self._html(
            "## What it's for\n\nOne line\nand the next.\n\n- a\n- b\n\n1. first\n2. second\n\n### Detail"
        )
        self.assertIn('<h2>What it&#x27;s for</h2>', html)
        self.assertIn('<p>One line and the next.</p>', html)
        self.assertIn('<ul>\n<li>a</li>\n<li>b</li>\n</ul>', html)
        self.assertIn('<ol>\n<li>first</li>\n<li>second</li>\n</ol>', html)
        self.assertIn('<h3>Detail</h3>', html)

    def test_bold_code_and_outside_links(self):
        html = self._html('**Bold** and `code` and [Stripe](https://dashboard.stripe.com/apikeys).')
        self.assertIn('<strong>Bold</strong>', html)
        self.assertIn('<code>code</code>', html)
        self.assertIn(
            '<a href="https://dashboard.stripe.com/apikeys" rel="noopener" target="_blank">Stripe</a>',
            html,
        )

    def test_a_marker_becomes_a_link_to_the_live_place(self):
        self.assertIn(
            '<a href="/dashboard/reviews/">the Reviews tab</a>',
            self._html('Open [the Reviews tab](page:reviews).'),
        )

    def test_an_empty_marker_shows_the_live_label(self):
        self.assertIn(
            '<a href="/dashboard/reviews/">Products › Reviews</a>',
            self._html('Open [](page:reviews).'),
        )

    def test_a_marker_that_names_nothing_is_plain_text(self):
        html = self._html('See [the old page](page:gone).')
        self.assertIn('See the old page.', html)
        self.assertNotIn('<a', html)

    def test_a_place_in_an_app_that_is_off(self):
        app_registry.deactivate('reviews')
        self.addCleanup(app_registry.activate, 'reviews')
        self.assertIn(
            'the Reviews tab <span class="help-off">(when the app is on)</span>',
            self._html('Open [the Reviews tab](page:reviews).'),
        )

    def test_everything_else_is_escaped(self):
        html = self._html('<script>alert(1)</script> [x](javascript:alert(1)) & "quoted"')
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('href="javascript', html)
        self.assertIn('&amp; &quot;quoted&quot;', html)


class TextTests(TestCase):
    def test_plain_text_for_linda_names_the_paths(self):
        self.assertEqual(
            plain(
                '**Open** [the Reviews tab](page:reviews), then `Approve`. [Stripe](https://stripe.com).',
                app='reviews',
            ),
            'Open the Reviews tab (/dashboard/reviews/), then Approve. Stripe (https://stripe.com).',
        )

    def test_readable_text_for_search_has_no_paths(self):
        self.assertEqual(
            readable("## What it's for\n\nOpen [](page:reviews).", app='reviews'),
            "What it's for\n\nOpen Products › Reviews.",
        )
```

- [ ] **Step 2: Run them and watch them fail**

Run: `T plugins.installed.release_notes.tests.test_help_render`
Expected: ERROR, `ModuleNotFoundError: No module named 'plugins.installed.release_notes.help_render'`.

- [ ] **Step 3: Write the renderer**

`plugins/installed/release_notes/help_render.py`:

```python
"""A guide's Markdown as safe HTML for the Help page, and as text.

The subset guides use: ``##``/``###`` headings, paragraphs, ``-`` and ``1.`` lists,
``**bold**``, `` `code` ``, ``https://`` links and markers (help_markers.py).
Every character is escaped before a tag is added, so marking the HTML safe is
sound. ``plain`` is the guide for Linda (markers become names and paths) and
``readable`` the words search matches.
"""

from __future__ import annotations

import html
import re

from django.utils.safestring import SafeString, mark_safe

from plugins import app_help
from plugins.installed.release_notes import help_markers

_URL_LINK = re.compile(r'\[([^\]]+)\]\((https://[^)\s]+)\)')
_BOLD = re.compile(r'\*\*([^*]+)\*\*')
_CODE = re.compile(r'`([^`]+)`')
_HEAD = re.compile(r'^(#{2,3})\s+(.*)$')
_BULLET = re.compile(r'^[-*]\s+(.*)$')
_NUMBER = re.compile(r'^\d+[.)]\s+(.*)$')


def _marker_html(m, app: str) -> str:
    text, kind, target = m.group(1), m.group(2), m.group(3)  # text is escaped already
    link = help_markers.resolve(kind, target, app=app)
    if link is None:
        return text
    shown = text or html.escape(link.label)
    if link.url:
        return f'<a href="{html.escape(link.url)}">{shown}</a>'
    if link.off:
        return f'{shown} <span class="help-off">(when the app is on)</span>'
    return shown


def _inline(text: str, app: str) -> str:
    t = html.escape(text)
    t = app_help.MARKER_RE.sub(lambda m: _marker_html(m, app), t)
    t = _URL_LINK.sub(r'<a href="\2" rel="noopener" target="_blank">\1</a>', t)
    t = _BOLD.sub(r'<strong>\1</strong>', t)
    return _CODE.sub(r'<code>\1</code>', t)


def render(body: str, *, app: str) -> SafeString:
    """The guide's body as HTML."""
    out: list[str] = []
    para: list[str] = []
    open_list = ''

    def flush() -> None:
        if para:
            out.append('<p>' + ' '.join(para) + '</p>')
            para.clear()

    def close() -> None:
        nonlocal open_list
        if open_list:
            out.append(f'</{open_list}>')
            open_list = ''

    for raw in body.split('\n'):
        line = raw.strip()
        if not line:
            flush()
            close()
            continue
        head = _HEAD.match(line)
        if head:
            flush()
            close()
            level = len(head.group(1))
            out.append(f'<h{level}>{_inline(head.group(2), app)}</h{level}>')
            continue
        item, tag = _BULLET.match(line), 'ul'
        if item is None:
            item, tag = _NUMBER.match(line), 'ol'
        if item is not None:
            flush()
            if open_list != tag:
                close()
                out.append(f'<{tag}>')
                open_list = tag
            out.append(f'<li>{_inline(item.group(1), app)}</li>')
            continue
        close()
        para.append(_inline(line, app))
    flush()
    close()
    return mark_safe('\n'.join(out))  # noqa: S308 — every character escaped in _inline


def plain(body: str, *, app: str) -> str:
    """The guide as text for Linda: markers become their names and paths."""

    def marker(m) -> str:
        link = help_markers.resolve(m.group(2), m.group(3), app=app)
        if link is None:
            return m.group(1)
        name = m.group(1) or link.label
        if link.url:
            return f'{name} ({link.url})'
        return f'{name} (when the app is on)' if link.off else name

    text = app_help.MARKER_RE.sub(marker, body)
    text = _URL_LINK.sub(r'\1 (\2)', text)
    return _BOLD.sub(r'\1', text).replace('`', '')


def readable(body: str, *, app: str) -> str:
    """The guide as words only, for search: no paths, no Markdown marks."""

    def marker(m) -> str:
        if m.group(1):
            return m.group(1)
        link = help_markers.resolve(m.group(2), m.group(3), app=app)
        return link.label if link is not None else ''

    text = app_help.MARKER_RE.sub(marker, body)
    text = _URL_LINK.sub(r'\1', text)
    text = re.sub(r'(?m)^#{1,6}\s+', '', text)
    return _BOLD.sub(r'\1', text).replace('`', '')
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `T plugins.installed.release_notes.tests.test_help_render`
Expected: `OK` (9 tests).

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check plugins/installed/release_notes/help_render.py plugins/installed/release_notes/tests/test_help_render.py
.venv/bin/ruff format plugins/installed/release_notes/help_render.py plugins/installed/release_notes/tests/test_help_render.py
git add plugins/installed/release_notes/help_render.py plugins/installed/release_notes/tests/test_help_render.py
git commit -m "feat(help): render guides as escaped HTML, and as text for Linda and search

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: The facts nobody writes down

**Files:**
- Modify: `core/hooks.py` (add `HookRegistry.events_of` after `list_handlers`)
- Modify: `plugins/registry.py` (add `AppRegistry.url_prefixes` after `dashboard_url_mounts`)
- Create: `plugins/installed/release_notes/help_facts.py`
- Test: `plugins/installed/release_notes/tests/test_help_facts.py`

**Interfaces:**
- Consumes: `help_markers.ask_list`, `pages_of`, `page_link`, `settings_link`, `Link`.
- Produces:
  - `hook_registry.events_of(plugin) -> list[str]`;
  - `app_registry.url_prefixes(name) -> list[str]`;
  - `help_facts.SLOT_WORDS: dict[str, str]`;
  - `help_facts.facts(name) -> dict | None`, with keys `name, label, version, description, active, area, area_label, places (list[Link]), cards (list[str]), shop (list[str]), tools (list[dict name/description/asks_first]), requires, required_by, events, slots, urls`.

- [ ] **Step 1: Write the failing tests**

`plugins/installed/release_notes/tests/test_help_facts.py`:

```python
"""What the Help page says about an app without anyone writing it down."""

from __future__ import annotations

from unittest import mock

from django.test import TestCase

from core.hooks import MorpheusEvents
from plugins import app_help
from plugins.installed.release_notes.help_facts import SLOT_WORDS, facts
from plugins.installed.release_notes.help_markers import Link, ask_list
from plugins.registry import app_registry


class FactsTests(TestCase):
    def test_where_reviews_are_and_what_linda_can_do_there(self):
        f = facts('reviews')
        self.assertEqual(f['label'], 'Reviews')
        self.assertTrue(f['active'])
        self.assertIn(Link('Products › Reviews', '/dashboard/reviews/'), f['places'])
        self.assertEqual(
            {t['name']: t['asks_first'] for t in f['tools']},
            {'reviews.list_pending': False, 'reviews.approve': True, 'reviews.delete': True},
        )
        self.assertEqual(f['shop'], ['the product page, under the buy form'])
        self.assertEqual(f['requires'], ['catalog', 'orders'])
        self.assertIn(MorpheusEvents.ACTIVITY_FEED, f['events'])
        self.assertIn('/dashboard/reviews/', f['urls'])
        self.assertIn('/reviews/', f['urls'])

    def test_an_apps_settings_are_a_place(self):
        self.assertIn(
            Link('Settings › Marketing › Newsletter', '/dashboard/settings/newsletter/'),
            facts('newsletter')['places'],
        )

    def test_what_needs_an_app(self):
        self.assertIn('reviews', facts('catalog')['required_by'])

    def test_an_app_that_is_off_lists_its_places_without_links(self):
        app_registry.deactivate('reviews')
        self.addCleanup(app_registry.activate, 'reviews')
        f = facts('reviews')
        self.assertFalse(f['active'])
        self.assertTrue(f['places'])
        self.assertTrue(all(p.url == '' and p.off for p in f['places']))

    def test_an_app_whose_pages_raise_still_has_facts(self):
        inst = app_registry.get('reviews')
        with mock.patch.object(
            type(inst), 'contribute_dashboard_pages', side_effect=RuntimeError('boom')
        ):
            f = facts('reviews')
        self.assertEqual(f['places'], [])
        self.assertEqual(f['label'], 'Reviews')

    def test_no_such_app(self):
        self.assertIsNone(facts('no_such_app'))


class SlotWordsTests(TestCase):
    def test_every_slot_an_app_fills_has_plain_words(self):
        slots = {b.slot for b in app_registry._storefront_blocks}
        for name in app_help.tree_apps():
            inst = app_help.load_manifest(name)
            if inst is not None:
                slots |= {b.slot for b in ask_list(inst, 'contribute_storefront_blocks')}
        self.assertEqual(sorted(slots - set(SLOT_WORDS)), [])
```

- [ ] **Step 2: Run them and watch them fail**

Run: `T plugins.installed.release_notes.tests.test_help_facts`
Expected: ERROR, `ModuleNotFoundError: No module named 'plugins.installed.release_notes.help_facts'`.

- [ ] **Step 3: Add the two registry accessors**

In `core/hooks.py`, right after the `list_handlers` method of the hook registry class:

```python
    def events_of(self, plugin: str) -> list[str]:
        """Every event a plugin's handlers listen to, sorted (the Help page's
        technical details). Empty for an app whose ready() has not run."""
        return sorted(
            event
            for event, entries in self._handlers.items()
            if any(entry[3] == plugin for entry in entries)
        )
```

In `plugins/registry.py`, right after the `dashboard_url_mounts` method:

```python
    def url_prefixes(self, name: str) -> list[str]:
        """The URL prefixes an app mounts its own routes under ('/' for the root)."""
        return [
            '/' + (entry.get('prefix') or '')
            for entry in self._plugin_urls
            if entry.get('plugin') == name
        ]
```

- [ ] **Step 4: Write the facts module**

`plugins/installed/release_notes/help_facts.py`:

```python
"""What the Help page says about an app that nobody writes down: where its
screens and settings are, what it adds to the shop, what Linda can do with it,
and its technical details. Read from the running code on every request, so it
cannot go stale, and asked of the app itself, so an app that is off still
answers.
"""

from __future__ import annotations

from plugins.installed.release_notes import help_markers

#: Storefront slots in a merchant's words. A slot an app fills that is missing
#: here shows its raw name, and tests/test_help_facts.py fails.
SLOT_WORDS: dict[str, str] = {
    'account_nav': "the shopper's account menu",
    'account_summary_extra': "the shopper's account overview",
    'auth_login_extra': 'the sign-in page',
    'cart_summary_extra': 'the cart summary',
    'checkout_extra': 'the checkout page',
    'footer_extra': 'the shop footer',
    'footer_legal': "the footer's legal links",
    'global_below_body': 'every shop page, at the end',
    'global_head': 'every shop page, out of sight in the page head',
    'home_above_grid': 'the home page, above the products',
    'home_after_rails': 'the home page, after the product rows',
    'home_below_grid': 'the home page, below the products',
    'journal': 'journal posts',
    'listing_below_description': "an experience's page, below its description",
    'order_receipt_extra': 'the order confirmation page',
    'pdp_above_long_description': 'the product page, above the long description',
    'pdp_below_form': 'the product page, under the buy form',
    'pdp_below_gallery': 'the product page, under the photos',
    'pdp_below_long_description': 'the product page, below the long description',
    'pdp_below_price': 'the product page, under the price',
}


def facts(name: str) -> dict | None:
    """Everything the Help page generates for one installed app, or None."""
    from core.assistant import gates
    from core.hooks import hook_registry
    from plugins.installed.admin_dashboard import navigation
    from plugins.registry import app_registry

    inst = app_registry.get(name)
    if inst is None:
        return None
    on = app_registry.is_active(name)
    places = [
        help_markers.page_link(p, name, on)
        for p in help_markers.pages_of(inst)
        if p.nav != 'hidden'
    ]
    where = help_markers.settings_link(inst, on)
    if where is not None and where not in places:
        places.append(where)
    cards = []
    for card in help_markers.ask_list(inst, 'contribute_dashboard_cards'):
        key = navigation.main_section_key(card.section)
        line = f'a card on {navigation.section_label(key)}' if key else ''
        if line and line not in cards:
            cards.append(line)
    blocks = help_markers.ask_list(inst, 'contribute_storefront_blocks')
    slots = list(dict.fromkeys(b.slot for b in blocks))
    tools = help_markers.ask_list(inst, 'contribute_agent_tools')
    described = navigation.describe_app(inst)
    return {
        'name': name,
        'label': inst.label or name,
        'version': inst.version,
        'description': inst.description,
        'active': on,
        'area': described['area'],
        'area_label': described['area_label'],
        'places': places,
        'cards': cards,
        'shop': [SLOT_WORDS.get(s, s) for s in slots],
        'tools': [
            {
                'name': t.name,
                'description': t.description,
                'asks_first': gates.is_write_tool(t),
            }
            for t in tools
        ],
        'requires': list(inst.requires or []),
        'required_by': sorted(
            p.name for p in app_registry.all_plugins() if name in (p.requires or [])
        ),
        'events': hook_registry.events_of(name),
        'slots': slots,
        'urls': app_registry.url_prefixes(name),
    }
```

- [ ] **Step 5: Run the tests and the core boundary check**

Run: `T plugins.installed.release_notes.tests.test_help_facts`
Expected: `OK` (7 tests).

Run: `.venv/bin/python scripts/check_core_boundary.py`
Expected: `OK: 0 known core->plugin import(s), no new ones.`

- [ ] **Step 6: Lint and commit**

```bash
.venv/bin/ruff check core/hooks.py plugins/registry.py plugins/installed/release_notes/help_facts.py plugins/installed/release_notes/tests/test_help_facts.py
.venv/bin/ruff format core/hooks.py plugins/registry.py plugins/installed/release_notes/help_facts.py plugins/installed/release_notes/tests/test_help_facts.py
git add core/hooks.py plugins/registry.py plugins/installed/release_notes/help_facts.py plugins/installed/release_notes/tests/test_help_facts.py
git commit -m "feat(help): generate where an app lives, what it adds and what Linda can do there

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: The Help pages

**Files:**
- Create:
  - `plugins/installed/release_notes/urls.py`
  - `plugins/installed/release_notes/help_views.py`
  - `plugins/installed/release_notes/templates/release_notes/help_index.html`
  - `plugins/installed/release_notes/templates/release_notes/help_app.html`
  - `plugins/installed/release_notes/templates/release_notes/_help_app_list.html`
  - `plugins/installed/release_notes/templates/release_notes/_help_styles.html`
  - `plugins/installed/release_notes/help.md` (the first guide)
- Modify:
  - `plugins/installed/release_notes/app.py`: `ready()` mounts the URLs; the Help page points at `/dashboard/help/`.
  - `plugins/installed/release_notes/views.py`: delete `help_page`.
  - `plugins/installed/release_notes/tests/test_release_notes.py`: Help is no longer framed.
  - `plugins/installed/release_notes/tests/test_help_files.py`: drop `'release_notes'` from `_AWAITING_A_GUIDE`.
- Test: `plugins/installed/release_notes/tests/test_help_pages.py`

**Interfaces:**
- Consumes: `app_help.guide`, `app_help.summary`, `help_facts.facts`, `help_render.render`.
- Produces:
  - URL namespace `help` (`help:index` → `/dashboard/help/`, `help:app` → `/dashboard/help/<app>/`);
  - views `help_views.help_index`, `help_app`, `help_redirect`;
  - CSS class `help-guide`, and the data attributes `data-help-area`, `data-help-off`, `data-help-places`, `data-help-tools`.

- [ ] **Step 1: Write the failing page tests**

`plugins/installed/release_notes/tests/test_help_pages.py`:

```python
"""The Help area's pages: /dashboard/help/ and /dashboard/help/<app>/."""

from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.registry import app_registry

_OFF_SAMPLE = (
    'reviews',
    'newsletter',
    'feedback',
    'gift_cards',
    'webstories',
    'crm',
    'dynamics',
    'tax',
)


def _set_roles(mode: str) -> None:
    plugin = app_registry.get('rbac')
    plugin.set_config('enforcement_mode', mode)
    plugin.invalidate_config_cache()


class HelpPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            username='help-staff', email='help@example.test', password='pw', is_staff=True
        )

    def setUp(self):
        self.client.force_login(self.staff)

    def _get(self, url: str) -> str:
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, url)
        return resp.content.decode()

    def _section(self, html: str, marker: str) -> str:
        start = html.index(marker)
        return html[start : html.index('</section>', start)]

    def test_the_index_lists_the_apps_that_are_on_by_area(self):
        html = self._get('/dashboard/help/')
        self.assertIn('href="/dashboard/help/reviews/"', self._section(html, 'data-help-area="Products"'))
        self.assertNotIn('data-help-off', html)

    def test_an_app_that_is_off_is_listed_apart(self):
        app_registry.deactivate('reviews')
        self.addCleanup(app_registry.activate, 'reviews')
        html = self._get('/dashboard/help/')
        self.assertIn('href="/dashboard/help/reviews/"', self._section(html, 'data-help-off'))

    def test_every_installed_app_has_a_page(self):
        for inst in app_registry.all_plugins():
            with self.subTest(app=inst.name):
                self._get(f'/dashboard/help/{inst.name}/')

    def test_an_app_page_works_while_the_app_is_off(self):
        for name in _OFF_SAMPLE:
            with self.subTest(app=name):
                app_registry.deactivate(name)
                try:
                    html = self._get(f'/dashboard/help/{name}/')
                finally:
                    app_registry.activate(name)
                self.assertIn('<span class="pill pill-neutral">Off</span>', html)
                self.assertIn('This app is switched off.', html)

    def test_a_guide_renders_and_its_markers_link(self):
        html = self._get('/dashboard/help/release_notes/')
        self.assertIn('<h2>What it&#x27;s for</h2>', html)
        self.assertIn('href="/dashboard/apps/release_notes/version/"', html)

    def test_an_app_without_a_guide_says_so(self):
        with mock.patch('plugins.app_help.guide', return_value=None):
            html = self._get('/dashboard/help/reviews/')
        self.assertIn('This app has no guide yet.', html)

    def test_where_to_find_it_and_what_linda_can_do(self):
        html = self._get('/dashboard/help/reviews/')
        self.assertIn(
            '<a href="/dashboard/reviews/">Products › Reviews</a>',
            self._section(html, 'data-help-places'),
        )
        tools = self._section(html, 'data-help-tools')
        self.assertIn('What Linda can do here', tools)
        self.assertIn('asks you first', tools)

    def test_a_broken_manifest_still_has_a_page(self):
        inst = app_registry.get('reviews')
        with mock.patch.object(
            type(inst), 'contribute_dashboard_pages', side_effect=RuntimeError('boom')
        ):
            self._get('/dashboard/help/reviews/')

    def test_a_label_with_markup_is_escaped(self):
        inst = app_registry.get('reviews')
        with mock.patch.object(type(inst), 'label', 'Reviews <b>&</b>'):
            for url in ('/dashboard/help/', '/dashboard/help/reviews/'):
                html = self._get(url)
                self.assertIn('Reviews &lt;b&gt;&amp;&lt;/b&gt;', html)
                self.assertNotIn('Reviews <b>&</b>', html)

    def test_an_unknown_app_is_404(self):
        for name in ('no_such_app', 'REVIEWS'):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(f'/dashboard/help/{name}/').status_code, 404)
        self.assertEqual(self.client.get('/dashboard/help/../etc/').status_code, 404)

    def test_signed_out_visitors_are_sent_to_sign_in(self):
        self.client.logout()
        self.assertEqual(self.client.get('/dashboard/help/').status_code, 302)

    def test_staff_without_a_role_read_help_while_roles_are_enforced(self):
        _set_roles('enforce')
        self.addCleanup(app_registry.get('rbac').invalidate_config_cache)
        self._get('/dashboard/help/')
        self._get('/dashboard/help/reviews/')

    def test_the_old_address_redirects(self):
        resp = self.client.get('/dashboard/apps/release_notes/help/')
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp['Location'], '/dashboard/help/')
```

- [ ] **Step 2: Run them and watch them fail**

Run: `T plugins.installed.release_notes.tests.test_help_pages`
Expected: FAIL. Every request to `/dashboard/help/...` answers 404, because no URL is mounted yet.

- [ ] **Step 3: Write the views and URLs**

`plugins/installed/release_notes/help_views.py`:

```python
"""The Help area: /dashboard/help/ and /dashboard/help/<app>/.

Every staff member may read help, whatever their role: no capability is held by
every role (rbac's templates), and help shows documentation, not store data. The
screens it links to still check access themselves.
Spec: docs/superpowers/specs/2026-10-18-help-system-design.md.
"""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, HttpResponsePermanentRedirect
from django.shortcuts import render

from plugins import app_help
from plugins.installed.release_notes import help_facts, help_render


def _entries() -> list[dict]:
    """One row per installed app, for the index."""
    from plugins.installed.admin_dashboard import navigation
    from plugins.registry import app_registry

    rows = []
    for inst in app_registry.all_plugins():
        rows.append(
            {
                'name': inst.name,
                'label': inst.label or inst.name,
                'summary': app_help.summary(inst.name) or inst.description,
                'area': navigation.describe_app(inst)['area'],
                'active': app_registry.is_active(inst.name),
            }
        )
    return rows


def _groups(rows: list[dict]) -> list[dict]:
    """``[{'label', 'apps'}]`` in the Apps catalogue's area order."""
    from plugins.installed.admin_dashboard import navigation

    order = {key: i for i, (key, _label) in enumerate(navigation.CATALOGUE_AREAS)}
    labels = dict(navigation.CATALOGUE_AREAS)
    groups: dict[str, list] = {}
    for row in rows:
        groups.setdefault(row['area'], []).append(row)
    return [
        {
            'label': labels.get(key, key.title()),
            'apps': sorted(apps, key=lambda r: r['label'].casefold()),
        }
        for key, apps in sorted(groups.items(), key=lambda kv: order.get(kv[0], len(order)))
    ]


@staff_member_required
def help_index(request):
    rows = _entries()
    return render(
        request,
        'release_notes/help_index.html',
        {
            'groups': _groups([r for r in rows if r['active']]),
            'off': sorted((r for r in rows if not r['active']), key=lambda r: r['label'].casefold()),
            'active_nav': 'settings',
        },
    )


@staff_member_required
def help_app(request, app: str):
    found = help_facts.facts(app)
    if found is None:
        raise Http404('No such app.')
    guide = app_help.guide(app)
    return render(
        request,
        'release_notes/help_app.html',
        {
            'facts': found,
            'summary': guide.summary if guide else found['description'],
            'guide_html': help_render.render(guide.body, app=app) if guide else '',
            'active_nav': 'settings',
        },
    )


@staff_member_required
def help_redirect(request):
    """The Help card's old address, /dashboard/apps/release_notes/help/."""
    return HttpResponsePermanentRedirect('/dashboard/help/')
```

`plugins/installed/release_notes/urls.py`:

```python
"""The Help area, mounted at /dashboard/help/ by ReleaseNotesPlugin.ready()."""

from django.urls import path

from plugins.installed.release_notes import help_views

app_name = 'help'

urlpatterns = [
    path('', help_views.help_index, name='index'),
    path('<slug:app>/', help_views.help_app, name='app'),
]
```

- [ ] **Step 4: Write the templates**

`plugins/installed/release_notes/templates/release_notes/_help_app_list.html`:

```django
<ul class="help__apps">
  {% for app in apps %}
  <li><a href="{% url 'help:app' app.name %}" class="help__app">{{ app.label }}</a>{% if app.summary %}<span class="help__summary">{{ app.summary }}</span>{% endif %}</li>
  {% endfor %}
</ul>
```

`plugins/installed/release_notes/templates/release_notes/_help_styles.html`:

```django
<style>
  .help a { color: var(--brand); }
  .help a:hover { text-decoration: underline; }
  .help__area { font-size: .95rem; font-weight: 600; margin: 0 0 .65rem; }
  .help__apps { list-style: none; margin: 0; padding: 0; display: grid; gap: .6rem; }
  .help__apps li { display: grid; gap: .1rem; }
  .help__app { font-weight: 500; }
  .help__summary { font-size: .82rem; color: var(--text-muted); }
  .help__list { list-style: disc; margin: 0; padding-left: 1.25rem; display: grid; gap: .35rem; font-size: .9rem; }
  .help__tech { display: grid; grid-template-columns: max-content 1fr; gap: .35rem 1rem; margin: .75rem 0 0; font-size: .85rem; }
  .help__tech dt { color: var(--text-muted); }
  .help__tech dd { margin: 0; overflow-wrap: anywhere; }
  .help__toggle { cursor: pointer; margin: 0; }
  .help-guide h2 { font-size: 1rem; font-weight: 600; margin: 1.15rem 0 .4rem; }
  .help-guide h2:first-child { margin-top: 0; }
  .help-guide h3 { font-size: .9rem; font-weight: 600; margin: .9rem 0 .3rem; }
  .help-guide p { margin: 0 0 .7rem; font-size: .9rem; line-height: 1.6; }
  .help-guide ul, .help-guide ol { margin: 0 0 .8rem; padding-left: 1.25rem; font-size: .9rem; line-height: 1.6; }
  .help-guide ul { list-style: disc; }
  .help-guide ol { list-style: decimal; }
  .help-guide code { font-size: .82rem; padding: .05rem .3rem; border-radius: var(--radius-sm); background: var(--surface-2); }
  .help-off { color: var(--text-muted); font-size: .82rem; }
  .help__results { list-style: none; margin: 0; padding: 0; display: grid; gap: .75rem; }
  .help__snippet { font-size: .82rem; color: var(--text-muted); }
  .help__search { display: flex; gap: .5rem; }
  .help__search input { flex: 1; min-width: 0; }
  @media (max-width: 640px) { .help__tech { grid-template-columns: 1fr; } }
</style>
```

`plugins/installed/release_notes/templates/release_notes/help_index.html`:

```django
{% extends "admin_dashboard/base.html" %}
{% block title %}Help · Morpheus{% endblock %}

{% block content %}
{% comment %}The Help index (release_notes/help_views.py): the apps that are on,
grouped the way the Apps catalogue groups them, then the apps that are off. Each
sentence is the app's own help.md summary.{% endcomment %}
<div class="help max-w-4xl mx-auto space-y-5">
  <div>
    <h1 class="text-xl font-semibold tracking-tight">Help</h1>
    <p class="text-sm text-[color:var(--text-muted)]">What each app does, how to set it up and where to find it. New here? Start with <a href="{% url 'help:app' 'admin_dashboard' %}">how the dashboard works</a>.</p>
  </div>
  {% for group in groups %}
  <section class="card card-padded" data-help-area="{{ group.label }}">
    <h2 class="help__area">{{ group.label }}</h2>
    {% include "release_notes/_help_app_list.html" with apps=group.apps %}
  </section>
  {% endfor %}
  {% if off %}
  <section class="card card-padded" data-help-off>
    <h2 class="help__area">Not switched on</h2>
    {% include "release_notes/_help_app_list.html" with apps=off %}
  </section>
  {% endif %}
</div>
{% include "release_notes/_help_styles.html" %}
{% endblock %}
```

`plugins/installed/release_notes/templates/release_notes/help_app.html`:

```django
{% extends "admin_dashboard/base.html" %}
{% block title %}{{ facts.label }} · Help · Morpheus{% endblock %}

{% block content %}
{% comment %}One app's help (release_notes/help_views.py): its guide (help.md), then
what the running code says about it: where its screens are, what Linda can do
there and the technical details.{% endcomment %}
<div class="help max-w-4xl mx-auto space-y-5">
  <p class="text-sm"><a href="{% url 'help:index' %}">← All help</a></p>
  <header class="space-y-1">
    <div class="flex items-center gap-2 flex-wrap">
      <h1 class="text-xl font-semibold tracking-tight">{{ facts.label }}</h1>
      {% if facts.active %}<span class="pill pill-success">On</span>{% else %}<span class="pill pill-neutral">Off</span>{% endif %}
    </div>
    {% if summary %}<p class="text-sm text-[color:var(--text-muted)]">{{ summary }}</p>{% endif %}
    {% if not facts.active %}<p class="text-sm">This app is switched off. An admin can switch it on in <a href="/dashboard/apps/">Settings › Apps</a>; until then its screens are listed without links.</p>{% endif %}
  </header>

  <section class="card card-padded help-guide">
    {% if guide_html %}{{ guide_html }}{% else %}<p class="text-sm text-[color:var(--text-muted)]">This app has no guide yet.</p>{% endif %}
  </section>

  {% if facts.places or facts.cards or facts.shop %}
  <section class="card card-padded" data-help-places>
    <h2 class="help__area">Where to find it</h2>
    <ul class="help__list">
      {% for place in facts.places %}<li>{% if place.url %}<a href="{{ place.url }}">{{ place.label }}</a>{% else %}{{ place.label }}{% endif %}</li>{% endfor %}
      {% for card in facts.cards %}<li>{{ card|capfirst }}</li>{% endfor %}
      {% for spot in facts.shop %}<li>In the shop: {{ spot }}</li>{% endfor %}
    </ul>
  </section>
  {% endif %}

  {% if facts.tools %}
  <section class="card card-padded" data-help-tools>
    <h2 class="help__area">What Linda can do here</h2>
    <ul class="help__list">
      {% for tool in facts.tools %}<li>{{ tool.description }}{% if tool.asks_first %} <span class="pill pill-warn pill-xs">asks you first</span>{% endif %}</li>{% endfor %}
    </ul>
  </section>
  {% endif %}

  <details class="card card-padded">
    <summary class="help__area help__toggle">Technical details</summary>
    <dl class="help__tech">
      <dt>Name</dt><dd><code>{{ facts.name }}</code> · v{{ facts.version }}</dd>
      {% if facts.description %}<dt>Description</dt><dd>{{ facts.description }}</dd>{% endif %}
      <dt>Requires</dt><dd>{{ facts.requires|join:", "|default:"nothing" }}</dd>
      <dt>Required by</dt><dd>{{ facts.required_by|join:", "|default:"nothing" }}</dd>
      <dt>Listens to</dt><dd>{{ facts.events|join:", "|default:"nothing" }}</dd>
      <dt>Shop slots</dt><dd>{{ facts.slots|join:", "|default:"none" }}</dd>
      <dt>URL prefixes</dt><dd>{{ facts.urls|join:", "|default:"none" }}</dd>
      <dt>Agent tools</dt><dd>{% for tool in facts.tools %}<code>{{ tool.name }}</code>{% if not forloop.last %}, {% endif %}{% empty %}none{% endfor %}</dd>
    </dl>
  </details>
</div>
{% include "release_notes/_help_styles.html" %}
{% endblock %}
```

- [ ] **Step 5: Mount the area and retire the framed Help page**

In `plugins/installed/release_notes/app.py`:

1. Replace the module docstring's first bullet ("**Help** and **About Morpheus OS** — …") with:

   ```
   * **Help**: /dashboard/help/, every app's guide (its own
     ``plugins/installed/<app>/help.md``) and what the running code says about it,
     searchable and readable by Linda. Spec:
     docs/superpowers/specs/2026-10-18-help-system-design.md.
   * **About Morpheus OS**: the project website's About page in its embed mode.
   ```

2. Add `ready()` to the class, above `contribute_dashboard_pages`:

   ```python
       def ready(self) -> None:
           self.register_urls(
               'plugins.installed.release_notes.urls', prefix='dashboard/help/', namespace='help'
           )
   ```

3. Replace the Help `DashboardPage` with:

   ```python
               DashboardPage(
                   label='Help',
                   slug='help',
                   view='plugins.installed.release_notes.help_views.help_redirect',
                   icon='help-circle',
                   section='developer',
                   order=93,
                   nav='settings',
                   hint='What every app does and where to find it',
                   url='/dashboard/help/',
               ),
   ```

4. Set `version = '1.2.0'` and the description to:

   ```python
       description = (
           "Help for every app (each app's own guide plus what the running code says "
           "about it), About Morpheus OS (the project website's page) and the Version & "
           'updates changelog (renders docs/RELEASE_NOTES.md next to the running version).'
       )
   ```

In `plugins/installed/release_notes/views.py`, delete the `help_page` function, which is the whole last block:

```python
@staff_member_required
@require_capability('system.read')
def help_page(request):
    """Help — the website's guide to the dashboard."""
    return _site_page(request, 'help.html', 'Help')
```

In `_site_page`'s docstring, change "Help and About are written once on the website" to "About is written once on the website". Leave every other line.

In `plugins/installed/release_notes/tests/test_release_notes.py`, change `SitePageTests`:

- Replace the docstring's first sentence with "About lives on the project website and opens embedded here."
- In `test_about_and_help_embed_the_website_pages`, rename it to `test_about_embeds_the_website_page` and change the loop to `for slug, page in (('about', 'about.html'),):`.
- In `test_the_account_menu_links_help_and_about`, change the Help assertion to `self.assertIn('href="/dashboard/help/"', html)`.

- [ ] **Step 6: Write the first guide, then stop waiting for it**

`plugins/installed/release_notes/help.md`:

```markdown
---
summary: The help you are reading, plus About Morpheus OS and the version this store runs with every release's notes.
---

## What it's for

This app keeps the store's own documentation inside the dashboard. Every app has a page here: what it is for, how to set it up, the jobs people use it for, and where its screens and settings are. The lists of screens, settings and Linda's abilities are read from the running store each time you open a page, so they match what you see in the menus.

It also holds [About Morpheus OS](page:about), the project's page about the platform and its licence, and [Version & updates](page:version), which shows the version this store runs, any update that is waiting, and the notes for every release.

## Common tasks

- Find an app by typing a word into the search box at the top of the Help page.
- Open the help for the page you are on with the Help link at the top right of any dashboard page.
- Ask Linda how to do something in the dashboard. Linda reads the same help before answering.

## Good to know

Every staff member can read help, whatever their role. The screens it links to still decide who may open them.
```

In `test_help_files.py`, delete `'release_notes',` from `_AWAITING_A_GUIDE`.

- [ ] **Step 7: Run the tests, compile the templates**

Run: `T plugins.installed.release_notes`
Expected: `OK`, covering all release_notes tests including the 13 new page tests.

Run:
```bash
DATABASE_URL='sqlite:///:memory:' .venv/bin/python -c "
import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'morph.settings'); django.setup()
from django.template.loader import get_template
for t in ('release_notes/help_index.html', 'release_notes/help_app.html', 'release_notes/_help_app_list.html', 'release_notes/_help_styles.html'):
    get_template(t); print('ok', t)"
```
Expected: four `ok` lines.

- [ ] **Step 8: Lint and commit**

```bash
.venv/bin/ruff check plugins/installed/release_notes/
.venv/bin/ruff format plugins/installed/release_notes/
git add plugins/installed/release_notes/
git commit -m "feat(help): /dashboard/help/ lists every app, and each app has a page

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Search the help

**Files:**
- Create: `plugins/installed/release_notes/help_search.py`
- Modify: `plugins/installed/release_notes/help_views.py` (`help_index` reads `q`)
- Modify: `plugins/installed/release_notes/templates/release_notes/help_index.html` (search form and results)
- Test: `plugins/installed/release_notes/tests/test_help_search.py`

**Interfaces:**
- Consumes: `app_help.guide`, `help_render.readable`.
- Produces:
  - `help_search.fold(text) -> str`;
  - `help_search.search(query, *, limit=30) -> list[dict name/label/summary/snippet/active]`;
  - `help_search.forget() -> None`.

- [ ] **Step 1: Write the failing tests**

`plugins/installed/release_notes/tests/test_help_search.py`:

```python
"""Search across every installed app's help (the Help index's search box)."""

from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.installed.release_notes import help_search


class SearchTests(TestCase):
    def setUp(self):
        help_search.forget()
        self.addCleanup(help_search.forget)

    def _names(self, query: str) -> list[str]:
        return [hit['name'] for hit in help_search.search(query)]

    def test_a_word_in_a_guide_finds_its_app(self):
        hit = next(h for h in help_search.search('licence') if h['name'] == 'release_notes')
        self.assertIn('licence', hit['snippet'])

    def test_case_and_accents_fold(self):
        self.assertIn('release_notes', self._names('LICENCE'))
        self.assertIn('release_notes', self._names('licénce'))

    def test_every_word_must_match(self):
        self.assertNotIn('release_notes', self._names('licence qqqzzz'))

    def test_a_label_outranks_the_body(self):
        rows = [
            {'name': 'b', 'label': 'Beta', 'summary': '', 'headings': '', 'body': 'about refunds'},
            {'name': 'a', 'label': 'Refunds', 'summary': '', 'headings': '', 'body': ''},
        ]
        with mock.patch.object(help_search, '_index', return_value=rows):
            self.assertEqual(self._names('refunds'), ['a', 'b'])

    def test_punctuation_is_just_text(self):
        for query in ('(', '*', '?', '[', ')', '\\'):
            with self.subTest(query=query):
                self.assertIsInstance(help_search.search(query), list)

    def test_an_empty_query_finds_nothing(self):
        self.assertEqual(help_search.search('   '), [])


class SearchPageTests(TestCase):
    def setUp(self):
        help_search.forget()
        self.addCleanup(help_search.forget)
        staff = get_user_model().objects.create_user(
            username='help-search', email='hs@example.test', password='pw', is_staff=True
        )
        self.client.force_login(staff)

    def test_results_lead_the_page(self):
        html = self.client.get('/dashboard/help/?q=licence').content.decode()
        results = html[html.index('data-help-results') :]
        self.assertIn('href="/dashboard/help/release_notes/"', results[: results.index('</section>')])

    def test_no_hits_says_so_and_keeps_the_index(self):
        html = self.client.get('/dashboard/help/?q=qqqzzz').content.decode()
        self.assertIn('No help mentions “qqqzzz”.', html)
        self.assertIn('data-help-area=', html)
```

- [ ] **Step 2: Run them and watch them fail**

Run: `T plugins.installed.release_notes.tests.test_help_search`
Expected: ERROR, `ImportError: cannot import name 'help_search'`.

- [ ] **Step 3: Write the search**

`plugins/installed/release_notes/help_search.py`:

```python
"""Search across every installed app's help (the Help index's search box).

A small in-memory index of each app's label, summary, headings and guide words,
built once per process and version (guides change only with a deploy; under
DEBUG it is rebuilt every time). Case and accents fold, every word must match
somewhere, and a hit in the label ranks above the summary, a heading, then the
guide's text. Plain substring matching: a query is never a pattern.
"""

from __future__ import annotations

import unicodedata

from django.conf import settings

from plugins import app_help
from plugins.installed.release_notes import help_render

_WEIGHTS = (('label', 8), ('summary', 4), ('headings', 2), ('body', 1))
SNIPPET = 160
_cache: dict[str, list[dict]] = {}


def fold(text: str) -> str:
    decomposed = unicodedata.normalize('NFKD', text or '')
    return ''.join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def forget() -> None:
    _cache.clear()


def _index() -> list[dict]:
    from plugins.registry import app_registry

    key = str(getattr(settings, 'MORPHEUS_VERSION', ''))
    if not settings.DEBUG and key in _cache:
        return _cache[key]
    rows = []
    for inst in app_registry.all_plugins():
        guide = app_help.guide(inst.name)
        rows.append(
            {
                'name': inst.name,
                'label': inst.label or inst.name,
                'summary': (guide.summary if guide else '') or inst.description,
                'headings': ' '.join(guide.headings) if guide else '',
                'body': help_render.readable(guide.body, app=inst.name) if guide else '',
            }
        )
    _cache.clear()
    _cache[key] = rows
    return rows


def _snippet(body: str, terms: list[str]) -> str:
    folded = fold(body)
    found = [i for i in (folded.find(t) for t in terms) if i >= 0]
    if not found:
        return ''
    start = max(0, min(found) - SNIPPET // 3)
    piece = ' '.join(body[start : start + SNIPPET].split())
    return ('…' if start else '') + piece + ('…' if start + SNIPPET < len(body) else '')


def search(query: str, *, limit: int = 30) -> list[dict]:
    """Apps whose help mentions every word of ``query``, best first."""
    from plugins.registry import app_registry

    terms = fold(query).split()
    if not terms:
        return []
    hits = []
    for row in _index():
        fields = {name: fold(row[name]) for name, _weight in _WEIGHTS}
        score = 0
        for term in terms:
            best = max((w for name, w in _WEIGHTS if term in fields[name]), default=0)
            if not best:
                break
            score += best
        else:
            hits.append((score, row))
    hits.sort(key=lambda h: (-h[0], h[1]['label'].casefold()))
    return [
        {
            'name': row['name'],
            'label': row['label'],
            'summary': row['summary'],
            'snippet': _snippet(row['body'], terms),
            'active': app_registry.is_active(row['name']),
        }
        for _score, row in hits[:limit]
    ]
```

- [ ] **Step 4: Wire it into the index**

In `help_views.py`, add `help_search` to the `from plugins.installed.release_notes import …` line. Then replace `help_index` with:

```python
@staff_member_required
def help_index(request):
    rows = _entries()
    query = (request.GET.get('q') or '').strip()[:100]
    return render(
        request,
        'release_notes/help_index.html',
        {
            'q': query,
            'results': help_search.search(query) if query else [],
            'groups': _groups([r for r in rows if r['active']]),
            'off': sorted((r for r in rows if not r['active']), key=lambda r: r['label'].casefold()),
            'active_nav': 'settings',
        },
    )
```

In `help_index.html`, insert this right after the closing `</div>` of the heading block (the block holding `<h1 …>Help</h1>`):

```django
  <form method="get" class="help__search" role="search">
    <input type="search" name="q" value="{{ q }}" class="input" placeholder="Search the help" aria-label="Search the help">
    <button class="btn btn-secondary" type="submit"><i data-lucide="search" class="h-4 w-4"></i> Search</button>
  </form>
  {% if q %}
  <section class="card card-padded" data-help-results>
    {% if results %}
    <h2 class="help__area">Help that mentions “{{ q }}”</h2>
    <ul class="help__results">
      {% for hit in results %}
      <li><a href="{% url 'help:app' hit.name %}" class="help__app">{{ hit.label }}</a>{% if not hit.active %} <span class="pill pill-neutral pill-xs">Off</span>{% endif %}{% if hit.summary %}<div class="help__summary">{{ hit.summary }}</div>{% endif %}{% if hit.snippet %}<div class="help__snippet">{{ hit.snippet }}</div>{% endif %}</li>
      {% endfor %}
    </ul>
    {% else %}
    <p class="text-sm">No help mentions “{{ q }}”. Try another word, or browse the apps below.</p>
    {% endif %}
  </section>
  {% endif %}
```

- [ ] **Step 5: Run the tests**

Run: `T plugins.installed.release_notes`
Expected: `OK`.

- [ ] **Step 6: Lint, compile, commit**

```bash
.venv/bin/ruff check plugins/installed/release_notes/
.venv/bin/ruff format plugins/installed/release_notes/
DATABASE_URL='sqlite:///:memory:' .venv/bin/python -c "
import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'morph.settings'); django.setup()
from django.template.loader import get_template; get_template('release_notes/help_index.html'); print('ok')"
git add plugins/installed/release_notes/
git commit -m "feat(help): search every app's help from the Help index

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Help links on every dashboard page, the user menu and the Apps catalogue

**Files:**
- Modify: `core/hooks.py`: the `DASHBOARD_PAGE_HELP` constant, and `badge` on `DASHBOARD_USER_MENU`.
- Modify: `plugins/installed/admin_dashboard/navigation.py`: `CoreTab.app`, `Tab.app`, `tabs()`, `current_app()`.
- Modify: `plugins/installed/admin_dashboard/templatetags/morph_dashboard.py`: the `dashboard_page_help` tag.
- Modify: `plugins/installed/admin_dashboard/templates/admin_dashboard/base.html`.
- Modify: `plugins/installed/admin_dashboard/views_split/apps.py` and `templates/admin_dashboard/apps.html`.
- Modify: `plugins/installed/admin_dashboard/tests/test_disable_guards.py`.
- Modify: `plugins/installed/release_notes/app.py`: `on_user_menu`, `on_page_help`.
- Test: `plugins/installed/release_notes/tests/test_help_links.py`

**Interfaces:**
- Consumes: `app_help.summary`, `app_help.tree_apps`.
- Produces:
  - the filter `MorpheusEvents.DASHBOARD_PAGE_HELP` (`value=None`, kwargs `app`, `request`; the answer is `{'url', 'label', 'title'}`);
  - `navigation.current_app(request) -> str`;
  - the template tag `{% dashboard_page_help as page_help %}`;
  - the markup `<p class="page-help"><a href="…" title="…">`.

- [ ] **Step 1: Write the failing tests**

`plugins/installed/release_notes/tests/test_help_links.py`:

```python
"""Help is linked from the screens: every dashboard page, the user menu, the Apps
catalogue. The shell asks (DASHBOARD_PAGE_HELP, DASHBOARD_USER_MENU) and the help
app answers, so base.html links no app page itself."""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils.html import escape

from plugins import app_help
from plugins.installed.admin_dashboard import navigation

_LINK = re.compile(r'<p class="page-help"><a href="([^"]+)"')


class PageHelpLinkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.boss = get_user_model().objects.create_user(
            username='help-links',
            email='hl@example.test',
            password='pw',
            is_staff=True,
            is_superuser=True,
        )

    def setUp(self):
        self.client.force_login(self.boss)

    def _help_link(self, url: str) -> str | None:
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, url)
        m = _LINK.search(resp.content.decode())
        return m.group(1) if m else None

    def test_an_apps_own_page_links_its_help(self):
        self.assertEqual(self._help_link('/dashboard/reviews/'), '/dashboard/help/reviews/')

    def test_a_settings_tool_links_its_apps_help(self):
        self.assertEqual(
            self._help_link('/dashboard/apps/feedback/tickets/'), '/dashboard/help/feedback/'
        )

    def test_an_apps_settings_form_links_its_help(self):
        self.assertEqual(
            self._help_link('/dashboard/settings/newsletter/'), '/dashboard/help/newsletter/'
        )

    def test_a_shell_tab_links_the_app_it_belongs_to(self):
        self.assertEqual(self._help_link('/dashboard/orders/'), '/dashboard/help/orders/')
        self.assertEqual(self._help_link('/dashboard/products/'), '/dashboard/help/catalog/')

    def test_a_page_of_no_app_links_the_help_index(self):
        self.assertEqual(self._help_link('/dashboard/'), '/dashboard/help/')

    def test_the_help_pages_carry_no_help_link(self):
        self.assertIsNone(self._help_link('/dashboard/help/'))
        self.assertIsNone(self._help_link('/dashboard/help/reviews/'))

    def test_every_shell_tab_names_an_app_with_a_folder(self):
        apps = set(app_help.tree_apps())
        for tab in navigation.CORE_TABS:
            with self.subTest(tab=tab.label):
                self.assertIn(tab.app, apps)


class MenuAndCatalogueTests(TestCase):
    def setUp(self):
        boss = get_user_model().objects.create_user(
            username='help-menu',
            email='hm@example.test',
            password='pw',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(boss)

    def test_the_user_menu_comes_from_the_help_app(self):
        html = self.client.get('/dashboard/').content.decode()
        self.assertIn('href="/dashboard/help/"', html)
        self.assertIn('href="/dashboard/apps/release_notes/about/"', html)
        # The version pill rides on the contributed entry (the top bar shows the
        # version too, so look for it inside the Version link itself).
        self.assertRegex(
            html,
            r'href="/dashboard/apps/release_notes/version/"[^>]*>.*?Version &amp; updates '
            r'<span class="pill pill-info"[^>]*>' + re.escape(settings.MORPHEUS_VERSION),
        )

    def test_the_shell_names_no_app_page(self):
        base = (
            Path(settings.BASE_DIR)
            / 'plugins/installed/admin_dashboard/templates/admin_dashboard/base.html'
        )
        self.assertNotIn('release_notes', base.read_text(encoding='utf-8'))

    def test_the_catalogue_shows_each_apps_summary_and_help(self):
        html = self.client.get('/dashboard/apps/').content.decode()
        start = html.index('data-app="release_notes"')
        end = html.find('data-app=', start + 10)
        card = html[start : end if end != -1 else None]
        self.assertIn(escape(app_help.summary('release_notes')), card)
        self.assertIn('href="/dashboard/help/release_notes/"', card)
```

- [ ] **Step 2: Run them and watch them fail**

Run: `T plugins.installed.release_notes.tests.test_help_links`
Expected: FAIL/ERROR. `_help_link` returns None everywhere, `CoreTab` has no attribute `app`, and `base.html` still names `release_notes`.

- [ ] **Step 3: Declare the filter**

In `core/hooks.py`, extend the `DASHBOARD_USER_MENU` comment's first line from `value=list[dict] ({label, url, icon,` to `value=list[dict] ({label, url, icon, badge,`. Add this sentence before "Fired by admin_dashboard's context": `` `badge` is a short pill after the label (release_notes shows the running version). ``

Then add, right after the `DASHBOARD_BODY_END = 'dashboard.body_end'  # filter` line:

```python
    # DASHBOARD_PAGE_HELP — filter, value=None, kwargs: app (the name of the app
    #   the page belongs to, '' for a page of the shell's own), request. The Help
    #   link a dashboard page carries at its top right, and each Apps catalogue
    #   card: answer {'url', 'label', 'title'}; no answer means no link, so the
    #   links leave with the help app. Fired by admin_dashboard's
    #   `dashboard_page_help` tag and the catalogue; release_notes answers.
    DASHBOARD_PAGE_HELP = 'dashboard.page_help'  # filter
```

- [ ] **Step 4: Say which app each shell page belongs to**

In `plugins/installed/admin_dashboard/navigation.py`:

1. In `class CoreTab`, after `group: str = ''  # folds into …`, add:

   ```python
       app: str = ''  # the app this page belongs to, for its Help link
   ```

2. In `class Tab`, after `hint: str = ''`, add:

   ```python
       app: str = ''  # a shell tab's app (CoreTab.app); contributed pages use `plugin`
   ```

3. Replace `CORE_TABS` with:

   ```python
   CORE_TABS: tuple[CoreTab, ...] = (
       CoreTab('ai', 'Chat', '/dashboard/assistant/', 10, 'message-circle', app='agent_core'),
       CoreTab('ai', 'Chats', '/dashboard/assistant/chats/', 15, 'message-square', app='agent_core'),
       CoreTab(
           'ai', 'Insights', '/dashboard/ai-insights/', 60, 'lightbulb', badge='insights', app='ai_assistant'
       ),
       CoreTab(
           'ai',
           'Proposals',
           '/dashboard/assistant/proposals/',
           90,
           'git-pull-request',
           superuser=True,
           group=OVERSIGHT,
           app='agent_core',
       ),
       CoreTab('orders', 'All orders', '/dashboard/orders/', 10, 'shopping-bag', app='orders'),
       CoreTab('orders', 'Returns', '/dashboard/returns/', 30, 'undo-2', badge='returns', app='orders'),
       CoreTab('products', 'All products', '/dashboard/products/', 10, 'package', app='catalog'),
       CoreTab('products', 'Categories', '/dashboard/categories/', 20, 'folder-tree', app='catalog'),
       CoreTab('products', 'Collections', '/dashboard/collections/', 30, 'layers', app='catalog'),
       CoreTab('products', 'Tags', '/dashboard/tags/descriptions/', 40, 'tags', app='catalog'),
       CoreTab(
           'products',
           'Content audit',
           '/dashboard/products/content-audit/',
           95,
           'clipboard-check',
           nav='hidden',
           app='catalog',
       ),
       CoreTab('customers', 'All customers', '/dashboard/customers/', 10, 'users', app='customers'),
       CoreTab('marketing', 'Overview', '/dashboard/marketing/', 5, 'layout-grid', app='marketing'),
       CoreTab('analytics', 'Overview', '/dashboard/analytics/', 10, 'bar-chart-3', app='analytics'),
   )
   ```

4. In `tabs()`, change the shell-tab line to:

   ```python
           Tab(t.section, t.label, t.url, t.order, t.icon, t.nav, badge=t.badge, group=t.group, app=t.app)
   ```

5. Add after `build()`:

   ```python
   def current_app(request) -> str:
       """The app the current dashboard page belongs to, for its Help link: the
       owner of the tab or settings tool the path resolves to, the app a shell tab
       names, or the app whose settings form this is. '' for the shell's own pages
       (the home, the settings hub)."""
       from plugins.registry import app_registry  # noqa: PLC0415

       loc = build(request)['location']
       if loc.tab is not None:
           return loc.tab.plugin or loc.tab.app
       if loc.tool is not None:
           return loc.tool.plugin
       head = _settings_head(getattr(request, 'path', '') or '')
       return head if head and app_registry.settings_panel(head) is not None else ''
   ```

- [ ] **Step 5: The shell asks; the help app answers**

In `plugins/installed/admin_dashboard/templatetags/morph_dashboard.py`, add after `get_ai_page_help`:

```python
@register.simple_tag(takes_context=True)
def dashboard_page_help(context):
    """The current page's Help link, ``{'url', 'label', 'title'}``, or None.

    The shell asks through DASHBOARD_PAGE_HELP and the help app answers, so the
    shell links no app page itself and every link leaves with the help app.
    """
    request = context.get('request')
    if request is None:
        return None
    try:
        from morpheus.core import MorpheusEvents, hook_registry
        from plugins.installed.admin_dashboard import navigation

        link = hook_registry.filter(
            MorpheusEvents.DASHBOARD_PAGE_HELP,
            value=None,
            app=navigation.current_app(request),
            request=request,
        )
    except Exception:  # noqa: BLE001 — a Help link never breaks a page
        import logging

        logging.getLogger('morpheus.admin').warning('dashboard_page_help failed', exc_info=True)
        return None
    return link if isinstance(link, dict) and link.get('url') else None
```

In `base.html`:

1. Delete these three lines, which hold the hardcoded Help, About and Version links:
   ```
           {% plugin_enabled "release_notes" as release_notes_on %}{% if release_notes_on %}<a href="/dashboard/apps/release_notes/help/" …
           {% if release_notes_on %}<a href="/dashboard/apps/release_notes/about/" …
           {% if release_notes_on %}<a href="/dashboard/apps/release_notes/version/" …
   ```

2. In the contributed-entries loop, replace the `<a>` line with:
   ```django
           <a href="{{ item.url }}" class="nav-link" style="font-size:.85rem;"{% for k, v in item.attrs.items %} {{ k }}="{{ v }}"{% endfor %}><i data-lucide="{{ item.icon|default:'circle' }}" class="h-4 w-4"></i> {{ item.label }}{% if item.badge %} <span class="pill pill-info" style="font-size:.62rem; margin-left:auto;">{{ item.badge }}</span>{% endif %}</a>
   ```

3. Directly above the line `    {% comment %}The current section's pages as tabs (admin_dashboard/navigation.py).`, insert:
   ```django
       {% comment %}The page's Help link (DASHBOARD_PAGE_HELP): the help app answers with the help of the app this page belongs to; with it off there is no link.{% endcomment %}
       {% dashboard_page_help as page_help %}{% if page_help %}<p class="page-help"><a href="{{ page_help.url }}" title="{{ page_help.title }}"><i data-lucide="help-circle" class="h-4 w-4"></i> {{ page_help.label }}</a></p>{% endif %}
   ```

4. Directly above the line beginning `    .context-help { position: relative;`, insert:
   ```css
       .page-help { display: flex; justify-content: flex-end; margin: 0 0 .35rem; font-size: .8rem; }
       .page-help a { display: inline-flex; align-items: center; gap: .3rem; color: var(--text-muted); }
       .page-help a:hover { color: var(--text); }
   ```

In `plugins/installed/release_notes/app.py`, add `from morpheus.core import MorpheusEvents` to the imports. Register the two hooks at the end of `ready()`:

```python
        self.register_hook(MorpheusEvents.DASHBOARD_USER_MENU, self.on_user_menu)
        self.register_hook(MorpheusEvents.DASHBOARD_PAGE_HELP, self.on_page_help)
```

Add the two methods to the class:

```python
    def on_user_menu(self, value, **kwargs):
        """Help, About and Version in the account menu, in place of links the
        shell used to hardcode."""
        from django.conf import settings

        value.extend(
            [
                {'label': 'Help', 'url': '/dashboard/help/', 'icon': 'help-circle', 'order': 10},
                {
                    'label': 'About Morpheus OS',
                    'url': '/dashboard/apps/release_notes/about/',
                    'icon': 'info',
                    'order': 20,
                },
                {
                    'label': 'Version & updates',
                    'url': '/dashboard/apps/release_notes/version/',
                    'icon': 'git-commit-horizontal',
                    'order': 30,
                    'badge': getattr(settings, 'MORPHEUS_VERSION', ''),
                },
            ]
        )
        return value

    def on_page_help(self, value, app='', request=None, **kwargs):
        """The Help link for a page of ``app``: that app's help, else the index."""
        from plugins.registry import app_registry

        if (getattr(request, 'path', '') or '').startswith('/dashboard/help/'):
            return value  # a help page needs no link to help
        inst = app_registry.get(app) if app else None
        if inst is None:
            return {'url': '/dashboard/help/', 'label': 'Help', 'title': 'Help for every app'}
        return {
            'url': f'/dashboard/help/{inst.name}/',
            'label': 'Help',
            'title': f'Help for {inst.label or inst.name}',
        }
```

- [ ] **Step 6: The catalogue shows the summary and a Help link**

In `plugins/installed/admin_dashboard/views_split/apps.py`, in `apps_view`, after `from plugins.installed.admin_dashboard import navigation`, add:

```python
    from morpheus.core import MorpheusEvents, hook_registry
    from plugins import app_help

    def help_link(name):
        try:
            link = hook_registry.filter(
                MorpheusEvents.DASHBOARD_PAGE_HELP, value=None, app=name, request=request
            )
        except Exception:  # noqa: BLE001 — a Help link never breaks the catalogue
            return None
        return link if isinstance(link, dict) and link.get('url') else None
```

In the `plugins.append({...})` dict, add after `'description': getattr(cls, 'description', ''),`:

```python
                # The app's one sentence for staff (its help.md), else the
                # developer description; and its Help link.
                'summary': app_help.summary(name) or getattr(cls, 'description', ''),
                'help': help_link(name),
```

In `templates/admin_dashboard/apps.html`, make three changes:

1. Change `data-apps-text="… {{ p.description|lower }}"` to `data-apps-text="{{ p.label|default:p.name|lower }} {{ p.name }} {{ p.summary|lower }} {{ p.description|lower }}"`.
2. Replace `{% if p.description %}<p class="text-sm text-[color:var(--text-muted)] line-clamp-3">{{ p.description }}</p>{% endif %}` with `{% if p.summary %}<p class="text-sm text-[color:var(--text-muted)] line-clamp-3">{{ p.summary }}</p>{% endif %}`.
3. Right before `{% if p.has_settings %}` in the card's footer row, insert:
   ```django
             {% if p.help %}<a href="{{ p.help.url }}" class="btn btn-ghost text-xs" title="{{ p.help.title }}"><i data-lucide="help-circle" class="h-3.5 w-3.5"></i> Help</a>{% endif %}
   ```

In `plugins/installed/admin_dashboard/tests/test_disable_guards.py`, in `DashboardNavGuardTests`:

1. Replace `GUARDED_LINKS = {…}` and its comment with:
   ```python
       # None left: the account menu's Help, About and Version moved to
       # DASHBOARD_USER_MENU (release_notes, v0.115). Add a row only if an app
       # link ever has to be hardcoded again.
       GUARDED_LINKS: dict[str, str] = {}
   ```
2. In `test_contributed_nav_is_not_hardcoded`, add `'/dashboard/apps/release_notes/',` to the fragment list, after `'/dashboard/agents/',`.

- [ ] **Step 7: Run the tests**

Run: `T plugins.installed.release_notes plugins.installed.admin_dashboard`
Expected: `OK`.

- [ ] **Step 8: Lint, compile, commit**

```bash
.venv/bin/ruff check core/hooks.py plugins/installed/admin_dashboard/navigation.py plugins/installed/admin_dashboard/templatetags/morph_dashboard.py plugins/installed/admin_dashboard/views_split/apps.py plugins/installed/admin_dashboard/tests/test_disable_guards.py plugins/installed/release_notes/
.venv/bin/ruff format core/hooks.py plugins/installed/admin_dashboard/navigation.py plugins/installed/admin_dashboard/templatetags/morph_dashboard.py plugins/installed/admin_dashboard/views_split/apps.py plugins/installed/admin_dashboard/tests/test_disable_guards.py plugins/installed/release_notes/
DATABASE_URL='sqlite:///:memory:' .venv/bin/python -c "
import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'morph.settings'); django.setup()
from django.template.loader import get_template
for t in ('admin_dashboard/base.html', 'admin_dashboard/apps.html'): get_template(t); print('ok', t)"
git add core/hooks.py plugins/installed/admin_dashboard/ plugins/installed/release_notes/
git commit -m "feat(help): every dashboard page links its app's help; the shell links no app page

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Linda reads the help

**Files:**
- Create: `plugins/installed/release_notes/help_tools.py`
- Modify: `plugins/installed/release_notes/app.py`: `contribute_agent_tools`, and the `AGENT_SYSTEM_PROMPT` hook.
- Modify: `core/agents/base.py`: a storefront agent gets no scope-less platform tool.
- Test: `plugins/installed/release_notes/tests/test_help_tools.py`

**Interfaces:**
- Consumes:
  - `help_facts.facts`;
  - `help_render.plain`;
  - `app_help.guide`, `app_help.summary`;
  - `navigation.describe_app`.
- Produces:
  - tools `help.apps` (no args) and `help.read(app: str)`, both `scopes=[]`;
  - `ReleaseNotesPlugin.HELP_LINE: str`, which is appended to Linda's prompt.

- [ ] **Step 1: Write the failing tests**

`plugins/installed/release_notes/tests/test_help_tools.py`:

```python
"""Linda reads the same help: help.apps and help.read, for every staff role in
every mode, never for a shopper's agent."""

from __future__ import annotations

import re
import types

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.agents.base import MorpheusAgent
from core.assistant.modes import MODES
from core.assistant.prompts import build_system_prompt
from plugins.installed.agent_mcp.linda_turn import LindaTurn, catalogue
from plugins.installed.release_notes.help_tools import help_apps_tool, help_read_tool
from plugins.registry import app_registry

CONV = 'user:help-tools-test'


def _names(user, mode: str) -> set[str]:
    return {t.name for t in catalogue(LindaTurn(user=user, conversation_key=CONV, mode_slug=mode))}


class HelpToolTests(TestCase):
    def test_help_apps_lists_every_installed_app(self):
        apps = {a['name']: a for a in help_apps_tool.handler().output['apps']}
        self.assertEqual(set(apps), {p.name for p in app_registry.all_plugins()})
        self.assertTrue(apps['reviews']['on'])
        self.assertEqual(apps['reviews']['area'], 'Products')

    def test_help_read_turns_markers_into_names_and_paths(self):
        text = help_read_tool.handler(app='release_notes').output['text']
        self.assertIn('Version & updates (/dashboard/apps/release_notes/version/)', text)
        self.assertNotRegex(text, r'\((page|settings|field|section|app):')

    def test_help_read_says_where_things_are_and_what_linda_can_do(self):
        text = help_read_tool.handler(app='reviews').output['text']
        self.assertIn('- Products › Reviews (/dashboard/reviews/)', text)
        self.assertIn('reviews.approve (asks first)', text)

    def test_an_unknown_app_gets_the_closest_names(self):
        out = help_read_tool.handler(app='reviewz').output
        self.assertIn('error', out)
        self.assertIn('reviews', out['closest'])

    def test_every_staff_member_has_help_in_every_mode(self):
        plugin = app_registry.get('rbac')
        plugin.set_config('enforcement_mode', 'enforce')
        plugin.invalidate_config_cache()
        self.addCleanup(plugin.invalidate_config_cache)
        nobody = get_user_model().objects.create_user(
            username='help-norole', email='nr@example.test', password='pw', is_staff=True
        )
        for mode in MODES:
            with self.subTest(mode=mode.slug):
                names = _names(nobody, mode.slug)
                self.assertIn('help.apps', names)
                self.assertIn('help.read', names)

    def test_lindas_instructions_name_only_help_tools_she_has(self):
        prompt = build_system_prompt()
        self.assertIn('`help.read`', prompt)
        staff = types.SimpleNamespace(is_staff=True, is_superuser=False, pk=1)
        names = _names(staff, 'general')
        for name in re.findall(r'`(help\.[a-z_]+)`', prompt):
            self.assertIn(name, names)


class StorefrontAgentTests(TestCase):
    def test_a_storefront_agent_never_gets_a_scope_less_tool(self):
        class Shop(MorpheusAgent):
            name = 'help_test_shop'
            label = 'Shop'
            audience = 'storefront'
            scopes = ['catalog.read']

        names = {t.name for t in Shop().get_tools()}
        self.assertNotIn('help.apps', names)
        self.assertNotIn('help.read', names)

    def test_a_staff_agent_gets_the_help_tools(self):
        class Staff(MorpheusAgent):
            name = 'help_test_staff'
            label = 'Staff'
            audience = 'merchant'
            scopes = ['catalog.read']

        self.assertIn('help.read', {t.name for t in Staff().get_tools()})
```

- [ ] **Step 2: Run them and watch them fail**

Run: `T plugins.installed.release_notes.tests.test_help_tools`
Expected: ERROR, `ModuleNotFoundError: No module named 'plugins.installed.release_notes.help_tools'`.

- [ ] **Step 3: Write the tools**

`plugins/installed/release_notes/help_tools.py`:

```python
"""Linda's help tools: the same help staff read on /dashboard/help/.

Read-only and scope-less, like platform.capabilities: every staff member's Linda
reads help in every mode, whatever their role. A storefront agent never gets a
scope-less tool (core/agents/base.py), and the storefront, cart and checkout
agent doors list their tools explicitly, so a shopper's agent never sees these.
They leave with this app.
"""

from __future__ import annotations

import difflib

from core.agents.tools import ToolResult
from morpheus.core import tool
from plugins import app_help
from plugins.installed.release_notes import help_facts, help_render


@tool(
    name='help.apps',
    description=(
        'List every app this store has, with one sentence on what each does, the '
        'dashboard area it lives in and whether it is switched on. Use it to find '
        "the app a merchant's question is about, then read its help with help.read."
    ),
    scopes=[],
)
def help_apps_tool() -> ToolResult:
    from plugins.installed.admin_dashboard import navigation
    from plugins.registry import app_registry

    apps = [
        {
            'name': inst.name,
            'label': inst.label or inst.name,
            'summary': app_help.summary(inst.name) or inst.description,
            'area': navigation.describe_app(inst)['area_label'],
            'on': app_registry.is_active(inst.name),
        }
        for inst in sorted(app_registry.all_plugins(), key=lambda p: p.name)
    ]
    return ToolResult(output={'apps': apps, 'count': len(apps)}, display=f'{len(apps)} apps.')


def _closest(name: str) -> list[str]:
    from plugins.registry import app_registry

    choices: dict[str, str] = {}
    for inst in app_registry.all_plugins():
        choices[inst.name] = inst.name
        choices[(inst.label or '').casefold()] = inst.name
    hits = difflib.get_close_matches(name.casefold(), list(choices), n=5, cutoff=0.5)
    return sorted({choices[h] for h in hits})


@tool(
    name='help.read',
    description=(
        "Read one app's help: what it is for, how to set it up, common tasks, where "
        'its screens and settings are (with their paths) and what you can do there. '
        'Read it before answering how to do something in the dashboard.'
    ),
    scopes=[],
    schema={
        'type': 'object',
        'properties': {
            'app': {'type': 'string', 'description': 'The app name from help.apps, e.g. "reviews".'}
        },
        'required': ['app'],
    },
)
def help_read_tool(*, app: str) -> ToolResult:
    name = (app or '').strip()
    found = help_facts.facts(name)
    if found is None:
        return ToolResult(
            output={'error': f'no app named {name!r}', 'closest': _closest(name)},
            display=f'No app named {name!r}.',
        )
    guide = app_help.guide(name)
    parts = [f"# {found['label']} ({'on' if found['active'] else 'off'})"]
    summary = guide.summary if guide else found['description']
    if summary:
        parts.append(summary)
    if guide:
        parts.append(help_render.plain(guide.body, app=name))
    where = [f'- {p.label} ({p.url})' if p.url else f'- {p.label}' for p in found['places']]
    where += [f'- {c}' for c in found['cards']]
    where += [f'- In the shop: {s}' for s in found['shop']]
    if where:
        parts.append('Where to find it:\n' + '\n'.join(where))
    if found['tools']:
        parts.append(
            'What you can do here:\n'
            + '\n'.join(
                f"- {t['name']}{' (asks first)' if t['asks_first'] else ''}: {t['description']}"
                for t in found['tools']
            )
        )
    return ToolResult(
        output={
            'app': name,
            'label': found['label'],
            'on': found['active'],
            'text': '\n\n'.join(parts),
        },
        display=f"Help for {found['label']}.",
    )
```

- [ ] **Step 4: Contribute the tools and the prompt line**

In `plugins/installed/release_notes/app.py`, add above the class:

```python
#: Appended to Linda's instructions while this app is on (AGENT_SYSTEM_PROMPT):
#: a line in core's base prompt would name tools that vanish when it is off.
HELP_LINE = (
    '\nHELP\n'
    '  • When the merchant asks how to do something in the dashboard, or what an app '
    "does, read the store's own help first: `help.apps` finds the app, `help.read` "
    'gives its guide and where its screens are.\n'
)
```

Register the prompt hook at the end of `ready()`:

```python
        self.register_hook(MorpheusEvents.AGENT_SYSTEM_PROMPT, self.on_system_prompt, priority=60)
```

Add to the class:

```python
    def contribute_agent_tools(self) -> list:
        from plugins.installed.release_notes.help_tools import help_apps_tool, help_read_tool

        return [help_apps_tool, help_read_tool]

    def on_system_prompt(self, value, **kwargs):
        """Tell Linda the store's help exists (AGENT_SYSTEM_PROMPT)."""
        return value + HELP_LINE if isinstance(value, str) else value
```

In `core/agents/base.py`, in `get_tools()`, inside the `for tool in agent_registry.platform_tools():` loop, right after the existing `if tool.scopes and not set(tool.scopes).issubset(set(self.scopes)):` block, add:

```python
            # A tool with no scopes is staff-wide (the help tools): never a
            # shopper's. A storefront agent gets only tools inside its own scopes.
            if not tool.scopes and self.audience == 'storefront':
                continue
```

- [ ] **Step 5: Run the tests and the agent guards**

Run: `T plugins.installed.release_notes plugins.installed.agent_mcp core.agents core.assistant`
Expected: `OK`. This includes `LindaCatalogueTests`, `test_scopes`, `test_registry_collisions` and the core boundary.

- [ ] **Step 6: Lint and commit**

```bash
.venv/bin/ruff check core/agents/base.py plugins/installed/release_notes/
.venv/bin/ruff format core/agents/base.py plugins/installed/release_notes/
git add core/agents/base.py plugins/installed/release_notes/
git commit -m "feat(help): Linda reads the help (help.apps, help.read) for every staff role

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Turning the help app off takes every surface with it

**Files:**
- Test: `plugins/installed/release_notes/tests/test_help_disable.py`

**Interfaces:**
- Consumes: everything in Tasks 5–8.

- [ ] **Step 1: Write the test**

`plugins/installed/release_notes/tests/test_help_disable.py`:

```python
"""With release_notes off, every help surface is gone (CLAUDE.md's second litmus
test): the Help area, every Help link, the menu entries, Linda's tools and her
help line."""

from __future__ import annotations

import types

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.assistant.prompts import build_system_prompt
from plugins.installed.agent_mcp.linda_turn import LindaTurn, catalogue
from plugins.registry import app_registry


class HelpDisableTests(TestCase):
    def setUp(self):
        boss = get_user_model().objects.create_user(
            username='help-off',
            email='ho@example.test',
            password='pw',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(boss)
        app_registry.deactivate('release_notes')
        self.addCleanup(app_registry.activate, 'release_notes')

    def test_the_help_area_is_gone(self):
        for url in ('/dashboard/help/', '/dashboard/help/reviews/', '/dashboard/apps/release_notes/help/'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_no_help_link_renders_anywhere(self):
        for url in ('/dashboard/', '/dashboard/reviews/', '/dashboard/orders/', '/dashboard/apps/'):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertNotIn('class="page-help"', html)
                self.assertNotIn('href="/dashboard/help/', html)

    def test_linda_loses_the_tools_and_the_line(self):
        staff = types.SimpleNamespace(is_staff=True, is_superuser=False, pk=1)
        names = {
            t.name
            for t in catalogue(LindaTurn(user=staff, conversation_key='user:help-off', mode_slug='general'))
        }
        self.assertNotIn('help.apps', names)
        self.assertNotIn('help.read', names)
        self.assertNotIn('help.read', build_system_prompt())
```

- [ ] **Step 2: Run it**

Run: `T plugins.installed.release_notes.tests.test_help_disable`
Expected: `OK` (3 tests).

If one fails, the surface it names is wired outside the bus. Fix that wiring; the test stays as it is.

- [ ] **Step 3: Run the whole suite once before the guides**

Run: `T > /tmp/help-suite.log 2>&1; grep -nE "^Ran |^OK|^FAILED|^(FAIL|ERROR):" /tmp/help-suite.log`
Expected: `OK (skipped=10)` or the current skip count, with no FAIL or ERROR lines.

Any failure is a regression from Tasks 1–8. Debug it with superpowers:systematic-debugging before going on.

- [ ] **Step 4: Commit**

```bash
.venv/bin/ruff check plugins/installed/release_notes/tests/test_help_disable.py
.venv/bin/ruff format plugins/installed/release_notes/tests/test_help_disable.py
git add plugins/installed/release_notes/tests/test_help_disable.py
git commit -m "test(help): turning the help app off removes every help surface

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Write the guides for the other 112 apps

**Files:**
- Create: `plugins/installed/<app>/help.md` for each app in the batches below.
- Modify: `plugins/installed/release_notes/tests/test_help_files.py`: remove each batch's names from `_AWAITING_A_GUIDE`.
- Create: `docs/plans/help-guide-findings-2026-10.md`, for the defects found while writing, as a list for the owner.

**Interfaces:**
- Consumes:
  - the format and marker rules enforced by `test_help_files.GuideFormatTests` and `test_help_markers.GuideMarkerTests`;
  - Appendix A, the guide brief.

**Batches** (by the Apps catalogue's areas; 112 apps):
- **B1 storefront (13):** advanced_ecommerce bookstore_3d brand_kit catalog consent discovery_quiz drops dynamics flipbook immersive_pdp journal lookbook lumina
- **B2 storefront (12):** media_3d motion product_gallery product_videos pwa rails save_for_later storefront trust_signals ugc_reviews webstories wishlist
- **B3 channels, SEO, analytics (15):** amazon_ads channels google_shopping meta_commerce microsoft_commerce openai_shopping pinterest_commerce reddit_ads snapchat_commerce tiktok_commerce tracking seo analytics feature_adoption post_purchase
- **B4 orders and payments (15):** aliexpress booking_marketplace cjdropshipping draft_orders dsers subscriptions zendrop advanced_payments agentic_checkout fraud_rules one_click orders payments post_checkout_upsell returns_portal
- **B5 marketing and customers (13):** cart_abandonment eco_impact gift_cards live_commerce marketing newsletter promotions customers loyalty_points referrals affiliates crm marketplace
- **B6 products, shipping, general, content (16):** b2b book_product inventory reviews bookvault shipping smart_shipping tax audiobooks digital_products gdpr localization markets cms media product_stories
- **B7 AI, team, data (14):** agent_core ai_assistant ai_content ai_stylist janus morpheus_brain store_bootstrap observability rbac staff_mfa staff_sso backups importers demo_data
- **B8 developer and platform (14):** admin_dashboard agent_mcp cloudflare feedback metafields webhooks_ui workflows environments experiments functions notifications_center personalisation rich_post_purchase richtext

- [ ] **Step 1: Dispatch the eight drafting agents in parallel**

In one message, launch eight `general-purpose` agents with the Agent tool, one per batch. Each prompt is Appendix A verbatim, followed by the line `Your apps: <the batch's names>`.

The agents write only `plugins/installed/<their apps>/help.md`. They edit no test file and no code.

- [ ] **Step 2: Land each batch as it returns**

For each batch:

1. Run: `T plugins.installed.release_notes.tests.test_help_files.GuideFormatTests plugins.installed.release_notes.tests.test_help_markers.GuideMarkerTests`
   Expected: `OK`. When it fails, fix the named guide and rerun.
2. **Review the guides against the code.** For every app in the batch:
   - open at least one of the agent's reported claims at its `file:line` and confirm the code does what the guide says;
   - for apps that move money or data, open all three: payments, orders, subscriptions, gift_cards, tax, shipping, consent, gdpr, returns_portal, backups, importers;
   - check that the guide says "Linda" and never "Janus", except when naming its settings page.

   A claim the code doesn't back is rewritten or removed.
3. Remove the batch's names from `_AWAITING_A_GUIDE`.
4. Run: `T plugins.installed.release_notes.tests.test_help_files plugins.installed.release_notes.tests.test_help_markers`
   Expected: `OK`.
5. Commit:
   ```bash
   git add plugins/installed/*/help.md plugins/installed/release_notes/tests/test_help_files.py
   git commit -m "docs(help): guides for <batch area>

   Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
   ```

- [ ] **Step 3: Record what the agents found**

Write `docs/plans/help-guide-findings-2026-10.md`. Its heading is `# Defects found while writing the help guides (2026-10)`. Under it goes one line per defect the agents reported, each with the app, what is wrong, the `file:line`, and "found while writing its guide; not fixed in this release". Write "None reported." when the list is empty. Then commit:

```bash
git add docs/plans/help-guide-findings-2026-10.md
git commit -m "docs(help): defects found while writing the guides, for the owner

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Every app has a guide; the rules are written down

**Files:**
- Modify: `plugins/installed/release_notes/tests/test_help_files.py`: delete `_AWAITING_A_GUIDE` and its two ratchet tests.
- Modify: `CLAUDE.md`: a convention entry.
- Modify: `docs/PLUGIN_DEVELOPMENT.md`: the anatomy tree, the required-files line, and a new §5.4.

- [ ] **Step 1: Make the guide rule strict**

In `test_help_files.py`:

1. Delete the `_AWAITING_A_GUIDE = frozenset({…})` block and its comment.
2. Delete `test_an_app_with_a_guide_is_not_still_awaiting_one` and `test_every_awaiting_app_exists`.
3. Replace `test_every_app_has_a_guide` with:

   ```python
       def test_every_app_has_a_guide(self):
           missing = [a for a in app_help.tree_apps() if app_help.guide(a) is None]
           self.assertEqual(missing, [], 'apps without plugins/installed/<app>/help.md')
   ```

Run: `T plugins.installed.release_notes.tests.test_help_files plugins.installed.release_notes.tests.test_help_markers`
Expected: `OK`.

- [ ] **Step 2: Write the convention into CLAUDE.md**

In `CLAUDE.md`, insert this paragraph right after the paragraph that begins `**Convention — the dashboard has one taxonomy, and an app files into it`:

```markdown
**Convention — every app ships its own help, and most of the help is generated (v0.115.0).**
`/dashboard/help/` (release_notes) shows, per app, the guide in `plugins/installed/<app>/help.md`
next to what the running code says: its pages, settings, shop surfaces, Linda's tools there, the
events it listens to and its URL mounts. A guide links the store's pages only through markers
(`[text](page:slug)`, `settings:`, `field:`, `section:`, `app:`), resolved live, so a renamed page
renames itself and a moved one never leaves a dead link. Its one-sentence summary is the app's
sentence everywhere, the Apps catalogue too; it says only what the code does today, in plain words,
and calls the assistant Linda. A new app ships its `help.md`; a change to what staff see or do in
an app updates its guide in the same commit; a deleted app takes its guide with it, and a merge
folds the absorbed app's guide into the target's. Linda reads the same help through `help.apps` and
`help.read`, which have no scopes, so every staff role has them in every mode; a storefront agent
never gets a scope-less tool (`core/agents/base.py`). The shell asks for Help links through
`DASHBOARD_PAGE_HELP` and for menu entries through `DASHBOARD_USER_MENU`, so `base.html` links no
app. Guarded by `release_notes/tests/test_help_*.py`: a missing guide, a marker that names nothing,
a heading outside the set and developer words all fail CI.
```

If `manage.py release --minor` prints a version other than v0.115.0 in Task 12, change the `(v0.115.0)` here before that commit.

- [ ] **Step 3: Write it into the plugin guide**

In `docs/PLUGIN_DEVELOPMENT.md`, under "## 2. Anatomy of a plugin":

1. Add `├── help.md                 # ★ the app's guide for store staff (§5.4)` after the `├── app.py …` line of the tree.
2. Replace `The **only required file** is \`app.py\`. Everything else is opt-in.` with `The **required files** are \`app.py\` and \`help.md\` (CI fails on an app without a guide). Everything else is opt-in.`

Then insert this section right before `### Enable / disable lifecycle`:

```markdown
### 5.4 Help for store staff (`help.md`)

Every app ships `plugins/installed/<app>/help.md`, the page staff read at
`/dashboard/help/<app>/` and Linda reads through `help.read`:

    ---
    summary: One plain sentence, at most 140 characters, about what the app does for the store.
    ---

    ## What it's for
    ## Set it up
    ## Common tasks
    ## Good to know

- Only those headings, in that order; "What it's for" is required; 60–400 words.
- Describe only what the code does today, in plain words. Call the assistant Linda.
- Never write a URL to the store's own pages. Use markers, resolved live:
  `[text](page:<slug>)` (one of your `DashboardPage` slugs; `page:<app>/<slug>` for
  another app's), `[text](settings:<app>)`, `[](field:<app>.<key>)` (a field of your
  settings panel, shown by its live label), `[](section:<key>)` (a sidebar section),
  `[text](app:<name>)` (another app's help). Empty link text shows the live label.
- Everything else on the page is generated from your manifest: where your pages and
  settings are, what you add to the shop, your agent tools, the events you listen to.

`release_notes/tests/test_help_files.py` and `test_help_markers.py` fail on a missing
guide, a marker that names nothing, a heading outside the set, or developer words.
```

- [ ] **Step 4: Run every help test, then commit**

Run: `T plugins.installed.release_notes plugins.installed.admin_dashboard`
Expected: `OK`.

```bash
.venv/bin/ruff check plugins/installed/release_notes/tests/test_help_files.py
.venv/bin/ruff format plugins/installed/release_notes/tests/test_help_files.py
git add plugins/installed/release_notes/tests/test_help_files.py CLAUDE.md docs/PLUGIN_DEVELOPMENT.md
git commit -m "docs(help): every app must ship help.md; the rules in CLAUDE.md and the plugin guide

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: Release, deploy and check live

**Files:**
- Modify (by `manage.py release`): `morph/settings.py` (`MORPHEUS_VERSION`) and `docs/RELEASE_NOTES.md`.

- [ ] **Step 1: Every CI gate, and the full suite**

Run:
```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check . \
&& DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py check \
&& DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py makemigrations --check --dry-run \
&& .venv/bin/python scripts/check_core_boundary.py && .venv/bin/python scripts/check_plugin_boundary.py \
&& .venv/bin/python scripts/check_plugin_standard.py && .venv/bin/python scripts/check_api_stability.py
T > /tmp/help-release.log 2>&1; grep -nE "^Ran |^OK|^FAILED|^(FAIL|ERROR):" /tmp/help-release.log
```

Expected:
- `All checks passed!`;
- `No changes detected`;
- `OK: 0 known core->plugin import(s)`;
- `OK: 113 known undeclared plugin->plugin pair(s)`;
- `OK: 38 known plugin-contract violation(s)`;
- an API stability exit of 0 (additions only);
- the suite ends `OK (skipped=10)` or the current skip count.

If `check_plugin_standard.py` reports a stale baseline entry, run `--save` and commit `scripts/plugin_standard_baseline.json`. This can happen if an app's first file of a kind counts as fixing a contract gap.

- [ ] **Step 2: Cut the release**

```bash
DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py release --minor "Help inside the dashboard for every app" \
  -m "Help (/dashboard/help/) explains every app: what it's for, how to set it up and common tasks, from a guide in the app's own folder, plus where its screens and settings are and what Linda can do there, read live from the running store." \
  -m "Search across all of it from the Help page; every dashboard page links the help of the app it belongs to, and the Apps catalogue shows each app's one-sentence summary." \
  -m "Linda reads the same help (help.apps, help.read) before answering how to do something, for every staff member whatever their role." \
  -m "Every guide is checked in CI: an app without a guide, or a guide that links a page or setting that no longer exists, fails the build."
RELEASE_CHECK_BASE=origin/main DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py release --check
git add morph/settings.py docs/RELEASE_NOTES.md CLAUDE.md
git commit -m "chore(release): <printed version> — Help inside the dashboard for every app

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

Expected: `release --check` prints `✓ version <vX.Y.Z> in sync with RELEASE_NOTES`. If the printed version is not v0.115.0, edit the CLAUDE.md entry first.

- [ ] **Step 3: Push and wait for every store**

```bash
git push origin main
SMOKE_DEADLINE_SECS=2400 scripts/deploy_smoke.sh <printed version>
```

Expected: `SMOKE OK — every store serves <printed version>`.

- [ ] **Step 4: Check the Help area on the live stores**

Write this script to the scratchpad as `live_help_check.py`. It never uses `force_login`; it builds a session directly and deletes it afterwards.

```python
import re

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY, get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.test import Client

hosts = [h.lstrip('.') for h in settings.ALLOWED_HOSTS if '.' in h and '*' not in h and 'localhost' not in h]
host = hosts[0] if hosts else 'localhost'
user = get_user_model().objects.filter(is_superuser=True, is_active=True).first()
s = SessionStore()
s[SESSION_KEY] = str(user.pk)
s[BACKEND_SESSION_KEY] = settings.AUTHENTICATION_BACKENDS[0]
s[HASH_SESSION_KEY] = user.get_session_auth_hash()
s.create()
try:
    c = Client(secure=True, HTTP_HOST=host, HTTP_X_FORWARDED_PROTO='https')
    c.cookies[settings.SESSION_COOKIE_NAME] = s.session_key
    for path in ('/dashboard/help/', '/dashboard/help/orders/', '/dashboard/help/?q=refund', '/dashboard/orders/'):
        r = c.get(path)
        html = r.content.decode()
        link = re.search(r'<p class="page-help"><a href="([^"]+)"', html)
        guide = 'help-guide' in html and 'no guide yet' not in html
        print(host, path, r.status_code, 'guide' if guide else '-', 'help-link=' + (link.group(1) if link else 'none'))
    from core.assistant.prompts import build_system_prompt

    print('linda prompt has help:', '`help.read`' in build_system_prompt())
finally:
    s.delete()
```

Run it in each store's web container: dotbooks `ghtnqf6lw2bg5229lv1sf4h9`, supernatural `z10xg4j7yq8x1htipw12a368`, montenegro `fo8rvcg94bmcyi43e8iq9tvm`, irving `j7xoogxjqgyakdsjw37eneuh`:

```bash
~/.ssh/tetra-ssh.sh -- scp <scratchpad>/live_help_check.py root@tetra.imbamarketing.com:/tmp/live_help_check.py
~/.ssh/tetra-ssh.sh "c=\$(docker ps --format '{{.Names}}' | grep '^web-<uuid>' | head -1); docker cp /tmp/live_help_check.py \$c:/tmp/x.py && docker exec \$c sh -c 'python manage.py shell < /tmp/x.py' 2>&1 | grep -v -E 'WARNING|DEBUG|INFO|objects imported'"
```

Expected per store:
- every path answers 200;
- `/dashboard/help/orders/` shows `guide`;
- `/dashboard/orders/` shows `help-link=/dashboard/help/orders/`;
- `linda prompt has help: True`.

- [ ] **Step 5: Error logs since the deploy**

In each store's container, count `core.errors.models.ErrorEvent` rows with `last_seen` in the last 40 minutes. Read each one's path and message. A row on a `/dashboard/help/` path, or naming `help_`, is a regression to fix in a PATCH release.

---

## Appendix A — the guide brief (Task 10, Step 1)

```
You are writing in-dashboard help for some of Morpheus's apps. The readers are store staff
(merchants and their team), not developers. Work in /Users/magnetoid/coding/morph and write
nothing but plugins/installed/<app>/help.md for each of your apps. Edit no code and no test.

For each app:

1. Read plugins/installed/<app>/app.py first: the label, description, requires,
   contribute_dashboard_pages (each DashboardPage's slug, label, section and nav),
   contribute_settings_panel and get_config_schema (each field's key and title),
   contribute_storefront_blocks, contribute_dashboard_cards and contribute_agent_tools.
   Then read the views, templates and services behind those pages, and the app's
   tests: their names and docstrings say what the code guarantees.

2. Write plugins/installed/<app>/help.md in exactly this shape:

   ---
   summary: <one plain sentence, at most 140 characters, on what the app does for the store>
   ---

   ## What it's for
   <what the app does for the store and who uses it>

   ## Set it up
   <what to switch on or fill in before it works: keys, accounts, settings fields>

   ## Common tasks
   - <one line per job staff do with it>

   ## Good to know
   <limits, what happens automatically, what it does not do>

   Rules:
   - Only those four headings, in that order. "What it's for" is required; leave out a
     section with nothing true to say. 60 to 400 words of body. One-line list items.
   - The summary is one plain sentence with no markup.
   - Describe only what the code does today. If a screen, setting or feature is broken,
     unfinished or does nothing, do not describe it as working; say plainly what works.
     An app with nothing working gets a short, honest guide saying what it does today.
     Never mention plans to remove, merge or change an app.
   - Never write a URL to the store's own pages. Link with markers only:
       [text](page:<slug>)          one of this app's DashboardPage slugs
       [text](page:<app>/<slug>)    another app's page
       [text](settings:<app>)       the app's settings (only if it has a settings panel
                                    or a nav='settings' page)
       [](field:<app>.<key>)        one field of its settings panel; empty text shows
                                    the field's live label
       [](section:<key>)            a sidebar section: home, ai, orders, products,
                                    customers, crm, vendors, affiliates, marketing,
                                    channels, content, analytics, seo
       [text](app:<name>)           another app's help
     Empty link text [] shows the place's live name. Outside sites (Stripe, Google
     Merchant Center) are plain https:// links.
   - Plain words a merchant uses. Never write: plugin, hook, Celery, queryset, middleware.
     Say "app" for an app. The assistant is called Linda in the dashboard; never write
     "Janus" except as the label of its own settings page.
   - No marketing language, no promises the code does not keep, no invented numbers.
     English, second person ("you"), short sentences.

3. Check your guides. Run, and fix your guides until it passes:
   DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress' .venv/bin/python manage.py test plugins.installed.release_notes.tests.test_help_files.GuideFormatTests plugins.installed.release_notes.tests.test_help_markers.GuideMarkerTests
   Failures for apps that are not yours belong to other writers working at the same
   time; ignore them.

4. Report back, not in the files:
   - for each app, three claims from its guide, each with the file:line that backs it;
   - every defect you noticed: a screen that errors, a setting nothing reads, a feature
     that does nothing, a label that says something the code does not do. Give the app,
     the problem and the file:line. Do not fix code.
```
