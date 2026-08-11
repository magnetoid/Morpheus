# Morpheus Self-Improvement Engine — Architectural Plan (v2)

> **Status:** architectural recommendation, pre-implementation.
> **Position in the system:** core, not plugin. Lives in `core/self_improvement/`.
> **Cannot be disabled.** Only per-class confidence thresholds in
> `core.settings.self_improvement` are configurable.

## 0. Why this is core, not a plugin

A self-improvement loop is the **immune system** of an AI-first platform.
On a vibecoding platform where every shop customises code, the loop that
keeps each fork alive over months is foundational, not an optional add-on:

- It depends on `core/hooks.py`, `core/observability/`, `core/safety.py` —
  all foundational siblings.
- Disabling it would leave shops without code-drift tracking → forks
  silently decay → security patches don't apply → shop dies.
- Specific healers (per issue class) can still be pluggable — they
  register via the hooks bus. The orchestrator + signal bus + policy
  matrix + safety boundary stay in core.

This document supersedes any earlier "plugin-located" sketch.

---

## 1. Architecture — Four Subsystems, MAPE-K Mapped

```
                   ┌──────────────────────────────────────────────┐
                   │  /dashboard/system/self-improvement/         │
                   │  Renovate-Dashboard pattern: persistent      │
                   │  backlog · per-row checkbox · DORA strip     │
                   │  rendered by admin_dashboard, data from core │
                   └────────────┬─────────────────────────────────┘
                                │ HTMX poll
   ┌────────────────────────────┼────────────────────────────────┐
   │                            │                                │
   ▼                            ▼                                ▼
[INGEST]               [ANALYZE & RANK]                  [HEAL & VERIFY]
core/self_improvement/  core/self_improvement/            core/self_improvement/
  collectors/             recommend.py                      heal.py
  (one per source)        (Plan-and-Execute)                healers/<class>.py
  ▲                            ▲                                ▲
  │ core.hooks                 │ delegates to                   │ sandboxed PR-as-output
  │ Celery Beat                │ agent_core Worker              │ via gh CLI
  │ direct subscribers         │ (sibling foundational)         │ self-improvement/* branch
  │                            │                                │
  └──────────────► [KNOWLEDGE STORE] ◄──────────────────────────┘
                   core/self_improvement/models.py
                   PG tables (si_*) · core migrations
                   episodic memory (vector, optional Phase 3)
                   policy matrix in core.settings.self_improvement
                   safety boundary from core/safety.py
```

**MAPE-K canonical mapping** (Kephart & Chess 2003 — still the reference
architecture per current SOTA):

- **Monitor** = `collectors/` + hook subscribers wired in
  `core/self_improvement/apps.py:ready()`.
- **Analyze + Plan** = `recommend.py` — one Worker invocation,
  Plan-and-Execute over ReAct (cheaper, inspectable).
- **Execute** = `heal.py` + `healers/<class>.py` — sandboxed,
  PR-as-output, never auto-merge to `main`.
- **Knowledge** = `models.py` Postgres tables + `policy.py` matrix +
  `core/safety.py` boundary.

Single Worker (`agent_core`), no specialist agent class. Specialization
= Skill bundle. Honors the existing `MEMORY.md` rule.

---

## 2. Layout — Core + Admin Rendering Layer

