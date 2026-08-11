# richtext (Lexical) Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the TipTap rich-text editor with a self-hosted, vanilla-Lexical editor delivered as the `richtext` plugin, dropping the `esm.sh` CDN from the dashboard CSP with zero DB migration.

**Architecture:** A new plugin owns a vanilla (no-React) Lexical editor built once with `esbuild` into a committed IIFE bundle. Forms drop in a `{% richtext_field %}` inclusion tag that renders the same `.rte` markup and degrades to a plain `<textarea>` when the plugin is inactive. The bundle scans `[data-richtext]` elements, imports/exports HTML (so storage is unchanged), and re-scans after htmx swaps.

**Tech Stack:** Django template tags, vanilla JS, Lexical (`lexical` core + `@lexical/rich-text|list|link|code|history|html|utils|selection`), esbuild (dev-only, committed artifact), Playwright (browser smoke).

## Global Constraints

- **No React, no repo-wide build.** The build is isolated to `plugins/installed/richtext/frontend/`; `node_modules` is gitignored; the bundle is committed. No other file gains a build dependency.
- **No DB migration / no schema change.** Fields stay HTML `TextField`s. Editor imports/exports HTML.
- **Content format is HTML strings** written continuously into a hidden `<textarea name="…">`; the Django form POST is unchanged.
- **Keep `window.morph*Editor` globals** with `{getHTML(), setHTML(html), focus(), destroy()}` so the AI-draft/rewrite buttons keep working.
- **`unsafe-eval` STAYS** (Tailwind Play CDN owns it); this change only removes `https://esm.sh` from the dashboard `script-src` + `connect-src`.
- **Coolify/prod deploy has no Node** — the committed bundle is the source of truth for production.
- **Plugin name:** `richtext`. **Bundle global:** `window.MorphRichText`. **Test DB pin:** `DATABASE_URL='sqlite:///:memory:'`.
- Handled HTML vocabulary: `p, h2, h3, strong/b, em/i, s, code, pre, ul, ol, li, blockquote, a, img, hr`.

---

### Task 1: Plugin scaffold + registration

**Files:**
- Create: `plugins/installed/richtext/__init__.py` (empty)
- Create: `plugins/installed/richtext/apps.py`
- Create: `plugins/installed/richtext/app.py`
- Create: `plugins/installed/richtext/.gitignore`
- Create: `plugins/installed/richtext/tests/__init__.py`
- Modify: `morph/settings.py` (add `'richtext'` to `MORPHEUS_DEFAULT_APPS`, starts line 52)

**Interfaces:**
- Produces: a `RichTextPlugin(Plugin)` with `name='richtext'`, `has_models=False`, registered in `MORPHEUS_DEFAULT_APPS`; `app_registry.is_active('richtext')` returns `True` on a default boot.

- [ ] **Step 1: Write the failing test**

Create `plugins/installed/richtext/tests/__init__.py`:
```python
"""richtext plugin — Lexical editor as a self-hosted app."""

from django.test import SimpleTestCase


class RichTextPluginContractTests(SimpleTestCase):
    def test_plugin_registered_and_active(self):
        from plugins.registry import app_registry

        self.assertTrue(app_registry.is_active('richtext'))
        plugin = app_registry.get('richtext')
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.name, 'richtext')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.richtext -v 1`
Expected: FAIL — plugin not registered / module not found.

- [ ] **Step 3: Write the plugin files**

`plugins/installed/richtext/__init__.py`: empty file.

`plugins/installed/richtext/apps.py`:
```python
from django.apps import AppConfig


class RichTextConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.richtext'
    label = 'richtext'
    verbose_name = 'Rich Text Editor (Lexical)'
```

`plugins/installed/richtext/app.py`:
```python
"""richtext — self-hosted vanilla Lexical editor, contributed as a plugin.

Owns the editor bundle (built once with esbuild from frontend/editor.js,
committed to static/richtext/), the {% richtext_field %} widget tag, and the
shared editor CSS. Replaces the CDN-loaded TipTap that used to live inline in
the product + CMS page forms. Disable this plugin and every richtext_field
degrades to a plain <textarea> (see templatetags/richtext.py).
"""

from __future__ import annotations

from morpheus import Plugin


class RichTextPlugin(Plugin):
    name = 'richtext'
    label = 'Rich Text Editor'
    version = '1.0.0'
    description = (
        'Self-hosted Lexical rich-text editor. Provides the '
        '{% richtext_field %} widget used by the product and CMS page forms. '
        'No CDN, no build step at deploy time (the bundle is committed).'
    )
    has_models = False
```

`plugins/installed/richtext/.gitignore`:
```
frontend/node_modules/
frontend/package-lock.json
```

- [ ] **Step 4: Register in settings**

In `morph/settings.py`, inside the `MORPHEUS_DEFAULT_APPS` list (starts line 52), add `'richtext',` in alphabetical position (after `'reviews'` if present, else anywhere in the list).

