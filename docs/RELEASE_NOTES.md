# Morpheus OS — Release Notes

Detailed, user-facing updates to the **Morpheus OS core** and its modules,
surfaced in **Dashboard → Settings → Version & updates**.

> **House rule (enforced):** every Morpheus OS version bump MUST add a dated,
> versioned `## vX.Y.Z — YYYY-MM-DD` entry here describing the change. This file
> is the single source of truth for the in-dashboard changelog. See
> [`CLAUDE.md`](../CLAUDE.md) and the torsor ADR "Versioned release notes".

---

## v0.2.7 — 2026-06-24

### Security
- **Staff two-factor authentication (MFA).** New `staff_mfa` plugin adds a TOTP
  second factor (authenticator apps — Google Authenticator, 1Password, Authy)
  on top of the existing email sign-in code for staff accounts. Self-service
  enrollment lives at **Settings → Two-factor authentication** (scan a QR,
  confirm a code, save one-time recovery codes). Lost your device? A recovery
  code gets you in; an admin can run `python manage.py reset_mfa <email>` as a
  break-glass (audited). **Enrolled** staff are always challenged at sign-in.
  Enforcement for *un*enrolled staff is **opt-in**: turn on **Require MFA for all
  staff** in **Settings → Developer → Staff two-factor** to prompt them to enroll
  at sign-in (a first-admin grace prevents locking the org out before anyone has
  enrolled; hard per-page gating lands in a follow-up). Email-OTP stays factor
  one and is unchanged; disabling the plugin reverts sign-in to single-factor
  exactly. Customers are unaffected.

---

## v0.2.6 — 2026-06-21

### Plugins
- **Linda now reports the real product count.** Her `products.search` tool
  returned `count = page size` (capped at 20–50), so she'd say "there are ~40
  books" for an 859-product catalogue. It now returns `total` (the true number
  of matching products) alongside the sample, and a new **`products.count`** tool
  answers "how many products/books" exactly. Linda's prompt points at it.
- Retired the PDP **"Pairs with this / Goes well together"** recommendation block
  (cropped book covers; only rendered for the few products with co-purchase
  data). The recommendation service stays available for reuse.

---

## v0.2.5 — 2026-06-21

### Core
- **Morpheus Brain now actually sees application errors.** A fail-soft, loop-safe
  logging handler routes ERROR-level app logs into the error pipeline
  (`ErrorEvent` → error_log collector → `SiSignal`), so the Brain's **Errors tab**
  and AI analysis reflect real exceptions — completing the "analyze error logs"
  capability (previously those logs only hit the console).
- **Brain correctness fixes:** merchant insights are now fed to the AI digest
  (they were gathered + shown but never sent to the model); a transient AI-provider
  failure no longer pins a stale error banner for 24h (only successful analyses are
  cached); and the signal snapshot is cached ~90s (was ~18 DB queries on every page
  load), refreshed on demand when you click *Refresh analysis*.

---

## v0.2.4 — 2026-06-21

### Core
- **Fixed: CSP violation flood (~2,500/day).** The storefront Content-Security-
  Policy (report-only) didn't allow `cdn.ampproject.org`, which the webstories
  plugin's `<amp-story-player>` PDP embed loads (amp-story-player + amp-loader +
  v0). Added it to `script-src`/`style-src`, silencing the reports. (Report-only,
  so nothing was broken — just noise the self-improvement engine kept flagging.)
- **Fixed: false plugin-validation error on every boot.** `validate()` checked a
  plugin's `requires` only against other plugin names, so a `core.*` dependency
  (e.g. `ai_stylist` → `core.audit`) wrongly logged "not installed" even though
  the core app is always present. `core.*` deps now resolve against
  `INSTALLED_APPS`; the `ai_stylist`/`core.audit` boot error is gone.

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
