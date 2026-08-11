# Migrating between Morpheus versions

One section per release that breaks something an integrator depends on, newest
first. If a version isn't listed, it shipped no breaking change to a surface in
[`docs/API_STABILITY.md`](API_STABILITY.md).

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