- [ ] **Step 5: Run test to verify it passes**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.richtext -v 1`
Expected: PASS. Also run `DATABASE_URL='sqlite:///:memory:' python manage.py check` → no issues.

- [ ] **Step 6: Commit**

```bash
git add plugins/installed/richtext/ morph/settings.py
git commit -m "feat(richtext): plugin scaffold — Lexical editor as an app"
```

---

### Task 2: The `{% richtext_field %}` tag + widget template (disable-safe)

**Files:**
- Create: `plugins/installed/richtext/templatetags/__init__.py` (empty)
- Create: `plugins/installed/richtext/templatetags/richtext.py`
- Create: `plugins/installed/richtext/templates/richtext/_field.html`
- Modify: `plugins/installed/richtext/tests/__init__.py` (add render tests)

**Interfaces:**
- Consumes: `app_registry.is_active('richtext')` from Task 1.
- Produces: `{% richtext_field name value id allow_headings allow_images expose_as aria_label %}` inclusion tag. Active → a `<div class="rte" data-richtext data-allow-headings data-allow-images data-upload-url data-expose-as>` wrapper containing a toolbar, a `data-rte-mount` div, a hidden `.rte-source` textarea, and the real hidden `<textarea name="{name}" id="{id}">{value}`. Inactive → a bare `<textarea name="{name}" id="{id}" class="input" rows="10">{value}`. `value` is rendered inside a `<textarea>` (Django auto-escapes; the browser decodes it as the field value).

- [ ] **Step 1: Write the failing tests**

Append to `plugins/installed/richtext/tests/__init__.py`:
```python
from django.template import Context, Template
from django.test import TestCase


def _render(**kwargs):
    args = ' '.join(f'{k}={v!r}' if isinstance(v, str) else f'{k}={v}' for k, v in kwargs.items())
    tpl = Template('{% load richtext %}{% richtext_field ' + args + ' %}')
    return tpl.render(Context({}))


class RichTextFieldTagTests(TestCase):
    def test_active_renders_editor_markup(self):
        html = _render(
            name='description', value='<p>hi</p>', id='product-description',
            allow_headings=True, allow_images=False,
            expose_as='morphProductDescriptionEditor', aria_label='Product description',
        )
        self.assertIn('data-richtext', html)
        self.assertIn('data-rte-mount', html)
        self.assertIn('data-allow-headings="true"', html)
        self.assertIn('data-allow-images="false"', html)
        self.assertIn('data-expose-as="morphProductDescriptionEditor"', html)
        self.assertIn('/dashboard/media/api/upload/', html)  # upload url present
        # Real submit field is a hidden textarea carrying the value.
        self.assertIn('name="description"', html)
        self.assertIn('id="product-description"', html)
        self.assertIn('&lt;p&gt;hi&lt;/p&gt;', html)  # value escaped inside textarea

    def test_image_button_only_when_allowed(self):
        with_img = _render(name='body', value='', allow_images=True)
        without = _render(name='description', value='', allow_images=False)
        self.assertIn('data-rte="image"', with_img)
        self.assertNotIn('data-rte="image"', without)

    def test_heading_buttons_only_when_allowed(self):
        with_h = _render(name='body', value='', allow_headings=True)
        without = _render(name='short_description', value='', allow_headings=False)
        self.assertIn('data-rte="h2"', with_h)
        self.assertNotIn('data-rte="h2"', without)

    def test_degrades_to_textarea_when_plugin_inactive(self):
        from plugins.registry import app_registry

        original = app_registry.is_active
        app_registry.is_active = lambda n: False if n == 'richtext' else original(n)
        try:
            html = _render(name='description', value='<p>x</p>', id='product-description')
        finally:
            app_registry.is_active = original
        self.assertNotIn('data-richtext', html)
        self.assertIn('name="description"', html)
        self.assertIn('id="product-description"', html)
        self.assertIn('&lt;p&gt;x&lt;/p&gt;', html)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.richtext -v 1`
Expected: FAIL — `'richtext' is not a registered tag library`.

- [ ] **Step 3: Write the template tag**

`plugins/installed/richtext/templatetags/__init__.py`: empty file.

`plugins/installed/richtext/templatetags/richtext.py`:
```python
"""{% richtext_field %} — the Lexical editor widget.

Active plugin → full editor markup enhanced by static/richtext/
lexical-editor.bundle.js. Inactive → a plain <textarea> (graceful
degradation; the field still submits). The bundle scans [data-richtext]
elements, so no per-page init script is needed.
"""

from __future__ import annotations

from django import template

register = template.Library()

# Toolbar buttons rendered in order. Each: (action, title, label_html).
# `headings` / `image` groups are filtered by the tag's flags.
_BASE_BUTTONS = [
    ('bold', 'Bold', '<b>B</b>'),
    ('italic', 'Italic', '<i>I</i>'),
    ('strike', 'Strikethrough', '<s>S</s>'),
    ('code', 'Inline code', '&lt;&gt;'),
    ('_divider', '', ''),
]
_HEADING_BUTTONS = [
    ('h2', 'Heading 2', 'H2'),
    ('h3', 'Heading 3', 'H3'),
    ('paragraph', 'Paragraph', '¶'),
    ('_divider', '', ''),
]
_LIST_BUTTONS = [
    ('bulletList', 'Bullet list', '•'),
    ('orderedList', 'Numbered list', '1.'),
    ('blockquote', 'Blockquote', '❝'),
    ('codeBlock', 'Code block', '≡'),
    ('hr', 'Divider', '―'),
    ('_divider', '', ''),
]
_LINK_BUTTONS = [
    ('link', 'Insert link', '🔗'),
    ('unlink', 'Remove link', 'Unlink'),
]
_IMAGE_BUTTON = ('image', 'Insert image (upload)', '🖼')
_TAIL_BUTTONS = [
    ('clear', 'Clear formatting', '⌫'),
    ('_divider', '', ''),
    ('undo', 'Undo', '↶'),
    ('redo', 'Redo', '↷'),
    ('_spacer', '', ''),
    ('source', 'Edit HTML source', 'HTML'),
]


