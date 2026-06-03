# Caching settings unification (dashboard > settings > Caching)

> Make `/dashboard/settings/caching/` the single home for all caching /
> edge / image-performance settings. Decided 2026-06 with the user.

## Decisions (user-confirmed)
1. **Cloudflare scope = cache controls only.** Surface + edit CF's
   caching-relevant settings on the Caching page (cache_level,
   browser_cache_ttl, Brotli, early_hints, Polish/Mirage image-opt, Tiered
   Cache, Cache Reserve, Argo) + a purge control. DNS / firewall/WAF /
   analytics stay on the dedicated Cloudflare page (`/dashboard/cloudflare/`).
2. **Image optimization → moves onto Caching.** The SEO "Optimize images"
   button + last-run status move from `/dashboard/seo/settings/` to the
   Caching page's image section. **Supersedes ADR 0002** → record ADR 0005.
3. **Approach = extend the existing `settings_caching` view** (pragmatic;
   admin_dashboard keeps the rich custom view). Not the contributed-panel
   refactor.

## Where things live today (the map)
- Caching view: `plugins/installed/admin_dashboard/views_split/settings.py:228`
  `settings_caching()` → `admin_dashboard/settings_caching.html`. Already
  renders cache health, Redis stats, storefront HTML/edge TTLs, image flags
  (lazy/webp/preload/srcset), hints, PWA, compression, critical-path, route
  TTLs, warmup, and a **read-only** CF zone summary (`cf_zones`).
- CF services (reuse): `plugins/installed/cloudflare/services.py` —
  `zone_settings_map(zone)`, `patch_zone_setting(zone, id, value)`,
  `_client_for(zone)` (patch_tiered_cache / patch_cache_reserve /
  patch_argo_smart_routing + get_*), `purge_everything(zone, ...)`.
- CF per-zone editor today: `cloudflare/views.py:172 zone_detail` — has the
  full `notable_settings` list (mixes caching + security/TLS).
- SEO image-opt (reuse): `seo/views.py:539 seo_settings_page` action
  `optimize_images` → `seo/tasks.py optimize_images_task.delay(avif=)` +
  `last_image_optimize_status()` (cache key `seo:image_optimize:status`).

## Phases (each shippable + verifiable)

### Phase 1 — Image optimization onto Caching (+ ADR 0005)
- Add an `action=optimize_images` branch to `settings_caching` POST: enqueue
  `optimize_images_task.delay(avif=...)`, fail-soft if the broker is down.
- Add `image_optimize_status` (+ avif toggle) to the view context and render
  an "Optimize images now" button + last-run status in the image section of
  `settings_caching.html`.
- Remove the `optimize_images` action + button + status from
  `seo_settings_page` / `seo/settings.html`; leave a one-line pointer to the
  Caching page (don't break the SEO page).
- Record `docs/.../decisions/0005-*` superseding ADR 0002; update ADR 0002's
  status to "Superseded by 0005".
- **Verify:** Caching page shows the button + status; POST enqueues the task
  (mock/patch in test); SEO page no longer has it. `manage.py test`.

### Phase 2 — Cloudflare cache controls on Caching
- Curated **caching-only** CF setting list (module-level const, shared):
  cache_level, browser_cache_ttl, brotli, early_hints, polish, mirage. Plus
  the three endpoint toggles (tiered cache, cache reserve, argo).
- In `settings_caching` GET: for each zone in `cf_zones`, read
  `zone_settings_map(zone)` (fail-soft) and the three toggle states; build
  rows. In POST: `action=cf_patch_setting` → `patch_zone_setting`;
  `action=cf_toggle_*` → `_client_for(...).patch_*`; `action=cf_purge_all` →
  `purge_everything(zone, triggered_by=request.user)`.
- Template: turn the read-only CF section into editable cache controls +
  per-zone "Purge everything". Degrade gracefully when CF plugin is
  disabled/absent (imports already try/excepted) and on API errors.
- **Single-home / ADR 0003:** trim `cloudflare/views.py zone_detail`
  `notable_settings` to the **non-caching** subset (security_level,
  min_tls_version, https, hotlink, email_obfuscation, etc.); the caching
  subset now lives only on the Caching page. Add a pointer link.
- **Verify:** Caching page lists editable CF cache settings + purge for a
  zone; zone_detail no longer shows the caching subset; both degrade on a bad
  token. Tests with a patched CF client.

### Phase 3 — docs + tests
- `docs/ARCHITECTURE.md` / settings docs note: Caching is the single home for
  edge/image-perf settings; CF cache controls + image-opt live there.
- Tests in `admin_dashboard/tests/` for the new POST actions (image-opt
  enqueue, CF patch/purge dispatch with a mocked client).
- Update `.torsor` active context.

## Landmines / rules
- CF calls are live-API + per-zone — every read/write stays fail-soft (a busted
  token must never 500 the Caching page; it already try/excepts).
- Don't duplicate CF cache controls on two pages — moving them to Caching means
  removing them from zone_detail (ADR 0003 no-duplicate-surface).
- If the cloudflare plugin is disabled, the CF section must vanish, not error.
- Image-opt task enqueue must fail-soft when the Celery broker is down.

## Status log
- 2026-06: plan written; decisions captured. Implementation starting Phase 1.