```
core/
  safety.py                 # PROTECTED_PATHS, FORBIDDEN_DIFF_PATTERNS,
                            # CLASS_BLOCKLIST — single source of truth;
                            # also read by agent_mcp, CI hooks, pre-commit.

  self_improvement/
    __init__.py
    apps.py                 # AppConfig.ready() → wires hook subscribers
                            # + registers Beat tasks via morph/celery.py
    models.py               # 5 tables (§3); migrations in core/migrations/
    services.py             # ingest, scoring, dedup, suppression
    policy.py               # Per-class confidence + reversibility matrix
    prompts.py              # Versioned LLM prompt templates
    tasks.py                # Celery Beat entries
    recommend.py            # Plan-and-Execute analyzer Skill
    heal.py                 # Reason-Plan-ReAct healer Skill
    verify.py               # Adversarial verifier + perspective-diverse panel
    collectors/
      __init__.py
      error_log.py          # Read existing observability.ErrorEvent
      csp.py                # New /api/_csp_report/ endpoint
      slow_query.py         # New middleware, sample 1%
      web_vital.py          # New /api/_vitals/ endpoint + storefront beacon
      cart_abandon.py       # CART_ABANDONED hook subscriber
      zero_search.py        # SEARCH_PERFORMED hook, filter result_count=0
      seo_gap.py            # Daily DB scan (Product/Page missing meta/alt/OG)
      dep_scan.py           # pip-audit + osv-scanner --call-analysis nightly
      lighthouse.py         # Nightly LH-CI run against top sitemap URLs
      dead_link.py          # Weekly sitemap + internal link walk
      code_quality.py       # ruff + mypy + vulture + radon + jscpd + bandit
      upstream_drift.py     # Git diff vs canonical Morpheus tag
    healers/
      __init__.py
      base.py               # Healer ABC + register_healer() hook signal
      alt_text.py           # Class 1 — auto-apply, data fix
      meta_description.py   # Class 2 — auto-apply, data fix
      redirect.py           # Class 3 — auto-apply, deterministic
      synonym.py            # Class 4 — auto-apply, data fix
      dep_bump.py           # Class 5 — PR, never auto-merge
      cve_patch.py          # Class 6 — PR, reachability-gated
      csp_drift.py          # Class 7 — PR, 24h replay verifier
      slow_query.py         # Class 8 — ADVISE ONLY (migrations protected)
      image_regression.py   # Class 9 — auto-apply via Pillow re-encode
      flaky_test.py         # Class 10 — PR, quarantine decorator
      style_fix.py          # Class 11 — ruff --fix, auto-apply at high conf
      missing_types.py      # Class 12 — PR, mypy-verified
      dead_code.py          # Class 13 — ADVISE ONLY (could be exported)
      complexity_spike.py   # Class 14 — ADVISE ONLY (architectural)
      bandit_finding.py     # Class 15 — PR, never auto-merge
      upstream_sync.py      # Class 16 — PR, customization-aware cherry-pick
    tests/
      __init__.py
      test_safety_boundary.py   # Required: PROTECTED_PATHS enforced 5 ways
      test_policy_matrix.py
      test_dedup.py
      test_upstream_drift_classifier.py

plugins/installed/admin_dashboard/
  views/system.py           # Routes /dashboard/system/self-improvement/
                            # — just renders core/self_improvement data
  templates/admin_dashboard/system/self_improvement/
    page.html               # Backlog · Healing log · Settings · Cost · Drift
    _row.html
    _dora_strip.html
    _policy_matrix.html
    _action_log.html
    _drift_panel.html       # Per-file upstream/local/orphan view
```

The dashboard page renders **under `/dashboard/system/`** (sits next to
other core surfaces like environment, health, deploys). Engineer-facing,
not merchant-facing — emphasized by the URL.

Healers are pluggable: any installed plugin can register an additional
healer for an existing class (or a new class) via the new hook
`self_improvement.register_healer` fired from
`core/self_improvement/apps.py:ready()`. The orchestrator stays in
core; the specific repair recipes can ship from anywhere.

---

## 3. Database Tables

All tables prefixed `si_`. All have `created_at`, `updated_at` (omitted
below for brevity).

### `si_signal`
Raw ingested signal; append-only; partitioned weekly by `occurred_at`.

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `source` | varchar(64) | `error_log`, `csp`, `slow_query`, `web_vital`, `cart_abandon`, `zero_search`, `cve`, `dep`, `lighthouse`, `dead_link`, `seo_gap`, `code_quality`, `upstream_drift` |
| `fingerprint` | varchar(128) | Deterministic hash for dedup (`error:<type>:<top_frame>`, `code:<path>:<rule>`, `drift:<path>:<hunk_sha>`) |
| `severity` | smallint | 0-100 |
| `payload` | jsonb | Source-specific |
| `occurred_at` | timestamptz | |
| `seen_count` | int default 1 | Incremented on duplicate fingerprint within 24h |

Indexes: `(source, occurred_at DESC)`, `(fingerprint, occurred_at DESC)`,
BRIN on `occurred_at`. Auto-drop > 90d.

### `si_recommendation`
The backlog the dashboard renders.

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `class` | varchar(64) | one of the 16 (§6) |
| `title` | varchar(200) | Imperative, ≤ 80 chars |
| `rationale` | text | LLM-written, cites signal_ids |
| `confidence` | numeric(4,3) | 0.000–1.000 |
| `impact_score` | int | impact × feasibility × evidence |
| `evidence_signal_ids` | bigint[] | FK to `si_signal` rows |
| `proposed_action` | jsonb | `{kind: advise\|open_pr\|apply_data, files, patch, test_command}` |
| `status` | varchar(16) | `proposed`, `approved`, `auto_applied`, `in_pr`, `merged`, `rejected`, `suppressed`, `failed` |
| `pr_url` | varchar(300) | When opened |
| `actor` | varchar(64) | `worker` or staff username |
| `suppressed_by_id` | bigint FK | If matched a suppression rule |
| `model_id` | varchar(64) | LLM model + version (for eval) |
| `tokens_used` | int | Cost dashboard |
| `is_customization_safe` | bool | Set by upstream-drift classifier — `false` blocks auto-apply |

