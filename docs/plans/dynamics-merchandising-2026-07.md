# Dynamics Merchandising Takeover — Implementation Plan (2026-07)

> **For agentic workers:** execute task-by-task with the verify step after every task.
> Research: [`docs/analysis/dynamic-merchandising-research-2026-07.md`](../analysis/dynamic-merchandising-research-2026-07.md)
> User directive (2026-07-10): *dynamics controls every product placeholder in
> grids/sliders (except the PDP), ranks by internal analytics + AI purchase
> probability, and gets an extensive dashboard.*

**Ground truth (verified via full codebase map, 2026-07-10):**

- dynamics already has real machinery: 12 strategies + `recommend()` dispatch,
  a nightly purchase-probability scorecard (`calculate_grid_probabilities`,
  weights intent .30 / sales .30 / demand .20 / trend .15 / quality .05 ×
  inventory), a Thompson `BanditArm(product, segment)` reranker (`autopilot`
  strategy), block-level filters/pins/excludes, exploration_rate +
  diversity_cap fields, and a propose-then-approve `MerchandisingProposal`
  queue. What it lacks is **reach** and **explainability**.
- 16 product placeholders exist outside the PDP; the highest-traffic ones
  bypass dynamics: home hero / "New & notable" / staff picks are hard-coded in
  `storefront/views/home.py`; PLP `for_you` ordering calls
  `personalisation.rank_for_visitor` directly; the theme page-builder
  `FeaturedProductsSection` runs its own query; slots `home_after_rails`,
  `checkout_extra`, `order_receipt_extra` are not in dynamics' `_SLOTS`.
- The `rails` plugin is a dead stub (templates with no data provider).