def _toolbar(allow_headings: bool, allow_images: bool) -> list:
    buttons = list(_BASE_BUTTONS)
    if allow_headings:
        buttons += _HEADING_BUTTONS
    buttons += _LIST_BUTTONS + _LINK_BUTTONS
    if allow_images:
        buttons.append(_IMAGE_BUTTON)
    buttons += _TAIL_BUTTONS
    return buttons


@register.inclusion_tag('richtext/_field.html')
def richtext_field(
    *,
    name: str,
    value: str = '',
    id: str = '',  # noqa: A002 — template-facing kwarg name
    allow_headings: bool = True,
    allow_images: bool = False,
    expose_as: str = '',
    aria_label: str = 'Rich text editor',
):
    from plugins.registry import app_registry

    active = bool(app_registry.is_active('richtext'))
    return {
        'active': active,
        'name': name,
        'value': value or '',
        'field_id': id or name,
        'allow_headings': bool(allow_headings),
        'allow_images': bool(allow_images),
        'expose_as': expose_as,
        'aria_label': aria_label,
        'upload_url': '/dashboard/media/api/upload/',
        'toolbar': _toolbar(bool(allow_headings), bool(allow_images)),
    }
```

- [ ] **Step 4: Write the widget template**

`plugins/installed/richtext/templates/richtext/_field.html`:
```django
{% if active %}
<div class="rte" data-richtext
     data-allow-headings="{{ allow_headings|yesno:'true,false' }}"
     data-allow-images="{{ allow_images|yesno:'true,false' }}"
     data-upload-url="{{ upload_url }}"
     {% if expose_as %}data-expose-as="{{ expose_as }}"{% endif %}
     data-aria-label="{{ aria_label }}">
  <div class="rte-toolbar" role="toolbar" aria-label="{{ aria_label }} formatting">
    {% for action, title, label in toolbar %}
      {% if action == '_divider' %}<span class="rte-divider"></span>
      {% elif action == '_spacer' %}<span class="rte-spacer"></span>
      {% else %}<button type="button" class="rte-btn" data-rte="{{ action }}" title="{{ title }}">{{ label|safe }}</button>{% endif %}
    {% endfor %}
  </div>
  <div class="rte-content" data-rte-mount aria-label="{{ aria_label }}"></div>
  <textarea class="rte-source" hidden></textarea>
  <textarea name="{{ name }}" id="{{ field_id }}" class="rte-hidden" hidden>{{ value }}</textarea>
</div>
{% else %}
<textarea name="{{ name }}" id="{{ field_id }}" class="input w-full" rows="10">{{ value }}</textarea>
{% endif %}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.richtext -v 1`
Expected: PASS (all 5 tests).

- [ ] **Step 6: Commit**

```bash
git add plugins/installed/richtext/templatetags/ plugins/installed/richtext/templates/ plugins/installed/richtext/tests/__init__.py
git commit -m "feat(richtext): {% richtext_field %} widget tag + disable-safe template"
```

---

### Task 3: frontend/editor.js + esbuild build → committed bundle + CSS

**Files:**
- Create: `plugins/installed/richtext/frontend/package.json`
- Create: `plugins/installed/richtext/frontend/editor.js`
- Create: `plugins/installed/richtext/frontend/README.md`
- Create (built artifact, committed): `plugins/installed/richtext/static/richtext/lexical-editor.bundle.js`
- Create: `plugins/installed/richtext/static/richtext/editor.css`

**Interfaces:**
- Consumes: the `[data-richtext]` markup from Task 2.
- Produces: `window.MorphRichText.scan(root=document)` (idempotent) and, per `data-expose-as`, `window[name] = {getHTML(), setHTML(html), focus(), destroy()}`.

> **Note on testing this task:** the editor is browser JS with no unit harness in this repo. Its gate is: (a) the bundle builds, (b) `node --check` passes on the bundle, and (c) the Playwright smoke in Task 7. Treat `editor.js` as the one task with a browser feedback loop — iterate it until Task 7 is green rather than expecting first-try correctness.

- [ ] **Step 1: Write `frontend/package.json`**

```json
{
  "name": "morph-richtext",
  "private": true,
  "version": "1.0.0",
  "description": "Vanilla Lexical editor bundle for the Morpheus richtext plugin. Build only; not published.",
  "scripts": {
    "build": "esbuild editor.js --bundle --format=iife --global-name=MorphRichText --minify --legal-comments=none --outfile=../static/richtext/lexical-editor.bundle.js"
  },
  "devDependencies": {
    "esbuild": "^0.24.0",
    "lexical": "^0.21.0",
    "@lexical/rich-text": "^0.21.0",
    "@lexical/list": "^0.21.0",
    "@lexical/link": "^0.21.0",
    "@lexical/code": "^0.21.0",
    "@lexical/history": "^0.21.0",
    "@lexical/html": "^0.21.0",
    "@lexical/selection": "^0.21.0",
    "@lexical/utils": "^0.21.0"
  }
}
```

- [ ] **Step 2: Write `frontend/editor.js`**

```javascript
/* Morpheus rich-text editor — vanilla Lexical (no React). Built with esbuild
   into ../static/richtext/lexical-editor.bundle.js (committed). Exposes
   window.MorphRichText.scan(); enhances every [data-richtext] wrapper. */