Indexes: `(status, impact_score DESC)`, `(class, status)`, GIN on
`evidence_signal_ids`, partial index `WHERE status='proposed'`.

### `si_action_log`
Every healing attempt — append-only audit trail.

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `recommendation_id` | FK | |
| `phase` | varchar(16) | `detect`, `propose`, `gate`, `execute`, `verify`, `rollback` |
| `outcome` | varchar(16) | `ok`, `blocked`, `failed`, `timeout` |
| `details` | jsonb | stdout/stderr/diff/test result |
| `sandbox_run_id` | uuid | Links phases of one run |
| `duration_ms` | int | |

Indexes: `(recommendation_id, phase)`, `(outcome, created_at DESC)`.

### `si_ingest_job`
Health of the ingest pipeline.

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `collector` | varchar(64) | |
| `started_at` / `finished_at` | timestamptz | |
| `signals_emitted` | int | |
| `status` | varchar(16) | `ok`, `partial`, `failed` |
| `error` | text | |

Indexes: `(collector, started_at DESC)`.

### `si_suppression`
Rejected-once-means-never-again ("ThumbGate" pattern).

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `match_class` | varchar(64) | |
| `match_fingerprint` | varchar(128) | NULL = whole class |
| `reason` | text | Required from rejector |
| `expires_at` | timestamptz | NULL = forever |
| `created_by` | FK auth.User | |

Index: unique `(match_class, match_fingerprint)` where not expired.

### `si_customization` (new in v2)
Per-file declarations of intentional drift from canonical Morpheus.
Lives alongside the engine because every healer reads it.

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `path` | varchar(500) | Repo-relative |
| `intent` | varchar(32) | `intentional`, `experimental`, `vendor_specific` |
| `why` | text | Human-written rationale |
| `owner` | varchar(64) | username / role / team |
| `locked_until` | timestamptz | NULL = forever; auto-revisit after |

Index: unique `(path)`.

**Policy config** lives in `core.settings.self_improvement` (not a
table) — a single Python dict in settings with sane defaults, overridable
per environment. Matches the existing `core.settings` pattern.

---

## 4. Data Sources (Priority Order)

| # | Signal | Collection | Cadence | Stored as |
|---|---|---|---|---|
| 1 | `observability.ErrorEvent` | Direct read | Hourly | `error_log` |
| 2 | Celery task failures | Existing `@task_failure.connect` in `morph/celery.py` | Real-time | `error_log` |
| 3 | CSP violations | New `/api/_csp_report/` endpoint | Real-time | `csp` |
| 4 | Slow queries | New middleware logs > 250ms p95 (sample 1%) | Real-time | `slow_query` |
| 5 | Web Vitals | New `/api/_vitals/` + storefront beacon | Real-time | `web_vital` |
| 6 | `CART_ABANDONED` hook | Subscribe | Real-time | `cart_abandon` |
| 7 | `SEARCH_PERFORMED` w/ result_count=0 | Subscribe | Real-time | `zero_search` |
| 8 | SEO gap audit | `Product`/`cms.Page` query for missing meta/alt/OG | Daily 03:30 | `seo_gap` |
| 9 | CVE / dep advisories | `pip-audit` + `osv-scanner --call-analysis=python` | Daily 02:00 | `cve` / `dep` |
| 10 | Lighthouse-CI | Top 10 URLs sitemap-driven | Daily 03:00 | `lighthouse` |
| 11 | Dead-link scan | Sitemap + internal links walk | Weekly Sun 04:00 | `dead_link` |
| 12 | **Code-quality scan** (new) | `ruff`, `mypy`, `vulture`, `radon cc`, `jscpd`, `bandit`, coverage gap | Weekly Mon 05:00 | `code_quality` |
| 13 | **Upstream-drift scan** (new) | `git diff` vs canonical Morpheus tag, classify each hunk | Daily 04:30 | `upstream_drift` |

Collectors are pluggable: feature plugins can register additional
collectors via `self_improvement.register_collector` hook. The 13 above
are core.

---

## 5. Recommendation Pipeline

```
raw signals (last 24h)
  → dedupe by fingerprint, sum seen_count
  → drop anything matching active si_suppression
  → cluster by (class, top-N entity) using deterministic rules (no LLM)
  → score: impact_score = severity × reach × evidence_size × (1 / age_decay)
  → take top 50 clusters
  → for each: Plan-and-Execute analyzer Worker run
      Plan step:  one LLM call → "what kind of fix, what files, what risk"
      Execute step: deterministic — fetch the named files, run static checks,
                    consult si_customization (skip if intentional drift)
      Synth step:  second LLM call → write rationale + confidence + proposed_action
  → adversarial verifier (second LLM, different prompt) per recommendation
  → write si_recommendation rows
  → fire self_improvement.backlog.updated hook
```

