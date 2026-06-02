# Image optimization — caching dashboard (instant + backfill)

**Ask (2026-06-02):** *"in caching settings dashboard there should be instant
image conversion and optimization and optimize old images also, compliant with
SEO best practices."*

This is a real multi-part build that touches the **upload pipeline + media
storage**, so it is scoped here for a focused session rather than rushed.

## What already exists (don't rebuild)

- **On-the-fly WebP/AVIF variants.** `seo/services/images.py:generate_image_variant()`
  resizes (LANCZOS) + encodes WebP (q80) / AVIF (q68), idempotent. Served at
  `/img/<fmt>/<width>/<path>` (`seo/urls.py` → `views.image_variant`) and emitted
  by `{% seo_responsive_image %}` (responsive `srcset` + lazy + priority +
  view-transition). **SEO best practices at render time are already handled.**
- **ProductImage WebP on save.** `catalog/models.py` `ProductImage.save()`
  (~L438) populates `products/webp/<name>.webp`; a `post_delete` signal (~L486)
  cleans up `image` + `webp_image`.
- **Performance / caching settings page** (storefront plugin) drives the
  `{% caching_* %}` tags (`storefront/templatetags/caching.py`) + `warmup_cache`
  management command — resource hints, font preload, service worker, LCP preload,
  `loading`/`defer` attrs.

## The gaps to close

1. **MediaAsset uploads are NOT optimized.** `media/models.py:MediaAsset.from_upload()`
   reads dimensions only — no WebP generation, no downscale of huge originals, no
   EXIF strip. Add opt-in optimization here (respect the settings below).
2. **No batch job for existing images.** Nothing (re)optimizes the back-catalog.
3. **No image controls on the caching/performance settings page.**

## Build plan (one focused session)

1. **Settings — image section on the performance/caching page.** Toggles + knobs:
   `optimize_on_upload` (bool), `formats` (webp / webp+avif), `webp_quality`,
   `avif_quality`, `max_dimension` (downscale originals beyond N px). Store in the
   storefront plugin config (no migration) — mirror how the other caching toggles
   persist. Surface in that page's template.

2. **Instant optimization on upload.**
   - `MediaAsset.from_upload()`: when image + `optimize_on_upload`, generate a
     sibling WebP (and AVIF if enabled), downscale originals past `max_dimension`,
     strip EXIF. **Never destroy the original** — only add/auxiliary-encode.
     Reuse `seo.services.images` encoders (cross-plugin via service import, not a
     model import — keep the contract).
   - Verify `ProductImage.save()` honours the same quality/format knobs.

3. **Batch "optimize old images".** A management command
   `media/management/commands/optimize_images.py` iterating `MediaAsset` (images)
   + `catalog.ProductImage`: (re)generate variants, optionally downscale oversized
   originals. **Idempotent**, `--dry-run`, `--limit`, `--since`. Wrap in a Celery
   task and add a **"Optimize existing images" button** on the caching page that
   enqueues it (non-blocking) + reports progress (count done / total / bytes saved).

4. **SEO compliance checks.** Alt text already has `catalog/backfill_alt_text`;
   responsive `srcset` + lazy + dimensions already via `seo_responsive_image`.
   The batch job should *report* images missing alt text (link to the asset SEO
   modal shipped in `media`).

## Risks / why a fresh session

- Touches the **upload path** and **media storage** — a bug here corrupts or
  bloats stored assets. Re-compression of originals must be **opt-in + lossless to
  the original file** (add variants; never overwrite the source).
- Storage growth (webp + avif per image) — surface estimated added bytes before a
  bulk run.
- Needs real Pillow + AVIF plugin (`pillow-avif-plugin`) verification in the
  prod image (the encoders already assume it; confirm it's installed before the
  batch run advertises AVIF).

## Verify

- Upload an image in the asset library → a `.webp` sibling appears; original
  intact; `/img/webp/600/<path>` 200s.
- `manage.py optimize_images --dry-run` lists the back-catalog with no writes;
  without `--dry-run` it backfills idempotently (second run = 0 changes).
- Caching page button enqueues the task; progress reported; no request blocks.