import {
  createEditor, $getRoot, $getSelection, $isRangeSelection,
  $createParagraphNode, $insertNodes, FORMAT_TEXT_COMMAND,
  UNDO_COMMAND, REDO_COMMAND, DecoratorNode,
} from 'lexical';
import {
  HeadingNode, QuoteNode, registerRichText,
  $createHeadingNode, $createQuoteNode,
} from '@lexical/rich-text';
import {
  ListNode, ListItemNode, registerList,
  INSERT_ORDERED_LIST_COMMAND, INSERT_UNORDERED_LIST_COMMAND,
} from '@lexical/list';
import { LinkNode, $toggleLink } from '@lexical/link';
import { CodeNode, $createCodeNode } from '@lexical/code';
import { createEmptyHistoryState, registerHistory } from '@lexical/history';
import { $generateHtmlFromNodes, $generateNodesFromDOM } from '@lexical/html';
import { mergeRegister } from '@lexical/utils';
import { $setBlocksType } from '@lexical/selection';

/* ---- Custom leaf nodes: image + horizontal rule (Lexical has neither) ---- */
class ImageNode extends DecoratorNode {
  constructor(src, alt, key) { super(key); this.__src = src; this.__alt = alt || ''; }
  static getType() { return 'image'; }
  static clone(n) { return new ImageNode(n.__src, n.__alt, n.__key); }
  static importDOM() {
    return { img: () => ({ conversion: (el) => ({ node: new ImageNode(el.getAttribute('src') || '', el.getAttribute('alt') || '') }), priority: 0 }) };
  }
  exportDOM() {
    const img = document.createElement('img');
    img.setAttribute('src', this.__src);
    if (this.__alt) img.setAttribute('alt', this.__alt);
    img.setAttribute('loading', 'lazy');
    img.className = 'rte-img';
    return { element: img };
  }
  createDOM() { const span = document.createElement('span'); span.className = 'rte-img-wrap'; return span; }
  updateDOM() { return false; }
  decorate() {
    const img = document.createElement('img');
    img.src = this.__src; img.alt = this.__alt; img.loading = 'lazy'; img.className = 'rte-img';
    return img;
  }
}
function $createImageNode(src, alt) { return new ImageNode(src, alt); }

class HrNode extends DecoratorNode {
  static getType() { return 'horizontalrule'; }
  static clone(n) { return new HrNode(n.__key); }
  static importDOM() { return { hr: () => ({ conversion: () => ({ node: new HrNode() }), priority: 0 }) }; }
  exportDOM() { return { element: document.createElement('hr') }; }
  createDOM() { const span = document.createElement('span'); span.className = 'rte-hr-wrap'; return span; }
  updateDOM() { return false; }
  decorate() { return document.createElement('hr'); }
}
function $createHrNode() { return new HrNode(); }

const NODES = [HeadingNode, QuoteNode, ListNode, ListItemNode, LinkNode, CodeNode, ImageNode, HrNode];

/* ---- HTML in/out ---- */
function loadHTML(editor, html) {
  editor.update(() => {
    const root = $getRoot(); root.clear();
    const trimmed = (html || '').trim();
    if (!trimmed) { root.append($createParagraphNode()); return; }
    const dom = new DOMParser().parseFromString(trimmed, 'text/html');
    const nodes = $generateNodesFromDOM(editor, dom);
    root.append(...nodes);
    if (root.getChildrenSize() === 0) root.append($createParagraphNode());
  });
}
function serializeHTML(editor) {
  let html = '';
  editor.getEditorState().read(() => { html = $generateHtmlFromNodes(editor, null); });
  return html;
}

/* ---- Toolbar command dispatch ---- */
function applyBlock(editor, factory) {
  editor.update(() => {
    const sel = $getSelection();
    if ($isRangeSelection(sel)) $setBlocksType(sel, factory);
  });
}
function dispatch(editor, action, ctx) {
  switch (action) {
    case 'bold': editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'bold'); break;
    case 'italic': editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'italic'); break;
    case 'strike': editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'strikethrough'); break;
    case 'code': editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'code'); break;
    case 'h2': applyBlock(editor, () => $createHeadingNode('h2')); break;
    case 'h3': applyBlock(editor, () => $createHeadingNode('h3')); break;
    case 'paragraph': applyBlock(editor, () => $createParagraphNode()); break;
    case 'blockquote': applyBlock(editor, () => $createQuoteNode()); break;
    case 'codeBlock': applyBlock(editor, () => $createCodeNode()); break;
    case 'bulletList': editor.dispatchCommand(INSERT_UNORDERED_LIST_COMMAND, undefined); break;
    case 'orderedList': editor.dispatchCommand(INSERT_ORDERED_LIST_COMMAND, undefined); break;
    case 'hr': editor.update(() => { $insertNodes([$createHrNode()]); }); break;
    case 'link': {
      const url = window.prompt('Link URL'); if (url === null) break;
      editor.update(() => { $toggleLink(url || null); }); break;
    }
    case 'unlink': editor.update(() => { $toggleLink(null); }); break;
    case 'clear': editor.update(() => {
      const sel = $getSelection();
      if ($isRangeSelection(sel)) { ['bold','italic','strikethrough','code'].forEach((f) => { if (sel.hasFormat(f)) sel.formatText(f); }); }
    }); break;
    case 'undo': editor.dispatchCommand(UNDO_COMMAND, undefined); break;
    case 'redo': editor.dispatchCommand(REDO_COMMAND, undefined); break;
    case 'image': pickAndUploadImage(editor, ctx); break;
    case 'source': toggleSource(ctx); break;
    default: break;
  }
}