**Tier-1 deterministic signals always run first.** Style/format/complexity/
unused-import findings emit recommendations with confidence 1.0 and skip
the LLM analyzer entirely — they're already actionable. The LLM only runs
on the top-N items from tier 1 (semantic, hypothesis-required, ambiguous).

Plan-and-Execute over ReAct because the steps are knowable up-front,
cheaper, and inspectable before execution. The adversarial verifier
kills anything that fails the rubric.

**Prompt template** (`prompts.py`, versioned):

```
SYSTEM: You are a senior Django + e-commerce engineer reviewing a single
cluster of signals from a Morpheus shop. Output strict JSON matching the
schema. Be falsifiable. Cite evidence by signal_id. If unsure, set
confidence below 0.5 and propose `advise` not `open_pr`.

CONTEXT:
- Module: {module}                       # core path or plugin name
- Class: {recommendation_class}
- Customization status of affected files:
  {customization_summary}                # from si_customization
- Signal cluster ({count} signals over {window}):
  {signal_summary}                       # deduped, with seen_count + URLs
- Affected file excerpts (50-line windows, ACI-style):
  {file_excerpts}
- Episodic memory (prior similar):
  {prior_fixes_summary}                  # vector recall, max 3
- Policy for this class:
  reversibility={reversibility}, auto_threshold={auto_threshold}

REQUIRED OUTPUT (JSON, no prose):
{
  "title": "<=80 chars, imperative",
  "rationale": "<=600 chars, cites signal_ids",
  "confidence": 0.0-1.0,
  "impact_score": 0-1000,
  "is_customization_safe": true|false,
  "proposed_action": {
    "kind": "advise" | "apply_data" | "open_pr",
    "files": ["path/relative/to/repo/..."],
    "patch": "unified diff or null",
    "test_command": "pytest path -k ..."
  },
  "uncertainty_flags": ["..."],          # things you did NOT check
  "rollback_cost": "trivial" | "moderate" | "high"
}

HARD RULES:
- Never propose changes inside: {PROTECTED_PATHS}.
- Never modify migrations.
- Never propose changes to files flagged `intentional` in si_customization
  unless the class is `upstream_sync`.
- Never add a new top-level import not already in poetry.lock (slopsquatting).
- If the change touches > 5 files or > 200 lines, downgrade to `advise`.
```

Hard rules are also enforced in `core/safety.py` after the LLM returns —
defense in depth.

---

## 6. Healing Pipeline — 16 Issue Classes

Per Research 1, 3, 7: auto-apply only where blast radius is bounded,
change is reversible, and a deterministic verifier exists.

### Data-only auto-fixes (touch DB rows, not code)

| # | Class | Detect | Verifier |
|---|---|---|---|
| 1 | Missing alt text | SEO collector query | re-query: 0 missing |
| 2 | Missing meta description / OG | SEO collector | re-query |
| 3 | Broken internal redirect (→ 301) | Dead-link scan | curl returns 301 |
| 4 | Zero-result search → synonym | `zero_search` cluster ≥ 10 | re-run query, ≥ 1 result |

### Code-touching auto-PRs (never auto-merge to `main`)

| # | Class | Detect | Safety Gate | Verifier |
|---|---|---|---|---|
| 5 | Dep patch bump (no API change) | `pip-audit` + `osv-scanner` | ≥ 0.85 + tests green + Trivy clean + not in `{django, celery, strawberry, psycopg, redis}` | CI on PR |
| 6 | CVE patch (reachability-gated) | OSV scanner | ≥ 0.90 + `--call-analysis` confirms reachable + grep diff doesn't touch `payments/`, `rbac/`, `customers/auth*` | CI on PR |
| 7 | CSP allowlist drift | CSP cluster ≥ 100 same `blocked-uri` | ≥ 0.75 | 24h replay shows ≤ 1% legit blocks |
| 8 | **Slow query → index** | `slow_query` cluster ≥ 50 same shape | **ADVISE ONLY — migrations protected** | n/a |
| 9 | Lighthouse image regression | LH delta > 200ms LCP | ≥ 0.90 (deterministic re-encode) | re-run LH, LCP improved |
| 10 | Flaky-test quarantine | Fails ≥ 3 times in 7d on stable branch | ≥ 0.95 | reduces CI red rate |

### Code-quality classes (new in v2)

