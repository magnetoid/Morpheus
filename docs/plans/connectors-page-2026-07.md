# Connectors — one comprehensive dashboard page (2026-07)

**Goal:** Merge the scattered "AI" settings page and "API tokens" (Developer) surface
into ONE top-level **Connectors** page — the single place a merchant wires Morpheus
to the outside world: AI providers (outbound), agent/API access (inbound), webhooks,
ad/sales channels, and Cloudflare/Turnstile.

User decisions (2026-07-28): **consolidated page** (configure in place, not a link hub),
**scope = AI providers + agent/API tokens + Webhooks + Ad/sales channels + Cloudflare**,
**top-level nav** (replaces the "AI" settings entry, moves "API tokens" out of Developer).

## Architecture — disable-safe by construction

The page is an **admin_dashboard shell that renders only contributed sections** via one
new filter — never a hard-coded list of sibling surfaces (that would survive a disable
and fail `test_disable_guards.py`). This mirrors the proven `channels` + `CHANNELS_OVERVIEW`
aggregator pattern.

- **New filter** `CONNECTORS_SECTIONS = 'connectors.sections'` in `core/hooks.py`.
  Each owning plugin's `ready()` registers a handler that appends a section dict:
  `{key, heading, icon, order, status, body_html}` (or `{template, context}` the shell
  renders). The bus skips inactive-plugin handlers → a disabled connector's section
  vanishes for free. Documented alongside `CHANNELS_OVERVIEW`.
- **New page** `admin_dashboard` owns `/dashboard/connectors/` (a DashboardPage in
  admin_dashboard, `nav='main'`, `section` top-level, icon `plug`/`unplug`). Its view
  fires `CONNECTORS_SECTIONS`, sorts by `order`, renders each section's body inline into
  one page with a sticky in-page section nav (anchors). Template
  `admin_dashboard/connectors.html`.
- **Each section is contributed by its owner** (one-owner rule):
  1. **AI providers** — `ai_assistant`. Reuse the existing provider-card UI + probe/test/
     disconnect JSON endpoints (today in `admin_dashboard/views_split/settings.py:settings_ai`).
     Extract the provider-card render into a partial `ai_assistant` owns and contributes;
     the probe/disconnect endpoints move to `ai_assistant` URLs (or stay and are called
     from the section). Configured inline.
  2. **Agent & API access** — `agent_mcp`. Bearer token CRUD + scope grid, inline
     (reuse `agent_mcp/dashboard.py:tokens_view` + `tokens.html` as a contributed section
     fragment). Retarget its DashboardPage off `section='developer'`.
  3. **Webhooks** — `webhooks_ui`. Endpoint list + add, inline or compact list + manage.
  4. **Ad & sales channels** — `channels`. Status rows via the existing `CHANNELS_OVERVIEW`
     data; each links to its full channel config (channels keep their own deep OAuth pages —
     inlining ad-account OAuth is out of scope; this section is status + "configure").
  5. **Bot protection & CDN** — `cloudflare`. Turnstile/CDN config panel, inline.
  - Plus `category`-style panels that belong here: **Agent guardrails** (agent_core),
    **Brand voice & AI content** (ai_content) — either as their own contributed sections
    or by moving their SettingsPanel `category` to `connectors`.

## IA / nav changes

- Add top-level **Connectors** nav entry (main rail), between Users and Settings.
- Remove the standalone `ai` **settings category** (its panels/provider UI move to Connectors).
  `SETTINGS_CATEGORIES`, `context_processors` nav, and `settings_category` dispatch updated.
- Retarget `agent_mcp` (tokens), `webhooks_ui`, `cloudflare` DashboardPages from
  `section='developer'` → contribute to Connectors (via the filter), so the Developer hub
  no longer shows them. Developer keeps observability/metafields/workflows/etc.
- **Redirect** `/dashboard/settings/ai/` → `/dashboard/connectors/` (back-compat; some
  links/bookmarks/tests point at the old URL).

## Honest scope note (inline vs link)

"Configure in place" holds for AI providers, tokens, webhooks, Cloudflare (form/card UIs).
**Ad/sales channels stay status + link** — each channel has deep, per-provider OAuth /
ad-account setup that is not sensible to inline; the Connectors section shows connection
status and links to the existing channel page. Flag this to the user.

## Build order (each an independently testable checkpoint)

1. **Foundation** — `CONNECTORS_SECTIONS` filter + the `/dashboard/connectors/` page shell
   (renders "no connectors yet" when empty) + top-level nav entry + disable-test entry if
   any hard-coded link is added. Verify: page 200 for staff, 302 anon; nav shows; empty state.
2. **Agent & API access section** (agent_mcp contributes; retarget off developer). Verify:
   token section renders inline on Connectors; tokens still CRUD; gone when agent_mcp disabled.
3. **AI providers section** (ai_assistant contributes; extract provider-card partial). Verify:
   connect/test/disconnect work from Connectors; usage shows; gone when ai_assistant disabled.
4. **Channels + Cloudflare + Webhooks sections**. Verify each renders + disable-safe.
5. **Panels** — Agent guardrails + Brand voice under Connectors. Retire the `ai` settings
   category + redirect old URL. Update `test_disable_guards.py` if needed.
6. **Docs** — ARCHITECTURE/PLUGIN_DEVELOPMENT note the new filter; CLAUDE.md if a landmine
   emerges; `manage.py release` (MINOR).

Tests throughout: `DATABASE_URL='sqlite:///:memory:'`. Disable-test + boundary ratchet green.
One deploy on explicit "ship" with a version bump.