async function pickAndUploadImage(editor, ctx) {
  const input = document.createElement('input');
  input.type = 'file'; input.accept = 'image/*';
  input.onchange = async () => {
    const file = input.files && input.files[0]; if (!file) return;
    const tokenEl = document.querySelector('[name=csrfmiddlewaretoken]');
    const fd = new FormData(); fd.append('file', file);
    const resp = await fetch(ctx.uploadUrl, {
      method: 'POST', body: fd, credentials: 'same-origin',
      headers: tokenEl ? { 'X-CSRFToken': tokenEl.value } : {},
    });
    const data = await resp.json();
    if (resp.ok && data.url) {
      editor.update(() => { $insertNodes([$createImageNode(data.url, data.alt_text || data.filename || '')]); });
    }
  };
  input.click();
}

/* Source (HTML) toggle: swap the contenteditable for a raw textarea. */
function toggleSource(ctx) {
  const src = ctx.source;
  if (src.hidden) {
    src.value = serializeHTML(ctx.editor);
    src.hidden = false; ctx.mount.style.display = 'none';
  } else {
    loadHTML(ctx.editor, src.value);
    src.hidden = true; ctx.mount.style.display = '';
  }
}

/* ---- Mount one [data-richtext] wrapper ---- */
function mountOne(wrap) {
  const mount = wrap.querySelector('[data-rte-mount]');
  const hidden = wrap.querySelector('.rte-hidden');
  const source = wrap.querySelector('.rte-source');
  const toolbar = wrap.querySelector('.rte-toolbar');
  if (!mount || !hidden) return;

  const editor = createEditor({
    namespace: 'morph-richtext', nodes: NODES,
    onError: (e) => { console.error('richtext:', e); },
    theme: { paragraph: 'rte-p', heading: { h2: 'rte-h2', h3: 'rte-h3' }, list: { ul: 'rte-ul', ol: 'rte-ol' }, quote: 'rte-quote', link: 'rte-link' },
  });
  mount.contentEditable = 'true';
  mount.setAttribute('role', 'textbox');
  mount.setAttribute('aria-multiline', 'true');
  editor.setRootElement(mount);

  const ctx = { editor, mount, source, uploadUrl: wrap.getAttribute('data-upload-url') || '/dashboard/media/api/upload/' };

  mergeRegister(
    registerRichText(editor),
    registerList(editor),
    registerHistory(editor, createEmptyHistoryState(), 300),
  );

  // Decorator nodes (img, hr) mount their DOM here — required for vanilla.
  editor.registerDecoratorListener((decorators) => {
    for (const [key, el] of Object.entries(decorators)) {
      const host = editor.getElementByKey(key);
      if (host && el instanceof Node && !host.contains(el)) host.appendChild(el);
    }
  });

  loadHTML(editor, hidden.value);

  editor.registerUpdateListener(() => {
    const html = serializeHTML(editor);
    hidden.value = html;
    if (source && !source.hidden) source.value = html;
  });

  if (toolbar) {
    toolbar.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-rte]'); if (!btn) return;
      e.preventDefault();
      dispatch(editor, btn.getAttribute('data-rte'), ctx);
      editor.focus();
    });
  }

  const handle = {
    getHTML: () => serializeHTML(editor),
    setHTML: (html) => loadHTML(editor, html),
    focus: () => editor.focus(),
    destroy: () => editor.setRootElement(null),
  };
  const exposeAs = wrap.getAttribute('data-expose-as');
  if (exposeAs) window[exposeAs] = handle;
  return handle;
}