| # | Class | Detect | Safety Gate | Verifier |
|---|---|---|---|---|
| 11 | Style/format (ruff --fix) | Tier-1 deterministic | ≥ 0.95 (deterministic) | re-run ruff = 0 errors |
| 12 | Missing type hints on public APIs | mypy gap | ≥ 0.90 + mypy passes after | mypy delta |
| 13 | **Dead code** (unused defs not in `__init__` exports) | vulture | **ADVISE ONLY — could be exported** | n/a |
| 14 | **Complexity spike** (radon cc delta > +5) | radon | **ADVISE ONLY — architectural** | n/a |
| 15 | Bandit medium+ finding | bandit | PR, never auto-merge | human review |

### Vibecoding-specific (the differentiator)

| # | Class | Detect | Safety Gate | Verifier |
|---|---|---|---|---|
| 16 | **Upstream-drift cherry-pick** | upstream_drift collector + classifier | ≥ 0.90 + no customization conflict + tests green + clean cherry-pick + not `intentional` in `si_customization` | CI on PR |

**Class 8 (slow_query) and Classes 13–14 are `advise`-only forever.**
Schema migrations + dead-code removal + architectural complexity all
require human judgment.

**Classes 5–7, 9, 10, 11, 12, 15, 16 open PRs against
`self-improvement/*` branches.** Coolify deploys `main` only, so PRs
*cannot* reach prod until a human merges. This is the Cursor
"PR-as-output with mandatory review" pattern.

---

## 7. The Dashboard Page

URL: `/dashboard/system/self-improvement/`. Rendered by
`admin_dashboard.views.system`, data from `core/self_improvement`.

```
┌─────────────────────────────────────────────────────────────────────┐
│ Self-Improvement                  [Last analyzer run: 03:14 UTC ✓] │
├─────────────────────────────────────────────────────────────────────┤
│ DORA STRIP (4 tiles, computed weekly)                               │
│ [Deploy freq] [Lead time] [Healing rollback rate] [MTTR for spikes] │
├─────────────────────────────────────────────────────────────────────┤
│ Tabs: [Backlog (47)] [Healing log] [Drift] [Settings] [Cost]        │
├─────────────────────────────────────────────────────────────────────┤
│ BACKLOG TAB (Renovate Dashboard pattern)                            │
│                                                                     │
│ ☐ [auto-apply 0.92] Add alt text to 47 product images               │
│    seo_gap · 47 signals · rollback: trivial                         │
│    [Approve] [Reject] [Snooze 30d] [View diff ▾]                    │
│                                                                     │
│ ☐ [propose 0.78] Bump Pillow 10.2 → 10.4 (CVE-2026-1234)            │
│    cve_patch · reachable via storefront.image_proxy · PR #482       │
│                                                                     │
│ ☐ [advise 0.65] Add index on Order(customer_id, created_at)         │
│    slow_query · 1,247 hits over 24h, p95 320ms                      │
│    "Migration required — human review only"                         │
│                                                                     │
│ ☐ [propose 0.88] Cherry-pick upstream fix for cart.html load tag    │
│    upstream_sync · clean apply · not flagged customization          │
│    "From canonical Morpheus 2026.06 → your fork"                    │
│                                                                     │
│ Filter: [class ▾] [confidence ≥ ▢] [status ▾]   Group: per-module   │
├─────────────────────────────────────────────────────────────────────┤
│ DRIFT TAB (new in v2)                                               │
│                                                                     │
│ Files diverged from canonical Morpheus 2026.06.x:                   │
│   themes/library/dot_books/        intentional   [edit registry]    │
│   plugins/installed/storefront/    ↳ 12 files                       │
│     views.py                       drift (3 hunks)  [recommend]    │
│     models.py                      intentional      ✓               │
│   core/settings.py                 orphan (1 hunk)  [recommend]    │
│                                                                     │
│ Legend: ✓ intentional · drift = not registered · orphan = lone hunk │
├─────────────────────────────────────────────────────────────────────┤
│ SETTINGS TAB — Policy Matrix                                        │
│                                                                     │
│ Class             Enabled  Auto-apply ≥  Propose ≥  Reversible      │
│ seo_gap             ☑         0.85         0.60       yes           │
│ dep_bump_patch      ☑         0.85         0.60       yes           │
│ cve_patch           ☑         0.90         0.70       yes           │
│ csp_drift           ☑         0.75         0.50       yes           │
│ slow_query          ☐ (always advise)      0.50       NO            │
│ style_fix           ☑         0.95         0.90       yes           │
│ missing_types       ☑         0.90         0.70       yes           │
│ dead_code           ☐ (always advise)      0.60       NO            │
│ complexity_spike    ☐ (always advise)      0.60       NO            │
│ bandit_finding      ☑ (never auto-merge)   0.70       yes           │
│ upstream_sync       ☑         0.90         0.70       yes           │
│ ...                                                                 │
│                                                                     │
│ Token budget: [ 500,000 ] / day      Digest: [ Mon 09:00 → email ]  │
│ Protected paths (read-only, from core/safety.py):                   │
│   plugins/installed/payments/, plugins/installed/rbac/,             │
│   plugins/installed/customers/auth, core/, migrations/, secrets/    │
└─────────────────────────────────────────────────────────────────────┘
```

