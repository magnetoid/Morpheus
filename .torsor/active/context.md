---
type: active-context
status: active
tags: [active]
---

# Active Context

## Current focus
Live-testing dotbooks.store end-to-end (storefront + dashboard) and fixing bugs
as they surface, then hardening the platform toward the goal: enterprise-grade,
AI-first commerce. torsor-helper was just installed/seeded — restart the next
session so its MCP server loads.

## Recent changes
- **Asset library:** click→SEO modal + download buttons; fixed a tile-404; the
  panel now federates `ProductVariant.digital_file` (18 book PDFs that were
  invisible now show under Assets→PDFs, verified `PDF_VIEW_COUNT: 18`); a stray
  `.txt` no longer leaks into the PDFs tab; doc-tab counts corrected.
- **SEO:** no-code JSON-LD emission toggles (Organization/WebSite/Product/
  Reviews); Product `image` is now Google's multi-image array; `optimize_images`
  batch warmer + optimize-on-upload (WebP); 2 stale tests fixed; AMP web stories
  made self-canonical (resolves the GSC `amp-story canonical error`).
- **Lumina (`/create/`):** fixed dead `#features` anchor + pointed primary CTAs
  at the creator app.
- **Storefront:** keyboard skip-to-content (a11y).
- **Prod data:** `marko.tiosavljevic@gmail.com` is now an approved affiliate
  (`/markotiosavljevic`) + a vendor; COD + Test gateways enabled. New reusable
  `manage.py grant_demo_access` command.

## Open questions
- **Image-optimization dashboard button** (async Celery + progress) is the one
  feature still open — see `docs/plans/image-optimization.md`.
- **Disable the Test payment gateway** in Settings → Payments after testing (it
  lets anyone place free orders on the live store).
- Architectural debt that fails the disable test: loyalty's `/account/points/`
  + payments' settings view (see `CLAUDE.md`). CMS Phase 3: migrate hardcoded
  About/Shipping/Returns into editable pages.
