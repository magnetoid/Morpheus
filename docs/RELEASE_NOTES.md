# Morpheus OS — Release Notes

Detailed, user-facing updates to the **Morpheus OS core** and its modules,
surfaced in **Dashboard → Settings → Version & updates**.

> **House rule (enforced):** every Morpheus OS version bump MUST add a dated,
> versioned `## vX.Y.Z — YYYY-MM-DD` entry here describing the change. This file
> is the single source of truth for the in-dashboard changelog. See
> [`CLAUDE.md`](../CLAUDE.md) and the torsor ADR "Versioned release notes".

---

## v0.2.3 — 2026-06-21

### Plugins
- **Fixed:** the *Version & updates* page rendered blank in production — it
  depended on a markdown library that isn't installed there. Replaced with a
  small built-in renderer (no external dependency), so the release notes now
  show. (If this page was empty for you, that's why.)
- Settings nav: **Morpheus Brain** and **Version & updates** are now pinned
  right under **General** instead of buried at the bottom of the settings list.

---

## v0.2.2 — 2026-06-21

### Core
- Plugin contract gains `enabled_by_default` — a plugin can ship
  **installed-but-OFF**, opting in from Dashboard → Apps (default stays on, so
  existing plugins are unchanged).

### Plugins
- **Booking marketplace** (new, **off by default**): a multivendor *services*
  marketplace alongside the product one. Vendors offer time-slot
  `BookableService`s with weekly availability; customers book a slot at
  `/bookings/`. Manage at Dashboard → Bookings. Enable it from Dashboard → Apps.

---

## v0.2.1 — 2026-06-21

### Storefront
- Author page: the author image now spans the full content width instead of a
  cramped 160px thumbnail.

---

## v0.2.0 — 2026-06-20

### Core
- **Morpheus Brain** is now a **core capability** (`core/brain/`), not an app —
  always on (the surface plugin is protected from disable). It continuously
  reads the platform's own signals (code-quality + error-log findings from the
  self-improvement immune system, plugin health, SEO/content audits, storefront
  Core Web Vitals) and uses your **configured AI provider** to synthesize a
  prioritized list of fixes, improvements, and feature ideas. Refreshes on a
  6-hour beat and on demand; degrades cleanly when no AI is configured.
- **More comprehensive error/warning logging** — `django.request`,
  `django.security`, `django.db.backends`, `celery`, and Python `warnings` now
  flow through the log stream the error-log collector + Brain read.

### Plugins
- **Morpheus Brain** surface (Settings → Morpheus Brain): tabbed console for the
  above (Overview, Plugins, Code, Errors, Content & SEO, Storefront,
  Improvements) with a one-click **Refresh analysis**.

---

## v0.1.0 — 2026-06-20

The current foundation release. Highlights since the platform came together:

### SEO & structured data (rich results)
- **One complete, valid Product** rich result per product page — offer with
  price, availability, shipping, return policy, `itemCondition`, and
  `priceValidUntil`, plus absolute `image`, `brand`, and review stars
  (`aggregateRating` + `review`) when reviews exist.
- **Google Book structured data** — Work → Edition → ReadAction, with `sameAs`
  (Open Library) + OCLC identifier so public-domain titles are reconcilable
  without fabricated ISBNs.
- **VideoObject** for product videos, and an enriched **Organization** graph
  (contact point + postal address) for the brand knowledge panel.
- **Rich-snippets editor** gained Book + enriched Article types.
- Fixed the AMP Web Story canonical error (stories are now standalone /
  self-canonical).

### Catalog & books
- **Identifier fields** (ISBN-13 / OCLC / Open Library work ID) on the product
  edit form, plus a bulk `backfill_book_identifiers` command that reconciles the
  catalog against Open Library with conservative title+author matching.

### Storefront
- Editorial homepage hero, bigger grid titles with first-sentence excerpts.

### Platform
- **Version & updates** page in Settings (this page), backed by this document.
- **Morpheus Brain** (Settings → Morpheus Brain) — a tabbed intelligence console
  that aggregates plugin health, code analysis & self-improvement, content &
  SEO, storefront Core Web Vitals, and improvement recommendations, read-only
  from the platform's own engines.
- **Book identifiers** — ISBN-13 / OCLC / Open Library fields on the product
  form, plus the `backfill_book_identifiers` bulk reconciliation command.

_Earlier engineering history (PR-level) lives in [`CHANGELOG.md`](../CHANGELOG.md)._
