# richtext — Lexical editor as a self-hosted plugin

**Date:** 2026-07-03 · **Status:** approved (owner) · **Approach:** A (self-hosted
vanilla Lexical, one-time isolated esbuild, committed bundle)

## Goal

Replace the TipTap rich-text editor with **Lexical**, delivered as a Morpheus
plugin (`richtext`), self-hosted (no CDN), so the editor is a swappable app and
the dashboard CSP can drop `https://esm.sh`. Four owner drivers: off buggy
TipTap · modern editor · editor-as-plugin · tighter CSP / no CDN.

## Non-goals

- **No React, no repo-wide build pipeline.** The one build step is isolated to
  this plugin's `frontend/` and produces a committed artifact; the rest of the
  repo stays no-build vanilla JS + Django templates + Tailwind.
- **No DB migration / no schema change.** Fields stay HTML `TextField`s. The
  editor imports/exports the same HTML vocabulary TipTap did.
- **Not dropping `unsafe-eval` in this change.** The Tailwind Play CDN JIT is
  its other owner; fully removing eval is a separate follow-up (precompile
  Tailwind). This change removes the CDN dependency and the `esm.sh` allowlist
  entry only.
- **Journal is out of scope** — it's a separate JSON `document_json` block
  system, not TipTap.

## Current state (from exploration, 2026-07-03)

TipTap v3.23.4 is loaded no-build as ES modules from `esm.sh`, inlined in **two**
templates, editing **three** fields, via ~130 lines of duplicated `wireTiptap()`:

| Surface | Template | Fields | Model | Image button |
|---|---|---|---|---|
| Product form | `admin_dashboard/templates/admin_dashboard/product_form.html` | `description`, `short_description` | `catalog.Product` | no |
| CMS page form | `cms/templates/cms/dashboard/page_form.html` | `body` | `cms.Page` | yes |

- **Storage: HTML strings** in `TextField`s. TipTap writes `editor.getHTML()`
  continuously into a hidden `<textarea name="…">`; the Django form POST carries
  it. No submit handler.
- **Storefront render:** `product_detail.html:66,251` render with `|safe`; CMS
  `Page.save()` runs `bleach.clean()` against an allowlist (`cms/models.py`).
  Product descriptions are trusted staff input (not bleached).
- **Legacy Markdown rows** are converted to HTML at read time by
  `admin_dashboard/forms/_helpers.py:_ensure_html()` before reaching the editor.
- **AI-draft button** (`#ai-draft-description`) sets the hidden textarea's
  `.value` and relies on a monkey-patched setter + `MutationObserver` to push
  into the editor.
- **CMS image insert** uploads to `/dashboard/media/api/upload/` then inserts an
  `<img>`.
- **CSP:** `core/security_headers.py` dashboard policy keeps `'unsafe-eval'`
  (comment: required by TipTap esm.sh `new Function` **and** Tailwind Play CDN
  JIT) and allowlists `esm.sh` in `script-src` + `connect-src`.
- **No React, no bundler, no package.json** anywhere in the repo. `base.html`
  literally states "no React, no build pipeline."

## Architecture

### The plugin
`plugins/installed/richtext/` — standard Morpheus plugin (AppConfig +
`app.py` manifest, registered in `MORPHEUS_DEFAULT_APPS`). It owns the
editor source, the build, the committed bundle+CSS, the widget tag, and tests.

### The bundle (self-hosted, eval-free)
- **Source:** `frontend/editor.js` — vanilla Lexical, no React. Deps: `lexical`
  core + `@lexical/rich-text` (HeadingNode, QuoteNode, registerRichText),
  `@lexical/list` (ListNode/ListItemNode, registerList, list commands),
  `@lexical/link` (LinkNode, TOGGLE_LINK_COMMAND), `@lexical/history`
  (registerHistory), `@lexical/html` (`$generateHtmlFromNodes`,
  `$generateNodesFromDOM`), `@lexical/utils` (mergeRegister, `$setBlocksType`).
