---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-04T00:27:04'
updated: '2026-06-04T00:27:04'
rules: []
supersedes: 0002-image-optimization-controls-live-on-the-seo-dashboard-run-via-celery
---

# ADR 0005: Caching page is the single home for image-optimization + edge/cache controls

## Context
ADR 0002 placed the "Optimize existing images" button on the SEO settings page because, at the time, "there is no dedicated caching settings page." That premise no longer holds: /dashboard/settings/caching/ (admin_dashboard.views_split.settings.settings_caching) is now a rich page aggregating cache health, storefront edge/HTML Cache-Control, image flags, compression, critical-path, route TTLs, warmup, and a Cloudflare summary. The user's original request was an optimize button "in the caching settings dashboard." Keeping it on SEO now splits image-performance settings across two pages.

## Decision
Make the Caching page the single home for image-optimization and edge/cache controls. Move the "Optimize existing images" button + last-run status from the SEO settings page to the Caching page (action=optimize_images enqueues seo.optimize_images_task, fail-soft when the broker is down; status read from cache key seo:image_optimize:status). The SEO page keeps only a pointer link. The image-variant PIPELINE (generate_image_variant, optimize_images_task) stays owned by the seo plugin — only the trigger UI relocates, so there is no cross-plugin model coupling. Cloudflare cache-relevant controls (cache_level, browser_cache_ttl, brotli, early_hints, polish, mirage, tiered cache, cache reserve, argo) + purge are also surfaced/edited on the Caching page via the existing cloudflare.services functions; CF DNS/firewall/analytics stay on /dashboard/cloudflare/.

## Consequences
Image optimization is discoverable on the Caching page next to the WebP/lazy-load flags it pairs with. The admin_dashboard caching view calls into seo.tasks and cloudflare.services by name — both guarded fail-soft so a disabled seo/cloudflare plugin or a dead broker/bad CF token never 500s the page. To honour ADR 0003 (no duplicate settings surfaces), the caching-relevant CF settings are removed from cloudflare zone_detail (which keeps security/TLS/DNS/firewall). Pre-req fix shipped alongside: settings_caching's POST path 500'd because HttpResponseRedirect was not in scope (commit 386d3e9).