**Per-row controls**: Approve → enqueues execute task; Reject → opens
modal requiring text reason, writes `si_suppression`; Snooze 30d →
suppression with `expires_at`. View diff → fetches PR diff via `gh` and
renders inline.

**Per-class matrix, not a single slider** — each class has its own
auto/propose thresholds because reversibility differs by class.

---

## 8. Hook Events

**Fires:**
| Event | When | Payload |
|---|---|---|
| `self_improvement.signal.ingested` | Any new `si_signal` row | `{signal_id, source, fingerprint, severity}` |
| `self_improvement.backlog.updated` | After analyzer run | `{added_count, total_open}` |
| `self_improvement.recommendation.proposed` | New recommendation | `{recommendation_id, class, confidence}` |
| `self_improvement.recommendation.auto_applied` | Auto-execute succeeded | `{recommendation_id, action_log_id}` |
| `self_improvement.recommendation.rejected` | Human reject | `{recommendation_id, reason, suppressed: bool}` |
| `self_improvement.healing.started` / `.failed` / `.rolled_back` | Per execute | `{action_log_id, recommendation_id, error}` |
| `self_improvement.drift.detected` | New upstream-drift signal | `{path, classification, hunk_count}` |
| `self_improvement.digest.generated` | Weekly Mon 09:00 | `{week_iso, accepted_count, rejected_count, rollback_rate}` |

**Subscribes to** (in `apps.py:ready()`):
- `CART_ABANDONED` → `cart_abandon` signal
- `SEARCH_PERFORMED` (filter `result_count == 0`) → `zero_search` signal
- `PRODUCT_CREATED` / `PRODUCT_UPDATED` → trigger immediate SEO gap check
- `AGENT_INTENT_FAILED` → `error_log` signal with agent context

**Listens for plugin registration** (the pluggability layer):
- `self_improvement.register_collector` → plugin contributes a new collector
- `self_improvement.register_healer` → plugin contributes a healer for a class

Cross-system coupling is hooks only. The engine never imports from
plugins; plugins register via hooks.

---

## 9. Scheduler — Celery Beat

Registered directly in `core/self_improvement/apps.py:ready()` via the
existing `morph/celery.py` API.

| Beat name | Task | Schedule |
|---|---|---|
| `self_improvement.ingest_hourly` | `ingest_hourly` | `crontab(minute=7)` |
| `self_improvement.scan_deps_daily` | `scan_deps_daily` | `crontab(hour=2, minute=0)` |
| `self_improvement.scan_lighthouse_daily` | `scan_lighthouse_daily` | `crontab(hour=3, minute=0)` |
| `self_improvement.scan_seo_daily` | `scan_seo_daily` | `crontab(hour=3, minute=30)` |
| `self_improvement.scan_drift_daily` | `scan_upstream_drift_daily` | `crontab(hour=4, minute=30)` |
| `self_improvement.analyze_nightly` | `analyze_nightly` | `crontab(hour=4, minute=0)` |
| `self_improvement.execute_queue_minutely` | `execute_queue` | `crontab(minute='*/5')` |
| `self_improvement.scan_links_weekly` | `scan_links_weekly` | `crontab(hour=4, minute=0, day_of_week=0)` |
| `self_improvement.scan_code_weekly` | `scan_code_weekly` | `crontab(hour=5, minute=0, day_of_week=1)` |
| `self_improvement.digest_weekly` | `digest_weekly` | `crontab(hour=9, minute=0, day_of_week=1)` |
| `self_improvement.eval_monthly` | `eval_monthly` | `crontab(hour=6, minute=0, day_of_month=1)` |

---

## 10. Safety Boundary — `core/safety.py`

Single source of truth, read by self_improvement, agent_mcp, CI hooks,
pre-commit. **This file is the system's contract with itself.**