- **Custom nodes:** a minimal `ImageNode` (DecoratorNode, ~60 lines) with
  `importDOM`/`exportDOM` ⇄ `<img src alt loading="lazy">`, and a minimal
  `HorizontalRuleNode` (~20 lines) ⇄ `<hr>`. Parity with TipTap; matches the
  bleach allowlist.
- **Build:** `frontend/package.json` pins dev-deps + a build script; a single
  `npx esbuild frontend/editor.js --bundle --minify --format=iife
  --global-name=MorphRichText --outfile=static/richtext/lexical-editor.bundle.js`.
  `frontend/node_modules/` is gitignored; the **bundle is committed** so the
  Python/Coolify deploy needs no Node. `frontend/README.md` documents the
  rebuild command.
- **No eval:** a real esbuild IIFE has no `new Function`, so the editor no
  longer needs `esm.sh` in CSP.

### The bundle's public contract
The IIFE exposes `window.MorphRichText`:
- `MorphRichText.scan(root=document)` — idempotent; finds every
  `[data-richtext]:not([data-richtext-ready])` under `root`, mounts an editor,
  marks it ready. Called on `DOMContentLoaded` and from the dashboard's existing
  `htmx:afterSwap` handler.
- Per mount, if `data-expose-as` is set, publishes an instance handle on that
  `window` global with `{ getHTML(), setHTML(html), focus(), destroy() }`.

Mount options come from `data-*` attributes on the wrapper: `data-allow-headings`,
`data-allow-images`, `data-upload-url`, `data-expose-as`, `data-aria-label`.

### HTML in/out (zero migration)
- **Load:** read the hidden textarea's server-rendered HTML →
  `$generateNodesFromDOM(editor, new DOMParser().parseFromString(html,'text/html'))`
  → set editor state. Empty/whitespace → empty paragraph.
- **Serialize:** `editor.registerUpdateListener` → `$generateHtmlFromNodes(editor)`
  → write into the hidden `<textarea name="…">` (and the source view when open).
  Same continuous contract as today; the Django form POST is unchanged.
- Handled HTML vocabulary: `p, h2, h3, strong/b, em/i, s, code, pre, ul, ol, li,
  blockquote, a, img, hr`. Standard Lexical nodes cover all but `img`/`hr`
  (custom nodes).
- **Legacy Markdown:** the **product** form pre-converts Markdown→HTML at read
  time via `admin_dashboard/forms/_helpers.py:_ensure_html()` before the value
  reaches the tag, so the editor always receives HTML. The **CMS** `Page.body`
  is stored as HTML-or-Markdown and the editor treats the stored value as HTML —
  identical to TipTap's behaviour today (`content: hidden.value`), so this is
  **not a regression**; converting any residual raw-Markdown CMS bodies is out
  of scope for this change.

### The widget (template tag)
`richtext/templatetags/richtext.py` → `{% richtext_field %}` inclusion tag
rendering `templates/richtext/_field.html`:

```django
{% load richtext %}
{% richtext_field name="description" value=form.description.value id="description"
   allow_headings=True allow_images=False
   expose_as="morphProductDescriptionEditor" aria_label="Product description" %}
```

Renders the existing `.rte` structure (identical toolbar markup + CSS so the UI
is visually unchanged): a `[data-richtext]` wrapper with the `data-*` options, a
`data-rte-mount` content div, a hidden `.rte-source` textarea (HTML source
toggle), and the real hidden `<textarea name="…">{{ value }}`.

**Toolbar → Lexical command map:** bold/italic/strike/code → `FORMAT_TEXT_COMMAND`;
h2/h3/paragraph → `$setBlocksType($createHeadingNode/$createParagraphNode)`;
bullet/ordered list → `INSERT_UNORDERED_LIST_COMMAND`/`INSERT_ORDERED_LIST_COMMAND`;
blockquote → `$setBlocksType($createQuoteNode)`; codeBlock → code node; hr →
insert HorizontalRuleNode; link → `window.prompt` + `TOGGLE_LINK_COMMAND`; unlink
→ `TOGGLE_LINK_COMMAND(null)`; image (CMS only) → upload-then-insert ImageNode;
source → swap the contenteditable for a raw `<textarea>` (round-trip via
generate/parse); undo/redo → `UNDO_COMMAND`/`REDO_COMMAND`; clear → clear format.
Button active-state via `registerUpdateListener` reading the selection.