export function scan(root) {
  const scope = root || document;
  scope.querySelectorAll('[data-richtext]:not([data-richtext-ready])').forEach((wrap) => {
    wrap.setAttribute('data-richtext-ready', '1');
    try { mountOne(wrap); } catch (e) { console.error('richtext mount failed:', e); }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => scan(document));
} else {
  scan(document);
}
```

- [ ] **Step 3: Write `frontend/README.md`**

```markdown
# richtext frontend (Lexical)

`editor.js` is the source. The committed build artifact
`../static/richtext/lexical-editor.bundle.js` is what production serves — the
Coolify/Python deploy has no Node, so **you must rebuild + commit the bundle
whenever `editor.js` changes**.

## Rebuild

    cd plugins/installed/richtext/frontend
    npm install          # dev-only; node_modules is gitignored
    npm run build        # → ../static/richtext/lexical-editor.bundle.js

Commit both `editor.js` and the regenerated bundle in the same change.
```

- [ ] **Step 4: Write `static/richtext/editor.css`**

Move the `.rte*` rules out of `base.html` (lines ~580-603) into this file, adding the new classes referenced by `editor.js`:
```css
/* Rich-text editor (Lexical) — shared dashboard component. */
.rte { border:1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface); }
.rte-toolbar { display:flex; flex-wrap:wrap; align-items:center; gap:2px; padding:6px 8px; border-bottom:1px solid var(--border); background: var(--surface-2, var(--surface)); }
.rte-btn { min-width:1.9rem; height:1.9rem; padding:0 .4rem; font-size:.8rem; border:1px solid transparent; border-radius:var(--radius-sm); background:transparent; color:var(--text); cursor:pointer; display:inline-flex; align-items:center; justify-content:center; }
.rte-btn:hover { background: var(--surface-2); }
.rte-btn.is-active { background: var(--surface-3); color: var(--text); }
.rte-divider { width:1px; height:1.2rem; background:var(--border); margin:0 3px; }
.rte-spacer { flex:1; }
.rte-content { padding:.75rem .9rem; min-height:8rem; font-size:.9rem; line-height:1.6; color:var(--text); outline:none; }
.rte-content:focus { outline:none; }
.rte-content-short { min-height:4rem; }
.rte-source { width:100%; min-height:8rem; padding:.75rem .9rem; font-family:ui-monospace,monospace; font-size:.8rem; border:0; background:var(--surface); color:var(--text); resize:vertical; }
.rte-content .rte-h2 { font-size:1.25rem; font-weight:600; margin:.6rem 0 .3rem; }
.rte-content .rte-h3 { font-size:1.1rem; font-weight:600; margin:.5rem 0 .3rem; }
.rte-content .rte-ul { list-style:disc; padding-left:1.4rem; }
.rte-content .rte-ol { list-style:decimal; padding-left:1.4rem; }
.rte-content .rte-quote { border-left:3px solid var(--border); padding-left:.8rem; color:var(--text-muted); }
.rte-content .rte-link { color:var(--brand); text-decoration:underline; }
.rte-content .rte-img { max-width:100%; height:auto; border-radius:4px; }
.rte-content pre { background:var(--surface-2); padding:.6rem .8rem; border-radius:var(--radius-sm); overflow-x:auto; font-family:ui-monospace,monospace; font-size:.8rem; }
```

- [ ] **Step 5: Build the bundle**

Run:
```bash
cd plugins/installed/richtext/frontend && npm install && npm run build && cd -
node --check plugins/installed/richtext/static/richtext/lexical-editor.bundle.js && echo BUNDLE-OK
```
Expected: `npm run build` writes the bundle; `node --check` prints `BUNDLE-OK` (valid JS, no syntax error). The bundle should reference `MorphRichText` (grep it): `grep -c MorphRichText plugins/installed/richtext/static/richtext/lexical-editor.bundle.js` → ≥ 1.

- [ ] **Step 6: Commit**

```bash
git add plugins/installed/richtext/frontend/ plugins/installed/richtext/static/
git commit -m "feat(richtext): vanilla Lexical editor.js + esbuild build + committed bundle + css"
```

---

### Task 4: base.html wiring (guarded load + htmx scan; move CSS)

**Files:**
- Modify: `plugins/installed/admin_dashboard/templates/admin_dashboard/base.html` (remove `.rte*` CSS block ~lines 580-603; add guarded bundle+css load; add `MorphRichText.scan()` to the `htmx:afterSwap` handler at line 1529)

**Interfaces:**
- Consumes: `window.MorphRichText.scan` (Task 3), `{% plugin_enabled %}` tag (already loaded via `{% load ... morph ... %}` in base.html line 1).
- Produces: the bundle + css loaded once per dashboard page when `richtext` is active; a re-scan after every htmx swap.

- [ ] **Step 1: Remove the old TipTap CSS block**

In `base.html`, delete the CSS block starting at the comment `/* ── Rich-text editor (TipTap) — shared dashboard component ... ── */` (line ~580) through its last `.rte*`/`.ProseMirror*` rule (~line 603). (This styling now lives in `static/richtext/editor.css`.)

- [ ] **Step 2: Add the guarded asset load**

In `base.html`, immediately before `</head>` (or alongside the other `{% static %}` asset links near the top-of-body scripts), add:
```django
{% load static %}
{% plugin_enabled "richtext" as richtext_on %}
{% if richtext_on %}
<link rel="stylesheet" href="{% static 'richtext/editor.css' %}">
<script src="{% static 'richtext/lexical-editor.bundle.js' %}" defer></script>
{% endif %}
```
(`{% load static %}` and `{% load morph %}` are already present at line 1 — do not duplicate; add only the `plugin_enabled`/`if` block.)

- [ ] **Step 3: Add the htmx re-scan**

In the `htmx:afterSwap` handler (starts line 1529), next to the existing `lucide.createIcons()` / `Morph.reinit` calls, add:
```javascript
      if (window.MorphRichText && typeof window.MorphRichText.scan === 'function') window.MorphRichText.scan(e.detail.target);
```

- [ ] **Step 4: Verify base renders + tag balance**

Run:
```bash
python3 - <<'EOF'
import re
s = open('plugins/installed/admin_dashboard/templates/admin_dashboard/base.html').read()
for tag in ['if','for','block','with','comment','plugin_enabled']:
    if tag == 'plugin_enabled': continue
    o=len(re.findall(r'{%% *%s ' % tag, s)); c=len(re.findall(r'{%% *end%s' % tag, s))
    assert o==c, (tag,o,c)