```python
# core/safety.py

PROTECTED_PATHS = (
    'plugins/installed/payments/',
    'plugins/installed/rbac/',
    'plugins/installed/customers/auth',   # auth-only subset
    'plugins/installed/tax/',
    'plugins/installed/consent/',
    'plugins/installed/gift_cards/',
    'plugins/installed/subscriptions/billing',
    'core/',                              # foundational only
    'morph/settings.py',
    'morph/celery.py',
    '**/migrations/',
    '.env', '.env.*', 'secrets/', '**/credentials*',
)

PROTECTED_PLUGINS = ('admin_dashboard', 'agent_core', 'rbac')
# Per MEMORY.md soft-brick rule.

FORBIDDEN_DIFF_PATTERNS = (
    r'AUTH_PASSWORD_VALIDATORS', r'SECRET_KEY', r'ALLOWED_HOSTS',
    r'stripe\.api_key', r'\.delete\(\)', r'DROP TABLE', r'TRUNCATE',
    r'os\.system', r'subprocess\.', r'eval\(', r'exec\(',
)

CLASS_BLOCKLIST = {  # classes the engine refuses to even analyze
    'pricing_change', 'tax_rate_change', 'legal_copy',
    'terms_of_service', 'refund_policy', 'gdpr_consent_flow',
    'auth_logic', 'crypto_code',
}
```

**Five-layer enforcement** (per CLAUDE.md "hooks are the enforcement layer"):

1. **Pre-plan filter** in `recommend.py` — skips clusters whose primary
   file matches `PROTECTED_PATHS`.
2. **Prompt instruction** — listed in the template above (advisory).
3. **Post-LLM regex check** in `safety.assert_diff_safe(patch)` —
   rejects + logs + alerts if violated. Runs *before* the diff ever
   reaches `gh pr create`.
4. **CI guard** — pre-commit hook reads `core/safety.py` and greps the
   diff again at commit time.
5. **Permission boundary test** — required (anon blocked /
   authed-no-scope blocked / authed-scope ok).

Repository scope: PRs land on `self-improvement/*` branches only. The
Coolify deploy hook is filtered to `main`, so no auto-PR can ship to
prod without human merge. Hard cost cap in `tasks.py`: per-tick budget,
per-day budget, per-PR LOC ceiling — all from
`core.settings.self_improvement`. Exceeds budget → hard stop, log to
Sentry.

---

## 11. Cost Model

Assume Claude Sonnet 4.7 at ~$3/Mtok in / ~$15/Mtok out.

**Per-analysis run** (per cluster, top 50 clusters/day):
- Plan: ~2k tok in, 500 out → $0.014
- Execute (retrieval is deterministic, no LLM): $0
- Synth: ~4k tok in (with file excerpts), 800 out → $0.024
- Adversarial verify: ~2k tok in, 300 out → $0.011
- ≈ **$0.05 / cluster** → **$2.50 / day** for 50 clusters

**Per healing PR** (only auto-apply classes, ~10/day max):
- Patch generation: ~6k tok in, 2k out → $0.048
- PR body + rationale: ~1k in, 500 out → $0.011
- ≈ **$0.06 / PR** → **$0.60 / day** for 10 PRs

**Tier-1 deterministic** (style/format/complexity): $0 LLM cost.

**Weekly digest**: $0.10. **Monthly eval**: $2.

| Shop scale | Signals/day | Clusters/day | LLM cost/day | LLM cost/month |
|---|---|---|---|---|
| Small (<100 orders/d) | ~500 | ~10 | ~$0.60 | ~$18 |
| Medium (1k orders/d) | ~5k | ~30 | ~$2.00 | ~$60 |
| Large (10k orders/d) | ~50k | ~50 (capped) | ~$3.10 | ~$95 |

Hard cap default in `core.settings.self_improvement`:
`daily_token_budget = 500_000` → ~$5/day worst case. Haiku fallback for
the verifier step is a one-line config flip and drops costs ~5×.

---

## 12. Phased Delivery

### Phase 1 — Read-only MVP (3 weeks)

Deliverable: a populated backlog at `/dashboard/system/self-improvement/`
that shows recommendations engineers can read but not act on
programmatically. Proves the recommender's accept-rate per class before
any auto-apply ships.

- Tables: `si_signal`, `si_recommendation`, `si_suppression`,
  `si_ingest_job`, `si_customization`.
- Collectors: `error_log`, `csp`, `seo_gap`, `zero_search`,
  `cart_abandon`, **`code_quality` (deterministic only)**, **`upstream_drift`**.
- Analyzer Skill: Plan-and-Execute + adversarial verifier — runs only
  on tier-2 (LLM-required) classes. Tier-1 (style/format) emits
  recommendations directly without LLM.
- Dashboard page: Backlog tab + **Drift tab** + Settings (policy matrix)
  tab + Cost tab.
- All actions are `advise` — no `open_pr`, no `apply_data`, no
  auto-apply. Confidence shown but un-actionable.
- Weekly digest email.
- Permission boundary tests + safety regex tests.

### Phase 2 — Data-only auto-fixes (4 weeks)

- Add classes 1–4 (alt text, meta description, redirects, search
  synonyms). These touch DB rows, never code.
- Add `si_action_log` table + Healing log tab.
- Per-class `auto_apply` toggle defaults OFF. Engineer opts in per class.
- Rollback button on every applied action.
- Monthly eval task: track accept/reject precision per class.

