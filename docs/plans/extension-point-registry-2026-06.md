# Extension-Point Registry — Dashboard Nav Taxonomy

> Spec for the Phase 3 IA collapse described in
> [dashboard-audit-2026-06.md](dashboard-audit-2026-06.md). Concrete
> mechanism for ADR 0012 (plugins extend named shared surfaces).

## 1. Project Overview

- **Name:** Extension-Point Registry — dashboard nav-section taxonomy
- **Goal:** Replace the ad-hoc `_SECTION_ORDER` / `_SECTION_LABELS` /
  `_SECTION_ICONS` triple in
  [`plugins/context_processors.py:10–76`](../plugins/context_processors.py)
  with a single authoritative `SECTION_REGISTRY` in `core`; enforce the
  rule that an unknown `section=` value on a `DashboardPage` gracefully
  degrades to the "Apps" catch-all instead of minting a stray top-level
  header.
- **Target users:** platform developers adding plugins; merchant operators
  who experience the nav.
- **Why now:** Audit found ~21 top-level sections (target: ~9 + Apps).
  A plugin using `section='b2b'` currently renders a lone, unrecognised
  header — exactly the problem a governed taxonomy prevents. See
  [dashboard-audit-2026-06.md §D](dashboard-audit-2026-06.md).

## 2. Tech Stack & Dependencies

- **Language:** Python 3.12 / Django 5.x
- **Changed files:** `core/nav.py` (new — the registry); `plugins/context_processors.py`
  (consumer); `plugins/contributions.py` (docstring update on `DashboardPage.section`);
  `admin_dashboard/settings_categories.py` (optional: same pattern for settings categories).
- **No new dependencies.**

## 3. Data Models / Schemas

`SECTION_REGISTRY` is a plain ordered list of `NavSection` dataclasses
defined in `core/nav.py`. Nothing is persisted to the database.

```python
@dataclass(frozen=True)
class NavSection:
    key: str      # machine key; DashboardPage.section must equal this
    label: str    # sidebar header text
    icon: str     # Lucide icon name
    order: int    # sort position; lower renders first
```

**Canonical 9 + Apps entries (ordered):**

| order | key | label | icon |
|-------|-----|-------|------|
| 10 | `home` | Home | `home` |
| 20 | `orders` | Orders | `shopping-cart` |
| 30 | `products` | Products | `package` |
| 40 | `customers` | Customers | `users` |
| 50 | `marketing` | Marketing | `megaphone` |
| 60 | `discounts` | Discounts | `tag` |
| 70 | `content` | Content | `book-open` |
| 80 | `analytics` | Analytics | `bar-chart-3` |
| 90 | `settings` | Settings | `settings` |
| 999 | `apps` | Apps | `grid-3x3` |

The `apps` entry is the perpetual catch-all; its `order=999` keeps it
last. The `settings` entry hosts configuration pages that share the
settings-sidebar rail (nav='settings'). A `DashboardPage` with an
unrecognised or missing `section` value is silently remapped to `apps`
by the resolution function — it never creates a new header key.

## 4. Key Features & Acceptance Criteria

- [ ] **Single source of truth.** `SECTION_REGISTRY` in `core/nav.py`
  is the only place section keys, labels, and icons are defined.
  `context_processors.py` reads it; the three ad-hoc dicts
  (`_SECTION_ORDER`, `_SECTION_LABELS`, `_SECTION_ICONS`) are deleted.
  *Acceptance:* `grep -r "_SECTION_ORDER\|_SECTION_LABELS\|_SECTION_ICONS" plugins/` returns nothing.

- [ ] **Unknown section degrades to Apps — no stray headers.**
  `DashboardPage(section='b2b')` and `DashboardPage(section='')` both
  appear under the "Apps" group in the rendered sidebar.
  *Acceptance:* unit test — `_group_by_section([DashboardPage(section='b2b', ...)])` returns
  exactly one section dict with `key='apps'` and zero other top-level entries.

- [ ] **Known sections render in correct order.**
  *Acceptance:* unit test — a list of pages with sections `['orders', 'products', 'marketing']`
  returns groups in ascending `order` sequence.

- [ ] **New-group path has friction by design.** Adding a 10th top-level
  group requires editing `core/nav.py` plus committing an ADR entry.
  The registry is `frozen=True` dataclasses; no runtime mutability. A
  plugin cannot register a new section at import time.
  *Acceptance:* code review — no public API exists on the registry for
  plugins to append entries.

