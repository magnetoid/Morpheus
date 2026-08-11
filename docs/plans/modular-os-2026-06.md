# Modular OS initiative — "disable an app, its surfaces vanish"

Owner rule (now in CLAUDE.md § Plugin contract + AGENTS.md): a feature lives
entirely under `plugins/installed/<name>/` and appears elsewhere only by
**contributing**. Two litmus tests: deleting the dir leaves no dangling ref;
**disabling the plugin removes every surface** (nav, settings, blocks, tiles).

## Mechanisms that already exist (use these, don't hard-code)
- **Dashboard nav/pages:** `DashboardPage(label, slug, view, section, nav=...)`
  in `plugins/contributions.py:46-80`; rendered by the `sidebar_sections` loop in
  base.html (≈742-760) which auto-hides disabled plugins. ✅ correct path.
- **Storefront blocks:** `StorefrontBlock(slot, template, ...)` (`plugins/contributions.py:25-44`)
  + `{% storefront_blocks "slot" %}`. Slots: home_above/below_grid, pdp_*, cart_summary_extra,
  checkout_extra. **GAP: no `account_nav` / `account_page` slot.**
- **Settings:** `SettingsPanel` via `plugin.contribute_settings_panel()`. **GAP:** rich settings
  UIs (payments/ai/caching) are hard-coded as `if category==...` dispatch in
  `admin_dashboard/views_split/settings.py:763-768` — not pluggable.
- **Enabled check:** `active_plugins` context list (`{% if 'x' in active_plugins %}`);
  `app_registry.is_enabled(name)` in py. **GAP: no `{% plugin_enabled 'x' %}` tag.**

## Violations (from audit 2026-06-01)
1. **loyalty `/account/points/`** — view in `storefront/views/account.py`, route in
   `storefront/urls.py:89`, tile hard-coded in `themes/.../account_home.html:48-53`. Fails disable test.
2. **loyalty balance injection** in storefront `_account_summary()` (account.py:26-96) — hard-coded field.
3. **payments settings** — `settings_payments()` view + `settings_payments.html` in admin_dashboard;
   payments plugin has NO `contribute_settings_panel()`. (This is the build I just held — do NOT commit as-is.)
4. **affiliates nav** hard-coded in base.html:712-732 (guarded by `active_plugins` so it's safe, but
   duplicative with the `sidebar_sections` loop). Easiest win — verify affiliates contributes
   DashboardPages, then delete the hard-coded block.
5. ai/caching settings — same shape as payments (lower priority; arguably core).

## Phased plan
**Phase A — safe wins (no new mechanism):**
- Add a `{% plugin_enabled 'x' %}` template tag (thin wrapper over the registry).
- Verify affiliates contributes DashboardPages; if so, delete base.html:712-732.

**Phase B — build the two missing mechanisms:**
- `account_nav` StorefrontBlock slot in the storefront account shell + an
  `ACCOUNT_SUMMARY_FIELDS` hook so plugins contribute account tiles/pages/fields.
- A settings-view-override contribution (plugin ships its own settings view+template) OR
  require `contribute_settings_panel()`; drop the hard-coded `if category==` dispatch.

**Phase C — migrate the violations onto the mechanisms:**
- loyalty: move account_points view + template into `loyalty_points`, contribute the tile via
  `ACCOUNT_SUMMARY_FIELDS` + the account page via `account_nav`. Remove storefront/theme hard-coding.
- payments: move settings UI into the payments plugin via the Phase-B override; keep the (good,
  already-in-plugin) PaymentGatewayConfig model + enabled_gateways() helper + tests.

## More contribution slots requested (same mechanism family)
- **Customer-detail dashboard page** needs a plugin-contributed slot. Ask: the user
  account page should have toggles to turn a user on/off as a **vendor** (contributed
  by `marketplace`) and as an **affiliate** (contributed by `affiliates`) — each
  toggle lives in its own app, not hard-coded into customers/admin_dashboard. Build a
  `customer_detail_panels` contribution (plugins return a panel/partial for the
  customer detail view), then marketplace + affiliates each contribute their toggle.
  Disabling either plugin removes its toggle. Same pattern as `account_nav` /
  `ACCOUNT_SUMMARY_FIELDS`.

## Status
- Rule documented (CLAUDE.md, AGENTS.md). Audit done. Payments build HELD uncommitted.
- Phases B/C are real engineering (new slots/hooks) — do them deliberately, not in a bloated context.