assert 'richtext/lexical-editor.bundle.js' in s
assert 'MorphRichText.scan' in s
assert 'TipTap' not in s  # old CSS comment gone
print('base.html OK')
EOF
DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.admin_dashboard.tests.test_home_modular -v 1
```
Expected: `base.html OK`; home-modular tests PASS (base still renders).

- [ ] **Step 5: Commit**

```bash
git add plugins/installed/admin_dashboard/templates/admin_dashboard/base.html
git commit -m "feat(richtext): load bundle in dashboard shell (guarded) + rescan on htmx swap; move rte css to plugin"
```

---

### Task 5: Cut over the product + CMS forms

**Files:**
- Modify: `plugins/installed/admin_dashboard/templates/admin_dashboard/product_form.html` (replace short-desc block ~181-203, long-desc block ~223-252, the two TipTap `<script type="module">` blocks ~339-497, and the AI-draft/rewrite inline scripts ~500+)
- Modify: `plugins/installed/cms/templates/cms/dashboard/page_form.html` (replace body block ~60-89 and its TipTap `<script type="module">` ~189-343)

**Interfaces:**
- Consumes: `{% richtext_field %}` (Task 2), the bundle globals (Task 3).
- Produces: forms that emit `[data-richtext]` and still POST `description`/`short_description`/`body` as HTML via the same hidden textarea names.

- [ ] **Step 1: Product form — swap both fields to the tag**

At the top of `product_form.html`, ensure `{% load richtext %}` is present (add after the existing `{% load %}` lines).

Replace the **short description** block (the `<div id="short-description-editor-wrap" ...>` through its `<textarea id="product-short-description" name="short_description" hidden>...`, ~181-203) with:
```django
{% richtext_field name="short_description" value=form.short_description.value id="product-short-description" allow_headings=False allow_images=False expose_as="morphProductShortDescriptionEditor" aria_label="Short description" %}
```

Replace the **long description** block (the `<div id="description-editor-wrap" class="rte">` through `<textarea id="product-description" name="description" hidden>...`, ~223-252) with:
```django
{% richtext_field name="description" value=form.description.value id="product-description" allow_headings=True allow_images=False expose_as="morphProductDescriptionEditor" aria_label="Product description" %}
```
(Keep the surrounding `<label>` + AI-draft/rewrite button row at ~205-222 exactly as-is.)

- [ ] **Step 2: Product form — delete the TipTap module scripts, fix AI buttons**

Delete both `<script type="module">` blocks that import from `esm.sh` and call `wireTiptap(...)` (~339-497).

In the AI-draft / AI-rewrite inline `<script>` (~500+), find where it writes the result into the hidden textarea (it sets `ta.value = ...` on `#product-description`) and replace that write with the editor handle:
```javascript
// Was: document.getElementById('product-description').value = html; (+ MutationObserver hack)
if (window.morphProductDescriptionEditor) window.morphProductDescriptionEditor.setHTML(html);
```
Remove any now-dead monkey-patched-setter / MutationObserver code that existed only to feed TipTap.

- [ ] **Step 3: CMS form — swap body to the tag**

At the top of `page_form.html`, ensure `{% load richtext %}` is present.

Replace the body block (`<div class="rte">` at ~61 through `<textarea id="page-body" name="body" hidden>{{ page.body|default:'' }}</textarea></div>`, ~61-89) with:
```django
<label class="block text-xs font-medium mb-1">Body</label>
{% richtext_field name="body" value=page.body id="page-body" allow_headings=True allow_images=True expose_as="morphPageBodyEditor" aria_label="Page body" %}
```

Delete the CMS TipTap `<script type="module">` block (~189-343), including its `pickAndUploadImage` (the bundle now owns image upload).

- [ ] **Step 4: Verify no esm.sh / TipTap remains in the two forms; tag balance**

Run:
```bash
grep -rn "esm.sh\|tiptap\|wireTiptap\|ProseMirror" plugins/installed/admin_dashboard/templates/admin_dashboard/product_form.html plugins/installed/cms/templates/cms/dashboard/page_form.html || echo "CLEAN: no TipTap refs"
python3 - <<'EOF'
import re
for f in ['plugins/installed/admin_dashboard/templates/admin_dashboard/product_form.html',
          'plugins/installed/cms/templates/cms/dashboard/page_form.html']:
    s=open(f).read()
    for tag in ['if','for','block','with','comment']:
        o=len(re.findall(r'{%% *%s ' % tag,s)); c=len(re.findall(r'{%% *end%s' % tag,s))
        assert o==c,(f,tag,o,c)
    assert 'richtext_field' in s
print('forms OK')
EOF
```
Expected: `CLEAN: no TipTap refs`; `forms OK`.

- [ ] **Step 5: Run the affected Django suites**

Run:
```bash
DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.admin_dashboard plugins.installed.cms plugins.installed.richtext -v 1
```
Expected: OK (existing product/CMS form tests still pass — field names + hidden textareas unchanged).

- [ ] **Step 6: Commit**

```bash
git add plugins/installed/admin_dashboard/templates/admin_dashboard/product_form.html plugins/installed/cms/templates/cms/dashboard/page_form.html
git commit -m "feat(richtext): cut product + CMS forms over to {% richtext_field %}; drop inline TipTap"
```

---

### Task 6: Drop esm.sh from the dashboard CSP + update the memory note

**Files:**
- Modify: `core/security_headers.py` (dashboard `script-src` ~line 104 and `connect-src` ~line 113; comment ~98-103)
- Modify: `/Users/magnetoid/.claude/projects/-Users-magnetoid-coding-morph/memory/dashboard-csp-unsafe-eval.md`

**Interfaces:**
- Consumes: nothing at runtime — the editor is now `'self'`.
- Produces: a dashboard CSP with no `esm.sh`, `'unsafe-eval'` retained for Tailwind.

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_csp_richtext.py`:
```python
from django.test import Client, TestCase, override_settings


@override_settings(CSP_DASHBOARD_ENFORCE=True)
class DashboardCspTests(TestCase):
    def _dashboard_csp(self):
        # Any /dashboard/ path — the middleware sets the header regardless of auth.
        resp = Client().get('/dashboard/')
        return resp.headers.get('Content-Security-Policy', '')

    def test_esm_sh_dropped_from_dashboard_csp(self):
        csp = self._dashboard_csp()
        self.assertNotIn('esm.sh', csp)

    def test_unsafe_eval_retained_for_tailwind(self):
        csp = self._dashboard_csp()
        self.assertIn("'unsafe-eval'", csp)