**Design pillars (from the research):** AI ranks by default; merchant overrides
surgically (pin > boost > rule — pins survive re-ranking, personalization never
overrides a pin); the system always explains itself ("why is this product
here"); exploration floor so new products are never entombed; heuristic
transparent scoring, not deep models, at this catalog scale.

---

## Task M1 — Surface takeover: dynamics controls every non-PDP placeholder

**Mechanism (disable-safe by construction):** new filter hook in `core/hooks.py`:

```python
# STOREFRONT_PRODUCTS — filter, value=list[Product] (the view's default pick),
#   kwargs: surface=str, request, limit=int. Fired by storefront views at every
#   product placeholder; the merchandising owner (dynamics) may replace/reorder.
#   No subscriber (dynamics disabled) → the default list stands.
STOREFRONT_PRODUCTS = 'storefront.products'  # filter
```

**Model:** add `surface = CharField(max_length=40, blank=True, db_index=True)`
to `DynamicBlock` (+ migration). A block with `surface` set controls a named
placeholder (its strategy/filters/pins produce the list); `slot` blocks keep
rendering their own carousels as today. `SURFACE_CHOICES` registry:
`home_hero`, `home_featured`, `home_staff_picks`, `plp_default`,
`collection_list`, `tag_list`, `section_featured` (page-builder section).

**Fire sites (each: compute default as today → fire hook → use result):**
- `storefront/views/home.py`: `home_featured` (before hero slice),
  `home_hero` (over the featured result, limit 4), `home_staff_picks`.
- `storefront/views/catalog.py`: the three `sort=='for_you'` reorder sites →
  surfaces `plp_default` / `collection_list` / `tag_list`. Personalisation
  keeps working when dynamics has no block for the surface (the hook
  subscriber returns `value` untouched → existing `rank_for_visitor` path
  already ran / still runs).
- `themes/library/dot_books/sections/__init__.py` `FeaturedProductsSection.render_context`
  → `section_featured`.

**Slots:** add `home_after_rails`, `checkout_extra`, `order_receipt_extra` to
`SLOT_CHOICES` + `_SLOTS` so merchant blocks can target them.

**Subscriber (dynamics/plugin.py ready):** `register_hook(STOREFRONT_PRODUCTS,
placeholders.provide, priority=40)` → looks up the enabled block for
`surface` (first by sort_order), runs `recommend()` with the default list as
fallback candidates, returns default unchanged when no block exists. Pins
first, always.

- [ ] Failing tests: hook fires + block takeover reorders; no-block surface →
      default list identical; disabled-dynamics → hook skipped by the bus
      (ADR 0023 gating) and defaults stand; PDP surfaces untouched.
- [ ] Verify: dynamics + storefront + catalog suites green; template compile;
      boundary guard.
- [ ] Commit: `feat(dynamics): STOREFRONT_PRODUCTS takeover — dynamics controls every non-PDP placeholder`

## Task M2 — `smart` blended strategy + exploration floor + score breakdown

**`smart` strategy** (new default for surface blocks) — transparent weighted
blend, all stdlib, exact-tested:

```
score(p) = 0.50·purchase_probability          (nightly scorecard)
         + 0.20·trend_velocity_norm           (7d views vs prior, normalized)
         + 0.20·session_affinity              (category/author match to THIS
                                               session's views — in-session
                                               personalization, research §4)
         + 0.10·recency_norm                  (newness decay, 90d half-life)
```

**Exploration floor** (research #7): reserve `ceil(exploration_rate · limit)`
positions (default ε=0.10) for under-exposed products — fewest BanditArm
trials, newest first — so the scorecard never entombs new items. Pinned
products always outrank everything (pin > AI). Diversity cap enforced
(existing `diversity_cap`: max share per category).

**Score breakdown** for explainability: `recommend()` gains an optional
`explain=True` returning per-product `{score, components: {probability,
trend, session, recency}, flags: [pinned|explore|diversity_capped]}` — the
data behind the dashboard's "why is this product here" panel (research #5).

- [ ] Failing tests (exact values on fixtures): blend math; session-affinity
      boost from a seeded session; floor guarantees ≥1 explore slot at
      limit=10, ε=0.1; pins always first; diversity cap trims; breakdown keys.
- [ ] Verify: dynamics suite green.
- [ ] Commit: `feat(dynamics): smart blended strategy — probability + trend + session affinity + exploration floor, with explainable scores`

## Task M3 — Merchandising console (extensive dashboard)

Rebuild `/dashboard/dynamics/` from a block table into a **surfaces console**:

1. **Surfaces tab (new index):** every placeholder (SURFACE_CHOICES) + every
   slot, each row showing: controlled-by (block name + strategy, or "theme
   default"), enabled, limit, last probability refresh, preview link. One
   click "Take control" creates a surface block prefilled with `smart`.
2. **Editor upgrades** (existing edit view): surface binding, strategy picker
   incl. `smart`, ε + diversity controls surfaced with plain-language help,
   pinned products via slug list (visual drag = later increment).
3. **Preview + explainability panel:** for any block: render top-N picks with
   per-product score-breakdown bars (probability/trend/session/recency,
   pinned/explore badges) — "why is this product here" (research #5), plus
   **preview-as-segment** selector (reuses `segments.segment_for` keys) for
   the autopilot/smart strategies.
4. Proposals queue stays (linked from the console header).

- [ ] Failing tests: permissions on new views; surfaces tab lists every
      surface + slot; preview returns breakdown for `smart`; take-control
      creates a bound block.
- [ ] Verify: dynamics suite green; template compile sweep; disable litmus
      (console pages vanish, storefront placeholders revert to defaults).
- [ ] Commit: `feat(dynamics): merchandising console — surfaces takeover UI, live preview with score explanations, preview-as-segment`

## Deploy gate
- [ ] MINOR bump + release notes → push → smoke: home hero/grid order changes
      under a surface block; `/dashboard/dynamics/` console; disable dynamics
      → home reverts.

## Deliberately later (backlog, research-ranked)
- Visual drag-pinning over the live grid (research #2) — needs a grid editor UI.
- Rule builder with context conditions + scheduling + conflict detection (#3);
  weather condition is one cheap API + rule field.
- Measurement pack (#6): team-draft interleaving (no vendor ships it),
  GrowthBook-style sequential stats + CUPED, 5% program holdout, margin/returns
  guardrails — belongs in `experiments`, consumed by dynamics.
- NL merchandising via Linda → compiles to inspectable rules, propose-then-
  approve (#8) — extends the existing MerchandisingProposal queue.
- Rails plugin: fold its curated-rail concept into dynamics surfaces or retire
  it (it's a dead stub today) — needs its own small ADR.
