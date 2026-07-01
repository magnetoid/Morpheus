---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-01T01:47:54'
updated: '2026-07-01T01:47:54'
rules:
- id: i18n-patterns-storefront-only
  rule: i18n_patterns must wrap only storefront (prefix='') plugin URLs; dashboard/,
    api/, payments/, auth/, admin/ stay unprefixed.
---

# ADR 0022: Storefront language routing via i18n_patterns on prefix='' URLs only

## Context
Phase 1b of full localization (docs/plans/full-localization-2026-06.md). The core language (Settings → General `core_language`, default 'en') must be served UNPREFIXED (/product); other enabled languages get a URL prefix (/fr/, /sr/). morph/urls.py mounts `path('', include('plugins.urls'))` where plugins.urls = plugin_registry.get_urlpatterns(), an aggregate of storefront (prefix='') + dashboard (prefix='dashboard/') + api (prefix='api/') + payments. i18n_patterns must wrap ONLY the storefront, never dashboard/api/auth.

## Decision
Partition plugin URL entries by prefix: entries with prefix=='' are the storefront and get wrapped in django.conf.urls.i18n.i18n_patterns(prefix_default_language=False); every entry with an explicit prefix (dashboard/, dashboard/seo/, api/, payments/) plus the core routes (healthz, dashboard/assistant, errors, api/graphql, auth, admin) stay UNPREFIXED. Add LocaleMiddleware after SessionMiddleware, before CommonMiddleware. LANGUAGES = static supported-language list; LANGUAGE_CODE from env MORPHEUS_CORE_LANGUAGE (default 'en') — changing the core language to a non-default needs that env + redeploy. Verify via Django test-client resolve() of /, /fr/, /dashboard/, /api/graphql/ (no browser needed).

## Consequences
prefix_default_language=False keeps every existing unprefixed URL working (core language) — only /xx/ variants are added, so it's backward-compatible. Crawler files (sitemap.xml, robots.txt) and webhooks at prefix='' keep their canonical unprefixed path for the core language; harmless /xx/ variants also resolve. The DB core_language picker is the merchant's intent but LANGUAGE_CODE is import-time, so a non-'en' core language requires the env var to actually be unprefixed.