```

- [ ] **Step 2: Run test to verify the esm.sh assertion fails**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test core.tests.test_csp_richtext -v 1`
Expected: `test_esm_sh_dropped_from_dashboard_csp` FAILS (esm.sh still present); the unsafe-eval test PASSES.

- [ ] **Step 3: Edit the CSP**

In `core/security_headers.py`:
- In `_CSP_DASHBOARD_ENFORCE` `script-src` (~line 104), remove ` https://esm.sh` (keep `'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://unpkg.com`).
- In `connect-src` (~line 113), remove `https://esm.sh` (keep `https://unpkg.com` if used elsewhere; otherwise remove that too — verify with a grep for `unpkg` usage in dashboard templates first).
- Replace the `'unsafe-eval'` rationale comment (~98-103) with:
```python
# 'unsafe-eval' is required by the Tailwind Play CDN's JIT compiler
# (cdn.tailwindcss.com), which evals at runtime. The TipTap editor that
# also needed it is gone (replaced by the self-hosted richtext/Lexical
# bundle, served from 'self'), so esm.sh was dropped from script-src +
# connect-src. To finally remove 'unsafe-eval', precompile Tailwind to a
# static stylesheet — tracked as a separate follow-up.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test core.tests.test_csp_richtext -v 1`
Expected: PASS (both).

- [ ] **Step 5: Update the memory note**

In `/Users/magnetoid/.claude/projects/-Users-magnetoid-coding-morph/memory/dashboard-csp-unsafe-eval.md`, update the body to: `unsafe-eval` is now owned ONLY by the Tailwind Play CDN JIT (TipTap is gone — replaced by the self-hosted richtext/Lexical bundle at `static/richtext/`, so `esm.sh` was removed from the dashboard CSP). Removing `unsafe-eval` now requires precompiling Tailwind. Keep the file's frontmatter; update the one-line hook in `MEMORY.md` if its wording references TipTap.

- [ ] **Step 6: Commit**

```bash
git add core/security_headers.py core/tests/test_csp_richtext.py
git commit -m "feat(richtext): drop esm.sh from dashboard CSP (TipTap gone); note Tailwind as sole unsafe-eval owner"
```

---

### Task 7: Playwright browser smoke (the functional gate)

**Files:** none committed (verification procedure run at execution time with the Playwright MCP against a local `runserver`).

**Interfaces:** Consumes the whole stack (Tasks 1-6). This is the real gate for `editor.js` — iterate Task 3 until every check below passes.

- [ ] **Step 1: Boot a local server with the built bundle**

Run (background): `DATABASE_URL='sqlite:///:memory:' python manage.py migrate && DATABASE_URL='sqlite:///:memory:' python manage.py runserver 8999`
(Or use the existing SQLite dev path from `docs/QUICK_START.md`.) Ensure a staff user exists to reach `/dashboard/`.

- [ ] **Step 2: Product form — type + round-trip**

With the Playwright MCP: navigate to the product-edit form, click into the description editor, type `Hello **world**` styling via the toolbar (bold), then read the hidden `#product-description` textarea value and assert it contains `<p>` and `<strong>` (or `<b>`). Submit; reload; assert the editor re-renders the saved HTML.

- [ ] **Step 3: Existing-content load**

Open a product that already has HTML in `description`; assert the editor's `[data-rte-mount]` renders the formatted content (not raw tags).

- [ ] **Step 4: CMS image upload**

On the CMS page form, click the Image toolbar button, choose a small test image; assert an `<img loading="lazy">` appears in the editor and the hidden `#page-body` value contains `<img`.

- [ ] **Step 5: AI-draft button**

Click "Draft with AI" (or call `window.morphProductDescriptionEditor.setHTML('<p>drafted</p>')` via `browser_evaluate`); assert the editor shows the new content and the hidden textarea updates.

- [ ] **Step 6: CSP console check**

Capture browser console over the product + CMS form loads; assert **zero** `Content-Security-Policy` violation messages and **no** request to `esm.sh` in the network log.

- [ ] **Step 7: Record the result**

If all pass, note it in the PR/commit message. If any fail, fix `editor.js` (Task 3), rebuild + recommit the bundle, and re-run this task.

---

## Self-Review

**Spec coverage:** plugin scaffold (T1) · bundle self-hosted eval-free (T3) · widget tag + disable-safe (T2) · HTML in/out zero-migration (T3 loadHTML/serializeHTML) · AI-draft globals (T3 handle + T5 step 2) · CMS image upload (T3 pickAndUploadImage + T5) · base.html guarded load + htmx scan + CSS move (T4) · form cutover (T5) · CSP drop esm.sh keep unsafe-eval (T6) · settings registration (T1) · Django tests (T1/T2/T5/T6) · Playwright smoke (T7). All spec sections mapped.

**Placeholder scan:** no TBD/TODO; every code step shows complete code; the one browser-JS task (T3) is explicitly gated by the T7 smoke rather than a fake unit test.

**Type/name consistency:** `MorphRichText.scan`, `richtext_field`, `data-richtext`, `data-rte-mount`, `.rte-hidden`, `.rte-source`, exposeAs globals `morphProductDescriptionEditor` / `morphProductShortDescriptionEditor` / `morphPageBodyEditor`, upload URL `/dashboard/media/api/upload/` — used identically across tag, template, editor.js, and cutover.
