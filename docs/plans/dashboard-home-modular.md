# Dashboard home — modular tiles (KPIs / panels / setup steps)

## Problem

`admin_dashboard/views_split/home.py` still imports orders, catalog,
ai_assistant, agent_core and inventory models directly to build the
home page's KPI metrics, side panels, and first-run setup checklist.
That fails the disable litmus test (CLAUDE.md): a disabled plugin's
tile keeps rendering because the dashboard queries its models behind
the merchant's back. The activity feed already migrated to the
`ACTIVITY_FEED` filter; this increment migrates the rest of the page's
*data assembly* the same way.

## Design

Three new filters on the hooks bus (mirroring `ACTIVITY_FEED` /
`ACCOUNT_SUMMARY_FIELDS` semantics — value in, value out, bus isolates
broken handlers):

| Filter | value | kwargs | subscribers |
|---|---|---|---|
| `DASHBOARD_KPIS` (`dashboard.kpis`) | `list[dict]` — `{label, value, delta, trend, icon, series}` | `date_range` | orders (sales / orders / AOV, priority 10), catalog (active products, 20) |
| `DASHBOARD_HOME_PANELS` (`dashboard.home_panels`) | `dict` of template context keys | `date_range` | orders (`recent_orders`), catalog (`top_products`), ai_assistant (`insights`, `pulse`, provider half of `ai_summary`), agent_core (run-count half of `ai_summary`), inventory (`low_stock`, `low_stock_threshold`) |
| `DASHBOARD_SETUP_STEPS` (`dashboard.setup_steps`) | `list[dict]` — `{key, label, hint, url, done}` | — | catalog (product, 10), orders (order, 20), ai_assistant (provider, 30) |

Decisions:

- **KPI dicts, not the `Metric` dataclass.** The template reads
  `m.label` etc., which dicts satisfy; plugins must not import
  admin_dashboard's `_shared` (that would just reverse the coupling).
  orders carries its own tiny `_pct_delta`/`_trend` copies.
- **`ai_summary` is merged, not owned**: both ai_assistant and
  agent_core `setdefault('ai_summary', {...zeros})` then fill their
  half, so either can be disabled independently.
- **`date_range` passes duck-typed** (subscribers read `.start`,
  `.end`, `.prev_start`, `.prev_end`) — no import of the dataclass.
- The **email setup step stays in home.py** — it reads core settings,
  no plugin owns it. It is appended after the filter so it lands last.
- The home **template contract is unchanged** (same context keys); a
  missing key renders as an empty panel, which is the disable-test
  behaviour we want.

## Out of scope (next increments)

- `pulse_refresh` / `pulse_dismiss` views still import ai_assistant —
  they are whole routes that belong in the ai_assistant plugin via
  `register_urls`; moving them touches URL wiring + templates.
- The account sub-pages (orders list / credits / downloads) in the
  storefront — same route-ownership story.

## Verification

`admin_dashboard/tests/test_home_modular.py`:
1. `dashboard_home` + `_compute_setup_steps` bodies contain no
   `plugins.installed.<x>` imports (source scan, mirrors the
   activity-feed guard).
2. All expected subscribers registered on the three filters.
3. End-to-end: an order makes the sales KPI and `recent_orders`
   appear; a product makes the catalog KPI/setup-step flip.