- [ ] **Plugin needs zero core changes to appear.** A brand-new plugin
  with `section='products'` renders in the Products group on first boot
  with no other changes.
  *Acceptance:* integration smoke — add a test DashboardPage with
  `section='products'`; assert it appears in the Products group.

- [ ] **Disable test stays green.** Toggling a plugin off removes its
  `DashboardPage` contributions and its group disappears if it was the
  only member of that group.
  *Acceptance:* existing disable-test suite passes; no orphan nav entry
  visible when a plugin is disabled.

- [ ] **Migration: 21 sections → 9 + Apps remapped.** Each current
  `section=` value across all plugin `app.py` files is updated to a
  canonical key per the mapping table below.

  | Today | Target |
  |-------|--------|
  | `catalog` | `products` |
  | `sales` | `orders` |
  | `crm` | `customers` |
  | `marketing`, `growth`, `marketplace` | `marketing` |
  | `cms`, `seo` | `content` |
  | `ai` | `settings` (nav='settings') |
  | `developer`, `access`, `data`, `payments` | `settings` (nav='settings') |
  | `b2b`, `taxes`, (unknown) | `apps` (until reassigned) |
  | `analytics` | `analytics` |
  | `plugins` | `apps` |

## 5. Architectural Constraints

- `core/nav.py` must have **no Django imports** — it is imported at module
  load time before Django is fully initialised. Pure Python dataclasses
  only.
- The registry is **immutable at runtime** (`frozen=True`). Plugins cannot
  append to it; that is the governance mechanism.
- Implementing this spec does NOT require rewriting plugin page content,
  view logic, or URL patterns — only `section=` values in `app.py`
  files and the three dicts in `context_processors.py`.
- Conforms to ADR 0010 (tiny core owns extension points), ADR 0011 (one
  agent, specialisation via tools), ADR 0012 (plugins extend named shared
  surfaces). The registry is the concrete artefact ADR 0012 describes.

## 6. Non-Functional Requirements

- **Performance:** the registry is a module-level constant; zero DB
  queries, zero per-request computation beyond a single list iteration.
- **Reliability:** `_group_by_section` must never raise; unknown keys
  fall to `apps` silently — same fail-soft contract as the current
  `context_processors.py` `except Exception` blocks.
- **Accessibility:** no change to rendered HTML structure; icon + label
  contract unchanged.
- **i18n:** `NavSection.label` strings are candidates for `gettext_lazy`
  in a follow-up; not in scope for this spec.

## 7. Security & Privacy

No auth impact. The registry is read-only, server-side, never
user-supplied. Section keys in `DashboardPage` are set by developers at
install time, not by merchants at runtime.

## 8. Observability

- A startup `logger.debug` in `core/nav.py` listing the registered keys
  suffices. No metrics or alerts needed — this is pure config data.

## 9. Out of Scope

- **Rewriting plugin page content or view logic.** Only `section=` values
  and the three dicts change. URL patterns, view functions, templates —
  untouched.
- **Settings-category governance.** `admin_dashboard/settings_categories.py`
  has the same problem (ad-hoc list). Applying the same `NavSection`
  pattern to settings categories is a valid follow-on but is explicitly
  not part of this spec.
- **Other extension points.** The agent `@tool` registry (`core.agents`),
  `core.hooks` event bus, `StorefrontBlock` slots, and `SettingsPanel`
  categories remain unbounded — plugins register as many as they want.
  Only top-level dashboard nav sections are curated here.
- **i18n of section labels.** `gettext_lazy` wrapping is a follow-up.
- **Dynamic section registration by plugins at runtime.** Deliberately
  excluded — that is the scope-creep path this spec closes off.
- **Visibility rules / permissions per section.** RBAC-gating of sections
  is a separate concern owned by the `rbac` plugin.

## 10. Open Questions

None. All decisions are settled per the brief. The only implementation
choice deferred is whether `SettingsCategory` in
`admin_dashboard/settings_categories.py` adopts the same `NavSection`
dataclass (reuse) or stays a local dataclass (isolation) — decide at
implementation time; it has no bearing on this spec's acceptance criteria.

---

## AI Agent Instructions

Read [`plugins/context_processors.py`](../plugins/context_processors.py)
and [`plugins/contributions.py`](../plugins/contributions.py) fully before
writing any code. The three dicts to delete are at lines 10–76 of
`context_processors.py`. Verify every plugin's `section=` value before
remapping — run `grep -rn "section=" plugins/installed/` to get the full
list. Do not touch view logic, URL config, or template files.
