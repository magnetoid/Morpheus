# Migrating between Morpheus versions

One section per release that breaks something an integrator depends on, newest
first. If a version isn't listed, it shipped no breaking change to a surface in
[`docs/API_STABILITY.md`](API_STABILITY.md).

---

## v0.46.0 — the `<head>` is rendered by one core tag

**Who this affects:** anyone maintaining a **theme** outside this repo, and any
app that emitted `<head>` markup of its own. Merchants, the storefront, the
REST/GraphQL/MCP surfaces and webhook payloads are unaffected.

### What changed

SEO markup used to be the theme's job: `base.html` called `{% seo_meta %}`, page
templates called `{% seo_product_jsonld %}`, `{% seo_breadcrumb_jsonld %}` and
two dozen siblings, and every one of them wrote HTML directly. A theme that
skipped a call silently shipped a page with no canonical; a theme and a page
that both made one shipped duplicates (the product page really did emit two
`og:type` tags).

Now core builds a **head document** and fires `STOREFRONT_HEAD`; the seo app
fills it in. Themes call one tag:

```django
{% load morph %}
{% block seo %}{% storefront_head %}{% endblock %}
```

and declare `head_contract = 1` on their theme class.

### Do I have to change anything?

**Not immediately.** The old tags still work. On a page that has called
`{% storefront_head %}` they render nothing (so a half-migrated theme cannot
double-emit); on a page that has not, they behave exactly as before.

They are **deprecated** and will be removed in a later release. To migrate:

1. Replace the `{% seo_meta … %}` call in `base.html` with `{% storefront_head %}`.
   Pass your fallback copy as `title=` / `description=` if your home page needs it.
2. Delete every other `{% seo_*_jsonld %}`, `{% seo_*_og %}`,
   `{% seo_verification_metas %}`, `{% seo_llms_link %}`, `{% seo_hreflang %}`,
   `{% seo_pagination_links %}` and `{% seo_preconnect %}` call from your templates —
   all of that is in the document now.
3. Delete per-page `{% block seo %}` overrides that existed only to set
   `robots="noindex, …"`. Indexability is decided per page kind (cart, checkout,
   account and internal search are handled for you).
4. Remove any hardcoded shop name from titles: the brand comes from
   Settings → SEO / Settings → General and is applied at render.
5. Set `head_contract = 1` and run `manage.py test themes.test_head_contract`.

Tags that are NOT deprecated: `{% seo_title %}` (a string helper),
`{% seo_responsive_image %}`, `{% seo_meta_panel %}` (dashboard), and
`{% seo_ai_answer_block %}` (page body, not head).

### Two behaviour changes worth knowing

- **`robots.txt`, `sitemap*.xml`, `llms.txt`, `agents.md`, the feeds and
  `/.well-known/security.txt` are no longer language-prefixed.** On a
  multi-language store they used to resolve at `/fr/robots.txt` as well, which
  published a second copy of every discovery file per language. Only the
  unprefixed URLs answer now.
- **The IndexNow key file** is served at `/<key>.txt` only for a key matching
  the protocol's hex shape. The previous catch-all pattern shadowed any other
  root-level `.txt` route.

---

## v0.42.0 — "apps", not "plugins"

**Who this affects:** anyone maintaining an app (plugin) outside this
repository, or tooling that imports the registry. **Nobody else.** If your only
Morpheus code lives in `plugins/installed/` in this repo, it was migrated for
you — every one of the 108 shipped apps was updated in the same commit.

**Who this does not affect:** merchants, the storefront, the REST/GraphQL/MCP
surfaces, webhook payloads, and `MorpheusEvents.*` hook constants. No STABLE
surface from `API_STABILITY.md` changed. Your `.env` does not need editing.

### What changed

| Before | After |
|---|---|
| `plugins/installed/<name>/plugin.py` | `plugins/installed/<name>/app.py` |
| `from morpheus.plugin import Plugin, StorefrontBlock, …` | `from morpheus.app import Plugin, StorefrontBlock, …` |
| `from plugins.registry import plugin_registry` | `from plugins.registry import app_registry` |
| `PluginRegistry` | `AppRegistry` |
| `settings.MORPHEUS_DEFAULT_PLUGINS` | `settings.MORPHEUS_DEFAULT_APPS` |
| `settings.MORPHEUS_EXTRA_PLUGINS` | `settings.MORPHEUS_EXTRA_APPS` |
| `settings.MORPHEUS_PLUGINS_DIR` | `settings.MORPHEUS_APPS_DIR` |

**Deliberately unchanged** — these are not oversights:

- the directory `plugins/installed/<name>/`
- the base class `MorpheusPlugin` (still exported as `Plugin`)
- the `MORPHEUS_EXTRA_PLUGINS` **environment variable**, which is still read as
  a fallback. It lives in your deployment environment, not the repo, so
  renaming only the code would have silently dropped a live deployment's extra
  apps with no error anywhere. Set `MORPHEUS_EXTRA_APPS` when convenient; the
  old name keeps working.

### Find every reference in your codebase

```bash
grep -rnE 'morpheus\.plugin\b|\bplugin_registry\b|\bPluginRegistry\b|MORPHEUS_(DEFAULT|EXTRA)_PLUGINS|MORPHEUS_PLUGINS_DIR' \
  --include='*.py' --include='*.html' --include='*.md' .

# and the manifest filename itself
find . -name 'plugin.py' -path '*/plugins/installed/*'
```

### Apply the rename

```bash
# 1. the manifest file
for f in path/to/your/apps/*/plugin.py; do git mv "$f" "${f%plugin.py}app.py"; done

# 2. the symbols  (\b after 'plugin' protects the 'morpheus.plugins' logger name)
grep -rlE 'morpheus\.plugin\b|\bplugin_registry\b|\bPluginRegistry\b|MORPHEUS_(DEFAULT|EXTRA)_PLUGINS|MORPHEUS_PLUGINS_DIR' \
  --include='*.py' --include='*.html' . \
| xargs perl -pi -e '
    s/\bmorpheus\.plugin\b/morpheus.app/g;
    s/\bplugin_registry\b/app_registry/g;
    s/\bPluginRegistry\b/AppRegistry/g;
    s/\bMORPHEUS_DEFAULT_PLUGINS\b/MORPHEUS_DEFAULT_APPS/g;
    s/\bMORPHEUS_EXTRA_PLUGINS\b/MORPHEUS_EXTRA_APPS/g;
    s/\bMORPHEUS_PLUGINS_DIR\b/MORPHEUS_APPS_DIR/g;
  '
```

### Verify

```bash
python manage.py check          # every app must still be discovered
python manage.py morph_versions # your app must appear with its version
```

A missed manifest rename fails **silently**: the registry simply doesn't find
the app, so it vanishes from the catalogue instead of raising. Check the count
in the boot log (`Plugin system ready: N active`) against what you expect.

### New in the same release

Two optional manifest fields — see
[`docs/PLUGIN_DEVELOPMENT.md`](PLUGIN_DEVELOPMENT.md#4-metadata-reference):

- `protected = True` — no surface offers a disable (merchant toggle *and* AI
  tools both refuse). One-way: a manifest can add protection, never remove it.
- `system = True` — hide the app from the Apps catalogue.