### Phase 3 — Code-touching auto-PRs (6 weeks)

- Add classes 5–7, 9, 10, 11, 12, 15.
- `github.py` GitHub PR integration.
- Sandbox Celery worker (`self_improvement_sandbox` queue, scoped DB
  user, no shell access).
- Reason-Plan-ReAct healer Skill with perspective-diverse verifier panel.
- Tier-1 (style/format) auto-applies; tier-2 opens PRs.
- Class 8 (slow_query) ships as `advise`-only forever.
- DORA strip with rollback-rate tracking.

### Phase 4 — Vibecoding-specific upstream sync (6 weeks)

- Class 16 (`upstream_sync`) ships fully.
- `si_customization` registry editing UI.
- Upstream-drift classifier becomes a tested module — distinguishes
  intentional / drift / orphan with > 90% precision (eval set required).
- Cherry-pick automation: detect upstream commits affecting non-customized
  files, propose clean cherry-pick PRs.
- Defer indefinitely: pricing, copy, taxonomy, content. These are
  merchant-judgment territory, not engineering self-healing.

---

## 13. Anti-Patterns (Explicit "We Will Not")

1. **No multi-agent orchestration.** One Worker, Skill bundles. Honors
   `MEMORY.md`.
2. **No auto-merge to `main` — ever.** PRs always land on
   `self-improvement/*` and require human merge.
3. **No schema migrations from AI.** Migrations are protected paths.
   Class 8 stays `advise` forever.
4. **No new specialist agent class.** Specialization is Skill + scope,
   not a subclass.
5. **No single confidence slider.** Per-class matrix only.
6. **No LangGraph / CrewAI / AutoGen dependency.** Single-agent + Skills
   is provably equivalent at lower token cost.
7. **No new top-level package installs from AI suggestions.**
   Slopsquatting defense (18-21% of LLM-suggested packages are
   hallucinated).
8. **No agent that can spend money, change prices, issue refunds, write
   to legal/ToS pages, or modify auth.** Class blocklist.
9. **No "fix this for you" UI copy without precision/recall numbers.**
   Dashboard must show the system's own accept-rate per class.
10. **No "AI refactors ugly code".** Style is personal; system would
    generate noise. Tier-1 deterministic style/format only.
11. **No closed-loop autonomous rewriter.** PR-as-output is the contract.
    Every reported case in Research 2 (Devin, OpenHands, Cursor) collapsed
    when this rule was broken.
12. **No code review without test coverage.** Shops with < 50% coverage
    can't safely receive proposed code changes — system flags and waits.
13. **No "touch a customization without permission".** Files flagged
    `intentional` in `si_customization` are off-limits except for the
    `upstream_sync` class (and only with explicit confirmation).

---

## Integration anchors (existing Morpheus code to mirror)

- Worker + Skill contract: `plugins/installed/agent_core/app.py`,
  `contribute_agent_tools()` / `contribute_skills()`.
- Hooks: `core/hooks.py` (canonical events lines 295–407), subscribe
  via direct registration in `core/self_improvement/apps.py:ready()`.
- Beat: register directly with `morph/celery.py:app.conf.beat_schedule`.
- Dashboard page mounting: see `plugins/installed/admin_dashboard/views/`
  for the rendering pattern; new `views/system.py` adds the
  `/dashboard/system/self-improvement/` route.
- PluginConfig is not used (core, not plugin). Config lives in
  `core.settings.self_improvement` dict in `morph/settings.py`.
- Error capture infra to reuse: existing observability subsystem +
  `@task_failure.connect` in `morph/celery.py:52-71`.
- Protected-plugin enforcement: `MEMORY.md` PROTECTED_PLUGINS guard
  from `plugin_toggle_softbrick`.

---

## What's open

These need user decisions before Phase 1 ships:

1. **Episodic memory backing** (Phase 2+): Postgres + pgvector (already in
   stack) vs LanceDB vs in-memory hash. Recommendation: pgvector, already
   running.
2. **GitHub PR identity** (Phase 3): use a dedicated `morpheus-self-improvement`
   bot token, or sign PRs as the current staff user? Recommendation: bot
   token; auditable, separable.
3. **Per-shop vs platform-wide upstream tag** (Phase 4): does each shop
   declare which Morpheus version it forked from, or do we auto-detect
   from `morph/__version__.py`? Recommendation: declared in
   `core/customizations.yml`, auto-detected as fallback.
4. **CSP report endpoint adoption**: do we keep the existing
   `/api/csp-report/` and have the engine subscribe via hook, or move
   the canonical endpoint to `/api/_csp_report/`? Recommendation: keep
   existing, subscribe.
