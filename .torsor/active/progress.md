---
type: progress
status: active
tags:
- active
links: []
created: '2026-06-10T03:22:33'
updated: '2026-06-10T03:22:33'
---

# Progress

TipTap: ruled out via evidence — esm.sh modules resolve HTTP 200 with a self-consistent pm@3.23.4/core@3.23.4 graph (deps= pin propagates to transitive extensions, no ProseMirror duplication), dashboard CSP already allows esm.sh in script-src+connect-src, the `color:transparent` CSS is only `.skeleton` loaders, and the HEAD commit (43ee566) only added 3 unrelated extension-point lines. Editor almost certainly initializes; need the exact runtime symptom + browser console to proceed (asked user, interrupted). Audiobooks panel: wiring confirmed correct — audiobooks in MORPHEUS_DEFAULT_PLUGINS (settings.py:111), product_types is a registered SettingsCategory (settings_categories.py:32), _panels_by_category() (views_split/settings.py:19) indexes active plugins' panels by category. Root-cause candidates narrowed to: (a) two-layer enable — panel only registers during activation, gated on PluginConfig.is_enabled=True in DB (registry.py:138-146,199), so a toggled-off plugin loads its app but never registers the panel; or (b) deploy lag — audiobooks SettingsPanel is recent (commit 1acccc3) and may not be on the live dotbooks.store container yet.