### Disable-safety
The tag calls `app_registry.is_active('richtext')`: active → full editor
markup (the bundle enhances it); inactive → a plain `<textarea name="…">`. The
bundle only loads/scans when the plugin is active, so a disabled plugin degrades
to a working textarea — the swappable property. (Plugins stay in
`INSTALLED_APPS` when runtime-disabled, so `{% load richtext %}` never breaks.)

### Asset loading + htmx
`base.html` loads the bundle + css **once**, guarded by
`{% plugin_enabled "richtext" %}`, and calls `MorphRichText.scan()` inside the
existing `htmx:afterSwap` handler (next to `lucide.createIcons()` /
`Morph.reinit`). The `.rte*` CSS block moves out of `base.html` into
`static/richtext/editor.css`.

### CSP
`core/security_headers.py`: remove `https://esm.sh` from dashboard `script-src`
and `connect-src`. Keep `'unsafe-eval'`; rewrite the comment to name Tailwind
Play CDN as the sole remaining owner and reference the precompile-Tailwind
follow-up. Update the `dashboard-csp-unsafe-eval` memory note accordingly.

## Files

**New (plugin):** `__init__.py`, `apps.py`, `app.py`,
`templatetags/{__init__.py,richtext.py}`, `templates/richtext/_field.html`,
`frontend/{editor.js,package.json,README.md}`,
`static/richtext/{lexical-editor.bundle.js,editor.css}`,
`tests/__init__.py`, `.gitignore` (frontend/node_modules).

**Modified:** `product_form.html` (2 fields → tag; AI-draft script → `.setHTML()`),
`cms/templates/cms/dashboard/page_form.html` (body → tag, `allow_images=True`),
`admin_dashboard/.../base.html` (drop `.rte` CSS; guarded bundle load; scan in
afterSwap), `core/security_headers.py`, `morph/settings.py`
(`MORPHEUS_DEFAULT_APPS`), the CSP memory note, and docs (`CLAUDE.md` landmine
if wording changes).

## Testing

- **Django unit:** `{% richtext_field %}` renders the wrapper + correct
  `data-*` attrs; renders a plain `<textarea>` when the plugin is inactive;
  plugin manifest/contract valid; both forms still POST `description` / `body`
  as HTML (existing product/CMS form tests stay green).
- **Playwright browser smoke** (real functional gate — the editor is JS):
  1. product form: type → hidden textarea receives HTML → submit round-trips;
  2. load a product with existing HTML → renders in the editor;
  3. CMS form: image upload inserts `<img loading="lazy">`;
  4. AI-draft button → `setHTML` populates the editor;
  5. dashboard page load → **no CSP violations** in the console after esm.sh is
     dropped.
- **Build reproducibility:** `frontend/README.md` documents the exact esbuild
  command; the committed bundle is the source of truth for deploy.

## Risks & mitigations

1. **Coolify deploy has no Node** → bundle pre-built + committed. Design-level
   mitigation.
2. **Vanilla Lexical lacks image/hr nodes** → two small custom nodes, contained
   in `editor.js`.
3. **HTML round-trip fidelity** → standard nodes + custom img/hr cover the full
   vocabulary; legacy Markdown pre-converted by `_ensure_html`.
4. **First build step in repo** → isolated to `frontend/`, `node_modules`
   gitignored, artifact committed; no other file gains a build dependency.
5. **`unsafe-eval` not fully dropped** → Tailwind still owns it; documented
   follow-up (precompile Tailwind). This change is honest about the partial win.
6. **Two duplicated TipTap templates** → both cut in one change (blast radius is
   2 files); no long-lived dual-editor state.

## Rollout

Hard-cut both templates together behind the new plugin. Ship, then smoke the
product form + CMS page form on prod (editor loads, types, saves, round-trips;
console clean). The precompile-Tailwind / drop-`unsafe-eval` follow-up is
tracked separately.
