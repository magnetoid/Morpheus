# Morpheus — house rules for AI-assisted work

> Companion rulesets: [`vendor/vibe-skills/llm-rules/claude.md`](vendor/vibe-skills/llm-rules/claude.md) (Claude-specific) and [`vendor/vibe-skills/AGENTS.md`](vendor/vibe-skills/AGENTS.md) (cross-IDE). See [`AGENTS.md`](AGENTS.md) for the full map.

This file is **only for things you can't discover from `grep`, `find`, or
`manage.py`.** Stack, file layout, lint config — read the code. Things
written below are the rules, the landmines, and the conventions that
aren't visible from the tree.

Target length: under 200 lines. Edit it when an assumption ships wrong.

---

## Architectural compass

**Build an advanced, powerful e-commerce platform — and deliver that power
*through* modularity, not by bloating core.** Ambition is the point: deep
catalog (variants, bundles, digital, subscriptions), rich pricing/promotions,
multi-currency/markets, B2B, inventory, checkout, fulfillment — a serious
commerce engine, never a toy "minimal" spine. "Powerful" means deep
capabilities + a first-class agent/dashboard/storefront surface; it does **not**
mean feature code accreting in `core/`. The kernel stays a clean set of
extension points — that's the *mechanism* that keeps the powerful platform
swap-able, disable-safe, and agent-legible, not a cap on how capable it may be.
(ADR 0017, superseding the old "tiny core" framing of ADR 0010.) Anything that
isn't *required* for catalog → cart → checkout → fulfillment lives in
`plugins/installed/<name>/` with its own
`apps.py`, `app.py` manifest, `models.py`, `migrations/`, and
templates. Reach for `core/` only when the feature is genuinely
foundational: auth, hooks, i18n kernel, request_id, observability,
**the self-improvement loop** (autonomic engine + code-quality scanner +
upstream-drift tracking — the immune system of a vibecoded platform; cannot
be a togglable plugin), and **the safety boundary** (`core/safety.py` —
single source of truth for what AI can touch; read by self-improvement,
agent_mcp, CI hooks, pre-commit).

When in doubt: it's a plugin.

Examples (this is what's already shipped — mirror the pattern):

- Reviews, loyalty, markets, notifications, workflows, metafields, media,
  CMS — all plugins.
- The agent layer, hooks bus, settings, request lifecycle, self-improvement
  engine, safety boundary — core.

**Plugin contract:**

- Single AppConfig in `apps.py` (plus `ready()` for signal/hook wiring).
- Plugin manifest in `app.py` (name/label/version/requires/blocks/tools).
- Register in `morph/settings.py:MORPHEUS_DEFAULT_APPS`.
- Add a migration before merge — system check fails on every prod boot
  if you ship a model without one.
- Storefront integration through `StorefrontBlock(slot=...)` contributions,
  not direct template edits in `themes/`.
- Cross-plugin coupling through the `core.hooks` event bus — never import
  one plugin from another's models.
- **Before creating a plugin, audit for overlap**: grep
  `MORPHEUS_DEFAULT_APPS` and the existing plugin descriptions, and
  justify the boundary in the PR. One concept = one model owner —
  extending a flow means a FK/OneToOne to the owner's model (declared in
  `requires`) plus hooks, **never a parallel table**. (PR #62 shipped a
  second, incompatible `ReturnRequest` invisible to the dashboard, RMA
  numbers, and the refund service; consolidated since.)

**Landmine — a cache invalidator that deletes a prefix nothing writes is a
no-op that ONLY misbehaves in production.** `api/cache.py` keys GraphQL
responses `graphql:query:<hash>`; `core/utils/cache.py` deleted
`gql:*product*`, which nothing has ever written, so every product edit
invalidated **zero** keys and the API served stale prices until the TTL lapsed.
Dev never showed it: `delete_pattern` exists on django-redis, while dev/tests
use LocMem, which lacks it and falls through to `cache.clear()` — so
development always looked correct. The two files never import each other, so
nothing tied them together. Note the key is a hash of query+variables and says
nothing about which entities the response touched, so per-entity invalidation
is impossible by construction — clearing is necessarily broad. Guarded by
`core/tests/test_cache_invalidation.py`, which asserts the patterns actually
match a key built the way `api/cache.py` builds it.

**Landmine — registering a real tool under a fake owner hands over ownership,
and dropping the fake owner deletes the real tool.** `agent_registry` is
process-global. A test did `register_tool(products_update_status_tool,
plugin='__hygiene_test')` then `drop_plugin('__hygiene_test')` in `finally` —
which removed the REAL catalog tool for every test that ran later in the same
process, producing four "order-dependent" failures with no obvious cause. Save
and restore the prior registration (`get_tool` + `_tool_owners`) instead of
dropping. More generally: when a test mutates a process-global registry, restore
the previous *value*, never assume removal is the inverse of registration.

**Landmine — `body.index('Word')` on a rendered page finds the THEME'S copy.**
A live_commerce test asserted product order via `body.index('Two') <
body.index('One')` and failed for a year — because dot_books' own marketing
prose contains *"One bold move; everything…"* 26,000 characters before the
product grid. The products were ordered correctly the whole time. Assert on a
unique marker (a slug, an id, a contribution-specific string), never a bare
display word — the same rule `test_slot_parity` already states for
`'<style' in head`.

**Landmine — a capability no role can hold denies EVERYONE, and only once
enforcement is on.** Authorization goes through one seam, `core/authz.py`
(`has_capability` / `check` / `@require_capability`), which fires
`AUTHZ_CAPABILITY_CHECK`; the `rbac` app answers from role bindings. A direct
`admin_dashboard → rbac` import would be the plugin→plugin coupling the ratchet
blocks, so core fires and the app answers — same inversion as
`PRODUCT_CALCULATE_PRICE`. **The seam fails OPEN on absence** (nothing answers →
fall back to `is_staff`): an authorization layer that failed closed when its own
answerer is missing would lock every merchant out of their dashboard. Denial is
opt-in via rbac's `enforcement_mode` (`off` | `log` | `enforce`, default
**log** = record what *would* be denied, deny nothing). **The trap:** a view
gated on a capability that is not in `rbac._DEFAULT_TEMPLATES` looks fine, tests
green, until someone switches to `enforce` — then it denies everyone but
superusers, forever, because no role grants it. (`marketing.write` was written
this way and caught before it shipped; there is no `marketing.*` capability.)
Guarded by `core/tests/test_authz.py::CapabilityVocabularyTests`, which scans
every `@require_capability` on disk against the vocabulary. When gating a new
view, use an existing capability or add it to the templates in the same change.

**Convention — one word for the merchant ("app"), one shape in the tree.**
The merchant-facing vocabulary is **Apps**, everywhere: nav, page titles,
settings category, empty states. The code matches it at every seam a plugin
author touches — manifest `app.py`, `app_registry`, `MORPHEUS_DEFAULT_APPS` /
`MORPHEUS_EXTRA_APPS` / `MORPHEUS_APPS_DIR`, and the SDK door `morpheus.app`.
**Two things deliberately still say "plugin"** and are not drift: the
directory `plugins/installed/<name>/` and the base class `MorpheusPlugin`
(exported as `Plugin`) — moving the directory would rewrite ~2,000 import
paths and both CI boundary baselines, so it is a separate, opt-in change.
`MORPHEUS_EXTRA_APPS` reads the old `MORPHEUS_EXTRA_PLUGINS` env var as a
fallback, because that name lives in the deployment environment, not the repo
— renaming the read alone would silently drop a live deployment's extra apps.

**Landmine — two lists with the same name WILL drift, and the looser one
wins where it's read.** `PROTECTED_PLUGINS` ("apps that soft-brick if
disabled") existed twice: in `core/safety.py` (gating Linda's `plugins.disable`
/ `plugins.toggle` tools) and as a frozenset inside `admin_dashboard` (gating
the merchant's toggle). They diverged — the dashboard refused
catalog/orders/payments/morpheus_brain while the AI path allowed all four, so
the *automated* path was looser than the human one, and the tool's own comment
claimed `orders` was covered when it wasn't. There is now one gate,
`core.safety.is_plugin_protected()`, read by both surfaces; an app may also
declare `protected = True` in its own manifest, and that is **one-way** — a
manifest can add protection, never remove it, because an `app.py` is
AI-editable and `core/safety.py` is in `FORBIDDEN_PATHS`. Same rule for
`system = True` (hide from the Apps catalogue). When you add a
classification about apps, put it on the app or in core — never a second list
in a shell. Guarded by
`admin_dashboard/tests/test_disable_guards.py::ProtectedAppGuardTests`.

**A plugin owns all of its own code.** Every file a feature needs — views,
URLs, templates, dashboard pages, settings panels, GraphQL, beat tasks —
lives under `plugins/installed/<name>/`. It appears *elsewhere* by
**contributing**, never by editing another layer's files:

- Storefront surface → a `StorefrontBlock(slot=...)` (or the plugin's own
  URL + template), **not** an edit to `plugins/installed/storefront/` or
  `themes/`.
- Dashboard page / nav entry / settings form → the plugin's dashboard-page,
  nav, or `contribute_settings_panel` contribution, **not** an edit to
  `plugins/installed/admin_dashboard/`.
- Behaviour inside another plugin's flow (cart total, order lifecycle) → a
  `core.hooks` subscriber, **not** an import of its models or an edit to
  its views.

**Two litmus tests:**

1. **Delete** `plugins/installed/<name>/` → the feature is gone with no
   dangling view, URL, template, or import in core, the theme, or a
   sibling plugin.
2. **Disable** the plugin (toggle it off) → *every* surface it added —
   sidebar nav entries, settings pages, storefront blocks, account tiles —
   **disappears from Morpheus OS.** A surface that survives a disable was
   hard-coded in the wrong layer. Contributed surfaces are rendered only
   while the plugin is enabled; hard-coded ones are not, which is the bug.

If adding feature X made you edit a file outside `plugins/installed/X/`,
that edit belongs back inside X as a contribution.

**Disable-test enforcement:** hardcoded plugin nav links in the dashboard
shell must sit behind `{% plugin_enabled "<plugin>" %}` so they vanish on
disable; `admin_dashboard/tests/test_disable_guards.py` fails the build if a
plugin link is added unguarded. (loyalty's `/account/points/` and the
payments settings panel — the old known debt — are now properly contributed.)

**Landmine — `deactivate()` does NOT unwind `ready()`-wired hooks; the bus
gates on active-state instead.** A runtime plugin toggle (`registry.deactivate`)
drops the plugin's *contributions* (StorefrontBlock/DashboardPage/SettingsPanel)
but deliberately leaves its `register_hook` subscriptions in place (so a
re-enable doesn't double-register them). The safety net is `core/hooks.py`:
`fire`/`filter` skip any handler whose owning plugin is inactive (ownership is
tagged via `Plugin.register_hook(..., plugin=self.name)`; the registry wires the
`is_active` predicate through `hook_registry.set_active_check`). **Consequence:**
a surface contributed through a hook (`PRODUCT_FORM_CARDS`, `DASHBOARD_KPIS`,
`ACTIVITY_FEED`, `ACCOUNT_SUMMARY_FIELDS`, …) is disable-safe *for free*. But a
shared shell (`admin_dashboard`, `storefront`, a theme) that **hard-imports an
optional plugin to render a surface** bypasses the bus entirely, so that surface
survives a disable — the ADR 0023 bug (book_product's product-form card shipped
this way; fixed by moving it to `PRODUCT_FORM_CARDS`/`PRODUCT_FORM_SAVED`).
Render an optional plugin's surface via its hook/contribution, never a
try/except import (a `try/except ImportError` guards *absence*, not *disable* —
a disabled plugin is still importable). Guarded by
`core/tests/test_hook_disable_gating.py`. (bookvault — the old still-open
example — is repaid: its list column + fulfilment card + bulk action arrive
via `PRODUCT_LIST_COLUMNS` / `PRODUCT_FORM_CARDS`, guarded by
`test_disable_guards.py::ProductShellContributionGuards`.)

**Landmine — a runtime toggle that refreshes the WRONG URL module is a no-op
that only misbehaves after the next restart.** `registry._refresh_urlconf`
rebuilt `plugins.urls`, but since the ADR 0022 split the root urlconf includes
`plugins.chrome_urls` + `plugins.storefront_urls` — so a runtime *disable*
never reached the live resolver (the plugin's endpoints kept serving), and
`activate()` refreshed only on first wiring and *before* `_active.add`, so a
runtime *enable* never mounted URLs either. Everything looked fine until the
process restarted with the plugin disabled — then `get_urlpatterns` skipped its
routes at import and any template still reversing one of them (dot_books'
`{% url 'seo:journal_rss' %}` in `<head>`) **500'd every storefront page**,
weeks after the toggle. Two rules: (1) rebuild the modules the root urlconf
*actually* includes, in place, on every enable **and** disable, after the
active-set changes; (2) a shell/theme must never `{% url %}` an optional
plugin's namespace — contribute the markup from the owner (seo's feed links are
a `global_head` block now) or wrap it in `{% plugin_enabled %}`. Guarded by
`core/tests/test_registry_url_disable.py::LiveResolverDisableTests` (asserts on
the LIVE resolver, not `get_urlpatterns()` output — the earlier test proved
nothing about the resolver) and `storefront/tests/test_disable_safety.py`.

**Landmine — an update channel that verifies the manifest but not the bytes
is theatre.** The per-app/theme channel (`core/component_updates.py`) trusts
an entry only through the chain *signed manifest → entry `sha256` → streamed
artifact hash → member-by-member archive inspection → `tarfile` `data` filter →
marker file (`app.py`/`theme.py`) → `migrations/__init__.py` present*. Every
link fails **closed**: no checksum → refused before download; mismatch → file
deleted; a symlink, `..`, second top-level dir → archive untouched. It also
refuses to overwrite anything that ships with core (`MORPHEUS_DEFAULT_APPS` or a
git-tracked path — those are versioned by `MORPHEUS_VERSION` and would fork the
tree) and anything under `core/safety.py`'s protected paths. When extending it,
keep the order and keep it fail-closed; a mutation test that removes any single
guard must fail a test (`core/tests/test_component_updates.py`).

**Landmine — literal `{{ … }}` in display text is a TemplateSyntaxError, and
the page 500s for everyone, always.** `email_template_edit.html` documented
placeholders as `<code>{{ "{{ order.order_number }}" }}</code>`; the lexer cuts a
variable token at the FIRST `}}`, so the whole editor 500'd from 2026-06-13 to
v0.45.0 — no test rendered it, and the surrounding disable-safety test had to be
written *around* it. Wrap literal template syntax in `{% verbatim %}…{% endverbatim %}`,
and compile every changed template with `get_template()` before shipping
(sqlite tests + `manage.py check` do not catch this).

**Landmine — a new sign-in path silently bypasses MFA.** Staff second factor
(staff_mfa) hangs off the `AUTH_SECOND_FACTOR` filter, fired in
`core/auth/views.py:otp_verify` *after* email-OTP and *before* `login()`. Any
**other** login path — an allauth/SSO/social provider — does NOT fire that hook
(allauth calls its own `login()`), so it logs the user in single-factor. A new
sign-in path MUST itself run the gate (`staff_mfa.services.second_factor_response`
→ `ImmediateHttpResponse` to the TOTP challenge), which is exactly why staff_sso
interposes in its `SocialAccountAdapter.pre_social_login`. Don't add a login route
without it.

**Landmine — the staged-writes approval exemption is gated on `Tool.supports_staging`,
not on `context['staged']` alone.** `AgentRuntime._dispatch_tool` skips the approval
gate in staged mode **only** for tools that declare `supports_staging=True`
(`core/agents/tools.py`). That flag is a contract: it means "when
`context['staged']` is set I record an `OpsProposal` instead of executing"
(the `_is_staged`/`_stage` path in `core/assistant/tools/ecommerce_writes.py` +
`metafields.set`). **Set it *only* on a tool that actually stages** — putting it on
a tool that executes directly lets that tool run under a staged routine with **zero
approval** (the S1 hole; a blanket `context['staged']` exemption once reopened it for
`catalog.delete_product`/`orders.mark_refunded`). Conversely, a `requires_approval`
tool that *does* stage but forgets the flag just double-gates (fails safe, but breaks
the staged-routine UX). Guarded by `core/agents/tests/test_staged_gate.py`.
**Linda enforces the same contract** — `core/assistant/gates.py:gate_reason`
mirrors the Worker's chain (scope → budget → deadline → approval), so the
`supports_staging` rule above applies identically to her.

**Landmine — an LLM-supplied argument is NOT consent.** Linda's write tools take
`confirmed=True` (+ `hard_gate_ack`/`echo` on the destructive tier), and their
docstrings once claimed this meant the user had approved. It didn't: *the model*
writes those arguments, so anything Linda merely **reads** — a product
description, a log line, a customer note, a fetched page — could induce her to
set them on the first call. Consent now lives in the kernel
(`core/assistant/consent.py`): the first attempt is refused and a pending consent
is recorded against `sha256(tool + canonical args)`; it is spent only when the
**human's own next message** (a `role='user'` turn — the one thing injected
content can never be) reads affirmative, and the grant is single-use and
argument-bound. Negation always beats affirmation ("yes, but not that one"
denies). **The human message must also postdate the proposal** (v0.64.0): without
that, "set the price to 20, ok?" approved itself — the first attempt is refused
and recorded, and a retry in the same turn found the turn's own "ok" waiting.
Every caller passes `human_message_at`; the edge reads it from the stored message. **Never gate a new write tool on an argument alone** — add
`requires_approval=True` and let the kernel gate it. Refused attempts are
audited, so a blocked injection leaves a trace. Guarded by
`core/assistant/tests/test_enforcement.py`.

**Landmine — moving the agent loop OUT of process moves it out of every gate,
and the switch reads like a performance choice.** Janus (the store agent; Linda
is brand only) runs its own loop in a subprocess (`core/assistant/janus_engine.py`)
and reaches the store's tools over MCP, so the in-process gates never see its
calls. A standing MCP token is authentication, not per-action human consent, and
the edge could not tell which merchant or conversation a call belonged to. Since
v0.64.0 each turn carries a **signed turn token** (`core/assistant/turn_identity.py`,
prefix `lt1.`, env `LINDA_TURN_TOKEN`, referenced from the config as
`${LINDA_TURN_TOKEN}` so nothing secret is on disk), and `/mcp/admin/v1/` runs
**the same gate chain** as the loop (`core/assistant/gates.py`) via
`agent_mcp/linda_turn.py`: Linda's scope profile (never the token's), the mode
re-resolved against the user on every call, consent spent only by the
conversation's latest `role='user'` message, and an `assistant.tool_write` audit
naming the human. **Never re-add a static Linda MCP token** — its
`approved_tools` grant is the standing-consent hole. A turn token authenticates
nothing but that endpoint: `apply_bearer_user` (GraphQL) treats it as invalid.
When you change a gate, change `gates.py`; a second copy drifts and the looser one
wins. Merchant knobs (on/off, pinned provider, tool-step cap, turn time limit,
standing instructions, bundled skills) live on Settings → AI → Janus — the protected
`janus` app — and core reads them only through `core/assistant/janus_settings.py`
(cross-process fresh, clamped, fail-soft to defaults); the timeout never exceeds
55s whatever is stored. The page's slug is `engine`, not `settings`:
`/dashboard/apps/<app>/settings/` is the legacy settings deep link and silently
wins the route. Remaining fences: tests force `'legacy'` and must never spawn a real model;
YOLO/`LINDA_JANUS_AUTO_APPROVE` stays **off**; the child gets an env
**allowlist** (`_child_env`), never `os.environ.copy()`. A non-zero exit is a failure even when stdout carried
partial text. **The turn limit may exceed `GUNICORN_TIMEOUT` (60s) only because the
chat streams** (v0.68.0): the subprocess waits in a thread (`iter_janus_turn`) while
the SSE generator sends `progress` every 5s and tool events from the rows the MCP
edge stores — gthread workers heartbeat on their main loop, and the steady bytes
hold Cloudflare/nginx. A caller that does not stream (the settings page's connection
test) must pass a short `timeout_s`. Everything that touches the database (settings,
hydrate, harvest) stays on the request's thread: the worker thread has its own
connection and cannot see the request's. Also from v0.68.0: the system prompt is
stable per conversation (Janus places it ahead of the transcript, so a per-message
prompt defeats the prompt cache) — page, memories and knowledge travel with the
message; the history recap is sent only when a fresh Janus session starts
(`--resume` already carries the transcript), and sessions rotate after
`SESSION_MAX_TURNS` or `SESSION_IDLE_S` so context stays bounded; token use is read
from the session row in the home's `state.db` and counts toward `spend_cap_daily`. Bundled ecommerce skills live in
`core/assistant/janus_skills/` and are wired via `skills.external_dirs` in the
per-conversation Janus home. **Four CLI traps shipped live in v0.63.0 and each
looked fine in tests** (v0.63.1): (1) without `-t`, `janus chat` loads its
default 56-tool `janus-cli` set — terminal, `write_file`, `execute_code`, browser
— as the user that owns `/app` and can read the web process's env via `/proc`,
so `TURN_TOOLSETS` (store MCP server + `skills`) is the real boundary, not the
env allowlist; (2) bare `--continue` resumes the newest `cli`-sourced session,
never `linda`, so every follow-up exited 1 — store the stderr `session_id:` and
`--resume` it; (3) `janus-agent` without the `[mcp]` extra has a silently inert
MCP client, so the store had zero tools; (4) provider `auto` routes to OpenRouter
whenever `OPENAI_API_KEY` exists and never sees a dashboard-stored key — pin
`--provider`/`-m` from `core.agents.provider_registry` (`_provider_wiring`).
A fifth hid longer (v0.64.1): conversation homes lived under `BASE_DIR`, and `/app`
is root-owned in the image, so **every real turn raised PermissionError** — while
the prod smoke passed, because it patched the home to a temp dir. Homes now default
to a private temp dir or `LINDA_JANUS_HOME` (never `/app/media`: publicly served,
and a home holds `state.db`). **A smoke test that patches the path under test proves
nothing about that path; smoke the unpatched call.** Also: `HOME` is set to the
conversation home, and `MAX_TOOL_TURNS` caps iterations (~7s each on prod) so a
turn answers inside the timeout instead of exploring until it is killed. Each home
also gets Linda's `SOUL.md` (Janus seeds "You are Janus Agent" otherwise) and a
`.no-bundled-skills` marker (Janus copies ~70 general-purpose skills into every
home and its prompt says she MUST load a relevant one first); the config pins
`agent.reasoning_effort` (merchant setting, default `low` — a reasoning model's
provider default is `high`) and `api_max_retries: 1`. Janus prints status lines to
stdout even under `-Q` and exits 0 on an empty reply, so `_strip_notices` removes
them and an empty or `(empty)` answer is a failure, not a blank bubble. **Janus's
background review thread silences itself with `contextlib.redirect_stdout/stderr`,
which swaps the streams for the whole process**: every 10th message or tool step
the reply and `session_id` went to /dev/null and the merchant got "no reply"
(v0.68.0, live). The config sets `memory.nudge_interval` and
`skills.creation_nudge_interval` to 0, and a clean exit with no output recovers the
reply from the home's `state.db` (`_recover_reply`).
Guarded by `core/assistant/tests/test_janus_engine.py`, `test_turn_identity.py`
and `agent_mcp/tests/test_linda_turn.py`.

**Landmine — what Janus learns lives in files a redeploy deletes, and "add a disk
volume" only fixes it on one host.** Janus writes its memory notes, the skills it
authors and its lessons under `JANUS_HOME`, a temp dir per container. Morpheus is
open source and must behave the same with or without Coolify, so the durable copy
is the database (`JanusLearning`, `core/assistant/janus_learning.py`): each turn
**hydrates** the home from the DB, runs, then **harvests** only the diff — in a
`finally`, so a note saved before a timeout is kept. Four rules: (1) harvest
**merges**, because two conversations learn at once — notes entry by entry,
lessons by id, the daily journal by appended text, other files turn-wins and
delete-only-if-unchanged; a whole-file write would erase the other conversation;
(2) a hydrated `MEMORY.md` must be exactly `"\n§\n".join(entries)` — Janus treats
any file that doesn't round-trip as externally edited, backs it up, and **refuses
every later memory write**; (3) only agent-written text documents are kept —
bundled skills (`skills/.bundled_manifest`), dot-dirs, symlinks, scripts and
`state.db` never are, and more than `MAX_NEW_FILES_PER_TURN` new files in one turn
means the home was misread, so those skill files are dropped; (4) `USER.md` is
per staff member (`scope='user:<pk>'`), never shared — and Janus also journals
USER changes into the shared `memories/daily/*.md`, so harvest keeps only
`**MEMORY**` journal entries, and deleting a note on the page scrubs it from the
journal too (`recall_memory` searches the journal; v0.66.0 shipped without both). The generated config sets
`skills.guard_agent_created: true` (Janus's `auto` default leaves the skill scanner
**off** under `janus chat -q`), `inline_shell: false`, and `curator.enabled: false`
(it archives skills into a dot-dir that isn't kept). Linda's MCP turns no longer
see `memory.remember`/`memory.forget`/`memory.recall`: a second store would split
what she learns. Learned content can steer but never authorize — store writes still need the
merchant's own "yes" at the edge — and the merchant reviews and deletes it on
Settings → AI → Janus. Guarded by `core/assistant/tests/test_janus_learning.py`.

**Landmine — an agent that can't find the right tool doesn't say so; it explores
until it times out.** Linda's hand-picked tool list hid inventory, SEO and catalog
writes (and her scope profile hid the rest) while exposing `db.*`, `run_python` and
`platform.capabilities`; Sales/Support/Ops listed one tool because modes filtered
on scopes the read tools don't declare. Live, 5 of 11 everyday questions timed
out while she browsed internals — and an SEO question quietly spawned a background
Worker that burned 133k tokens. Now a turn's catalogue is every registered tool
inside `gates.LINDA_SCOPES` (store domains) minus shopper tools, duplicates and
internals (Developer mode only) — `agent_mcp/linda_turn.py:catalogue`. Widening
the catalogue exposed Worker tools that write **without** `requires_approval`
(their flags assume the Worker's own approval queue), so at the edge **every
write needs the merchant's yes** (`needs_consent`: approval flag, any write scope,
plus `delegate.spawn_workers` / `meta.sync_audience`). Also: the consent
fingerprint ignores the model's own `confirmed`/`hard_gate_ack`/`echo` (a yes then a
`confirmed=True` retry used to be refused again), and the prompt and skills may
name only tools in the catalogue. Guarded by
`agent_mcp/tests/test_linda_turn.py::LindaCatalogueTests` (coverage per mode,
handler-required ⊆ schema `required`, prompt/skill references resolve).

**Landmine — two plugins registering the same agent-tool NAME let load order
decide which one runs, and the loser might be the one with `requires_approval`.**
`agent_registry` was last-writer-wins on a name clash (warn + overwrite), so
`inventory.adjust_stock` resolved to agent_core's UNGATED twin instead of the
inventory plugin's `requires_approval=True` original — the MCP/Linda approval
gate silently never fired on stock writes. Tool **names are a STABLE API surface**
(API_STABILITY) and are single-owner: `register_tool` is now first-owner-wins and
RAISES under DEBUG/tests on a cross-plugin duplicate (a deliberate test swap passes
`replace=True`); the collision baseline is empty and must stay empty. When two
plugins want the same concept, one renames — `analytics.summary`/`top_products`
(order-derived) stay with **orders**; the analytics plugin's rollup pair is
`analytics.traffic_summary`/`analytics.top_viewed_products`. Guarded by
`core/agents/tests/test_registry_collisions.py`. (v0.55.0)

**Landmine — in the MCP scope layer, ABSENCE means wildcard, so every fail-open
default reads as full access.** `token_scopes()` treats a missing `mcp_scopes`
key as `{'*'}` (back-compat for unconfigured/legacy tokens). That one decision
turns three ordinary bugs into privilege escalations: (1) the token dashboard's
`_load_entries` dropped `mcp_scopes`/`approved_tools` on the normalise-and-resave
round-trip, so *creating or revoking any token* silently promoted every other
token to wildcard; (2) a malformed value (a hand-edited bare string, an int) hit
the same wildcard branch; (3) `apply_bearer_user` stashed scopes *after* fallible
work, so a half-failed resolution fell through to a wildcard default. Rules:
preserve the whole entry dict across a save; a present-but-garbage scope value
fails **closed** (`set()`), only a truly absent key inherits wildcard; stash
deny-first the moment a token is presented (but leave a *no-token* request
untouched, so session-staff keep the is_staff fallback). And a scope a tool
declares but that is **missing from `AVAILABLE_SCOPES`** can't be granted in the
dashboard, so the token falls back to wildcard — a subset test
(`test_scopes.py::ScopeVocabularyTests`) now asserts `{tool scopes} ⊆ vocabulary`.
Mirror rule on the GraphQL side: a Bearer token resolves to a shared
`is_staff=True` service user, so `has_scope` must authorize a token against its
OWN stashed scope set and never fall through to the is_staff shortcut (that
shortcut is for genuine session-staff, who carry no token). (v0.55.0,
`docs/plans/mcp-graphql-hardening-2026-08.md`.)

**Landmine — a `migrations/` dir without `__init__.py` is invisible to Django,
and ONLY production notices.** Five plugins (brand_kit, lookbook, media_3d,
rails, smart_shipping) shipped a `0001_initial.py` in a non-package directory:
`showmigrations` reported *"(no migrations)"*, `django_migrations` had zero rows,
and **their tables were never created on prod** — while every local test passed,
because Django creates tables directly (syncdb-style) for apps it believes have
no migrations. `makemigrations --check` was clean for the same reason. So the
usual gate (green tests + clean check) proves nothing here. **When adding a
plugin with models, verify `plugins/installed/<name>/migrations/__init__.py`
exists** — `for d in plugins/installed/*/migrations; do [ -f "$d/__init__.py" ]
|| echo "$d"; done` is the whole check. When repairing one, note that
never-applied migrations can be **regenerated** rather than patched forward
(check `django_migrations` first) — that avoids an `AlterField` on a PK, the
class that 503'd prod twice.

**Landmine — a settings field with no consumer is a lie, and the merchant can't
tell.** Three shipped: `maintenance_mode` (flip it, the shop stays open —
a control shaped like a safety mechanism that does nothing), brand_kit's design
tokens (the block read `tokens.*` that no view/tag/processor ever supplied, so
every palette rendered as the hardcoded default), and store identity
(`core/context_processors.py` read `STORE_NAME` from **env** while the merchant
edited a `StoreSettings` row). When adding a settings field, wire the consumer
in the **same change**, or don't add the field. The cheap check:
`grep -rn '<field_name>' --include='*.py' --include='*.html'` — if the only hit
is its own declaration, it does nothing. Still-dead knobs are inventoried in
`docs/plans/` (caching page, `products_per_page`, theme config). Guarded by
`storefront/tests/test_identity_maintenance.py` +
`brand_kit/tests/test_tokens_render.py`.

**Landmine — two plugins can register the same URL, and the loser is silent.**
`get_urlpatterns` mounts in `_topo_sort` order and **first registrant wins**, so
`newsletter` beat storefront to `/newsletter/subscribe/` and `pwa` beat it to
`/sw.js` — the losing views became dead code, taking their side effects with
them (the CRM lead capture simply stopped happening, with nothing to indicate
it). Also mind `<str:token>` swallowing a sibling literal: `nps/<str:token>/`
registered before `nps/thanks/` made every NPS submit render "link expired"
(410). **Order literals before converters, and when adding a root-level route,
grep for the path first.** Recover a lost side effect on the bus (a hook the
owner fires) rather than in a view that may be shadowed.

**Landmine — never infer entitlement from a status string.** A perk gate that
reads `subscription.state in ('active','trialing')` trusts whatever wrote that
string. The storefront subscribe view wrote `'active'` with **no payment leg at
all**, so any logged-in customer could POST `/membership/subscribe/` and take
the member discount off every order forever, having paid nothing (v0.40). The
rule: gate on **evidence the money moved** — plan is free, a provider
subscription exists, or a paid invoice is on file — expressed in ONE place
(`subscriptions/membership.py:entitling_subscriptions`) that every perk surface
reads. Evidence-based gating also retroactively de-entitles rows already minted
the wrong way, with no data migration, and stops the next writer of `'active'`
from silently reopening it. The same shape applies to any future entitlement
(seats, tiers, feature flags). Guarded by
`subscriptions/tests/test_entitlement.py`.

**Landmine — a reservation needs an expiry, not just a release path.** Stock is
reserved by the fail-closed `ORDER_RESERVE_STOCK` gate and released on
`ORDER_CANCELLED` — but nothing *cancelled* an unpaid order, so an abandoned or
card-declined checkout held its units forever (a failed card only marks the
transaction FAILED). `orders.expire_pending_orders` (beat, merchant-configurable
window, `0` = off) closes the loop by cancelling stale unpaid orders, which lets
the existing subscribers do the release. **Re-check payment state under a row
lock before cancelling** — the gap between selecting and cancelling is exactly
where a late webhook lands, and cancelling a paid order is far worse than
leaving one stranded. Note the two-layer hold: a Redis cart-hold at add-to-cart
*and* the DB reservation at checkout; `create_from_cart` must `release_cart()`
once the DB reservation takes over or every completed order double-holds until
TTL. Guarded by `orders/tests/test_expire_pending.py`.

**Landmine — a hook with subscribers but no producer is invisible dead weight
(and arms a bug).** Three shipped this way: `PRODUCT_CALCULATE_PRICE` (2
subscribers, 0 callers — every merchant pricing rule silently inert),
`PAYMENT_CAPTURED` (merchant webhook fan-out + analytics subscribed, nothing
fired), and `orders.on_payment_captured`, which was *worse than dead*: the
gateways already confirm directly, so the day anyone fired the event it would
re-run a `source='pending'` transition and raise on every confirmed order. When
adding an event, wire **both ends** in the same change, and when you find a
never-fired event, decide deliberately — fire it or delete the subscriber, never
leave it armed. `grep -rn EVENT_NAME | grep -c fire` is the cheap check.

**Landmine — a price seam must fire on BOTH the displayed and charged price.**
`PRODUCT_CALCULATE_PRICE` is applied in exactly two places — catalog's GraphQL
`Product.price` (display) and orders' `_resolve_unit_price` (charge) — and both
go through `core/pricing.py:apply_price_filter` so validation can't drift.
Fire only one and the shopper is quoted $8 and billed $10. The helper lives in
**core** because a shared helper in either plugin would be a plugin→plugin
import. It is fail-soft in every direction (non-`Money`, negative, currency
swap → keep the original): a merchant's pricing rule is untrusted input on the
money path, and a currency swap would breach the single-currency cart invariant.
Guarded by `core/tests/test_price_filter.py`.

**Landmine — SEO markup written into a template is invisible when it's wrong.**
As of v0.46 the storefront `<head>` is a *document*, not markup: core seeds
`HeadDocument` (`core/head.py`), fires `STOREFRONT_HEAD`, and the seo app fills in
title/description/canonical/robots/OG/Twitter/hreflang/pagination/JSON-LD. A theme
calls **`{% storefront_head %}` once** and declares `head_contract = 1`; apps
contribute through `SEO_RESOLVE_PAGE` / `SEO_JSONLD_GRAPH` / `SEO_SITEMAP_SOURCES`
/ `SEO_ROBOTS_RULES`, never by emitting tags. Entries are **keyed**, so a second
writer replaces rather than duplicates — which is the whole point: the old
per-tag arrangement shipped two `og:type` tags on every PDP, two `WebSite` nodes
on most pages, the brand appended twice on category/collection/journal titles,
and `/search/` with **no `<title>` at all** (the theme's title lived inside the
`{% block seo %}` that page overrode to force `noindex`). None of that is visible
in a browser. Guards: `themes/test_head_contract.py` (one title/canonical/robots/
JSON-LD per page kind, no hardcoded brand, survives a seo disable) and
`seo/tests/test_head_parity.py` (a recorded profile of every page type; re-record
deliberately and review the diff — a shrinking profile is the bug). Corollaries:
a page title is the **clean page name**, the brand is applied at render from
settings (ADR 0007) — never append the shop name in a view; and machine endpoints
(`robots.txt`, `sitemap*.xml`, `llms.txt`, `.well-known/*`) must register with
`surface='chrome'`, or `i18n_patterns` publishes a second copy of each per
language (`/fr/robots.txt`). ADR 0036.

**Landmine — when two tables hold the same field, "which row wins" is the wrong
question; "which value did a human choose" is the right one.** Product SEO lived
in 13 native `catalog.Product` columns *and* in the generic `SeoMeta` overlay,
and `SeoMeta` won. But `autofill_meta_for` mints a `SeoMeta` row for **every**
product on creation, seeded with the product's own **name** — so a merchant who
typed a meta title into the product form saw the storefront go on rendering the
plain name. Their edit was stored, resolved, and discarded, and every layer
looked correct in isolation. `resolve_meta` now checks `SeoMeta.auto_filled`: a
platform-generated guess loses to a value a human typed, whichever table it sits
in (`services/meta.py:stored()`, mirrored in `services/panel.py` and
`manage.py seo_backfill_meta`). **When you consolidate storage, mark what the
platform generated** — otherwise the merge silently prefers the guess. Two
corollaries that cost a release each: (1) removing a form's template block
without removing its `required=False` form fields **blanks the columns on the
next save**, because the field cleans to `''` and the old save loop assigned it
unconditionally — the template, the form fields and the save must go in one
change; (2) an **empty `FileField` is falsy but raises `ValueError` on `.url`**,
and a fail-soft card collector turns that into a feature that is simply absent,
with a 200 and nothing in the page to say why. Guarded by
`seo/tests/test_panel_contributions.py`.

**Landmine — `QuerySet.update()` and `QuerySet.delete()` skip `save()` and
`post_save`, so anything hung off them silently doesn't run.** The redirect
resolver reads a compiled ruleset out of the cache; the dashboard edited rows
with `Redirect.objects.filter(pk=…).update(…)`, which normalised nothing,
collapsed no chains, and — the part that matters — never dropped the cache, so a
merchant could edit a rule and watch the old one keep serving. Invalidation
therefore hangs off `post_save`/`post_delete` in `seo/signals.py` (which *do*
fire for a queryset delete) and every write path uses an instance `save()`.
Two more redirect rules worth keeping: a `to_path` is **staff- and
assistant-writable**, so it must be validated as site-relative before it reaches
a `Location` header (an open redirect turns the store into a phishing hop), and
`LocaleMiddleware` leaves the language prefix in `path_info`, so a rule stored as
`/old/` never fires for `/fr/old/` unless the matcher strips it. Guarded by
`seo/tests/test_redirects_engine.py`.

**Landmine — structured data is a PUBLIC CLAIM, and defaulting one is lying at
scale.** The Product offer used to carry a full `shippingDetails` +
`hasMerchantReturnPolicy` assembled inside `seo/services/jsonld.py` from
`PluginConfig` keys that **no settings screen ever wrote** (`shipping_fee_amount`,
`free_shipping_over`, `handling_days_*`, `transit_days_*`, `return_days` — none
were in `get_config_schema`). Every store therefore published the same invented
policy, and because the free-shipping threshold defaulted to the truthy string
`'0'`, **every product page on every store advertised free shipping on
everything** while the cart charged whatever the shipping app said. Two more of
the same shape: `availability` was computed by a stock query behind an ORM-only
branch, so the PDP — which renders a GraphQL dict — declared `InStock` for
sold-out items; and `aggregateRating` aggregated *all* reviews while the `Review`
nodes filtered to approved, advertising a rating built from reviews the page does
not show. The rule: **a property whose value you cannot source from the app that
owns it must be OMITTED, not defaulted.** A missing recommended property costs a
Search Console warning; an invented one is a Merchant Center policy violation and
a promise checkout will break. Shipping and returns are contributed by their
owners now (`shipping/seo_graph.py`, `returns_portal/seo_graph.py` on
`SEO_JSONLD_GRAPH`), availability comes from `inventory.product_availability`
through the one shared vocabulary in `plugins/feed_mapping.py`, and the head
parity profile SHRANK on purpose — the one case where that is not the bug.
Guarded by `seo/tests/test_offer_claims.py`, which asserts both directions
(configured → published and matching; unconfigured → absent).

**Landmine — an SEO gap is what the page RENDERS empty, never what one column
holds; and a collector nothing ever calls fails silently for months.**
`seo_gap` scanned columns instead of the resolved head, and got it wrong three
ways: it filtered `cms.Page` on a `meta_description` column the model has never
had (it has `excerpt` + a `metadata` JSON blob), so **107 of 107 nightly runs
raised FieldError from 2026-06-01 to v0.68.3** — after emitting the earlier gap
classes, so the job just showed red and the page gaps were never collected; it
reported a blank `Product.og_title` as debt though `og:title` renders from the
title when blank (`_helpers.py:to_html`), which is 648 of 861 live products of
permanent debt **no healer can repair**; and it read only the native description
column while `resolve_meta` prefers the `SeoMeta` overlay. Two rules: derive a
gap from the same fallback chain the `<head>` uses
(`seo/pages/resolve.py:_description_from_object`), and **call `run()` in a
test** — nothing ever had, which is the only reason a three-month-dead nightly
job stayed invisible. Guarded by
`core/self_improvement/tests/test_collectors.py::SeoGapCollectorTests`.

**Landmine — a deferred djmoney field raises `KeyError`, which `getattr`'s
default does NOT catch, and one unguarded read can cost a whole node.** A view
that loads a product with `.only()` leaves the unselected columns absent;
touching one raises `KeyError` out of djmoney, not `AttributeError`, so
`getattr(product, 'compare_at_price', None)` **raises**. The PDP defers both
`price` and `compare_at_price`. A single unguarded read inside `product_jsonld`
therefore raised, the graph's per-node guard caught it, and the product page
shipped with **no Product node at all** — a total loss of the page's structured
data, behind a 200 and nothing above debug in the logs. Read money fields
through `_safe_field` (checks `get_deferred_fields()` first, then catches), and
remember the general shape: a fail-soft wrapper turns "this raised" into "this
feature is silently absent", so the guard has to be inside, not outside. This
has now bitten `price` (v0.46), `compare_at_price` (v0.49), and the
SeoTemplate token reader (v0.54.1 — the pattern silently skipped every live
PDP while every ORM-loaded test stayed green, because only the real view uses
`.only()`; test the deferred load). Guarded by
`seo/tests/test_product_markup.py::DeferredFieldTests` +
`test_templates_engine.py::GrammarTests::test_deferred_money_fields…`.

**Landmine — a canonical that echoes a query parameter the view never read
mints one indexable page per value, forever.** Two independent causes produced
the identical live symptom on `?page=N`: Django's paginator **clamps** an
out-of-range number back to page 1 (so every paginated listing served page 1
under any number past the end), and a listing with **no paginator at all**
ignored `?page=` entirely while the canonical echoed it anyway. Both answered
`200` with page 1's products under a canonical naming *itself* — an unbounded
family of duplicates, one per integer, each claiming to be the original.
`/shop/?page=999` was doing the second on prod, which is why no view-level fix
could have reached it: `booking_marketplace` owns that route and never
paginated. So the rule is at the canonical layer — `?page=` is trusted only when
a real paginator (`SeoPage.page_obj` with a `.number`) says so — *and* at the
view layer (`storefront/views/catalog.py:_paginate` 404s out of range; only the
storefront paginates anywhere in the tree). The corollary is general: **before
reflecting a request parameter into a canonical, confirm the view acted on it.**
Also here: never emit `noindex` together with a canonical naming a *different*
URL — a facet page saying "don't index me" while pointing at its category is two
claims about two URLs, and the no-index can carry to the target and take the
category with it. `seo/rules/params.py` keeps no-indexed parameters in their own
canonical for exactly that reason; policy is one `IndexRule` row per parameter
(`consolidate` | `noindex` | `allowlist` | `block`, `param*` wildcards), compiled
and cached, invalidated on write. `page` is reserved and takes no rule.
Guarded by `seo/tests/test_index_rules.py` + `test_pagination_policy.py`.

**Landmine — a `StorefrontBlock` whose slot no template renders is silent.**
The plugin is enabled, its tests pass, its block renders fine in isolation — and
the merchant sees nothing, with no error anywhere. This had happened four times
over by v0.37 (`global_head`, `checkout_extra`, `pdp_below_gallery`,
`account_summary_extra` — eleven plugins invisible, including brand_kit's design
tokens never reaching `<head>`). Adding a slot means adding **both** the
contribution and a `{% storefront_blocks "<slot>" %}` emit. Enforced by
`core/tests/test_slot_parity.py`, which reads the **runtime registry** — never
grep `app.py` for slots, because dynamics registers one per `SLOT_CHOICES`
entry inside a loop and a text search misses all of them. A slot the active theme
deliberately declines (dot_books drops `home_above_grid`; `journal` is an
alternative whole-post renderer) goes in `_INTENTIONALLY_UNRENDERED` **with a
reason**, and a merchant-selectable/auto-provisioned slot must always render
(Autopilot defaulted to a dropped slot, so every new store got an invisible
block). Also: assert a **contribution-specific marker** when testing a render —
`'<style' in head` passes on the theme's own CSS and proves nothing.

**Landmine — a tender is not a discount: refunds must re-credit it.** Gift cards
and loyalty points are folded into `Order.discount_total`, and
`RefundService._compute_refund` nets them back **out** of the cash refund (the
shopper is repaid only the cash they paid). So a refund/return that doesn't
*also* re-credit the tender silently keeps it — which is exactly what shipped
until v0.36, because both plugins subscribed only `ORDER_CANCELLED` (whole-order
void) and not `PAYMENT_REFUNDED`. Any new tender type must subscribe
`PAYMENT_REFUNDED` with a **prorated** (`refund.amount / order.total` — cash and
tender are shares of the same returned goods), **idempotent-per-refund** credit,
capped so successive partials can never return more than was spent. A wholly
tender-paid order has no cash denominator — log for manual handling rather than
guessing. Guarded by `{gift_cards,loyalty_points}/tests/test_refund_recredit.py`.

**Landmine — merchant agent guardrails read config *cross-process fresh*,
enforce at fixed seams, and the USD spend cap silently no-ops on unpriced
models.** The kill switch, daily run/spend caps, and per-action price/refund caps
are merchant knobs stored on `agent_core` config (the "Agent guardrails" settings
panel) and read through **one** core module — `core/agents/guardrails.py` — so
every enforcement site imports from *core*, never plugin→plugin. Three traps:
(1) A plugin's `_config_cache` is **per-process**; a celery worker would never
see a switch a merchant flips from the web dashboard, so `guardrails._read`
**invalidates the cache before every read** (one indexed query — cheap next to a
provider call). Don't "optimize" that away. (2) The USD `spend_cap_daily` sums
*estimated* cost (`core/agents/pricing.py`), which is `$0.00` for any model not
in `_PRICES` — so an unpriced model's dollar cap **never trips**, leaving the
model-independent `max_agent_runs_daily` run-count cap as the only backstop.
The prod model (`deepseek-v4-pro`) was unpriced for exactly this reason until
v0.36; **any model a deployment can actually reach must be added to `_PRICES`
in the same change that makes it reachable** (`is_priced()` reports the gap). (3) The key names (`agents_paused`,
`max_agent_runs_daily`, `spend_cap_daily`, `max_price_change_pct`,
`max_refund_value`) are coupled by **string match** across three places — the
panel schema + `get_config_schema` in `agent_core/app.py`, the accessors in
`core/agents/guardrails.py`, and `compliance.py:_guardrail_config` — with no
shared constant; a rename silently breaks enforcement AND the AI-Act report (both
fail soft to off/empty). The kill switch aborts via `_fail` (a hard run stop),
not `_tool_back` (a per-step soft refusal); enforced off-by-default (caps `0` =
unlimited). Guarded by `core/agents/tests/test_guardrails.py` +
`catalog/tests/test_price_cap.py` + `orders/tests/test_refund_cap.py`.

**Landmine — a new LLM provider must be wired in *three* places or it silently
"isn't selected".** Adding a provider touches: (1) `core/agents/llm.py` — a
`Provider` class **and** a `_PROVIDER_CLASSES` entry; (2)
`core/agents/provider_registry.py` — `_DEFAULT_BASE_URLS` / `_DEFAULT_MODELS` /
`_ENV_KEYS` / `_ENV_BASE`; (3) `ai_assistant/app.py` — schema fields + the
`ai_provider` enum, **and** the `_AI_PROVIDERS` catalog in
`admin_dashboard/views_split/settings.py`. Miss #1 and `get_llm_provider`
returns the unconfigured mock — the dashboard shows *"No AI provider selected"*
even though the provider is offered in Settings (this shipped for apikey.fun:
config + enum existed, the class did not). Add the resolution test alongside
(`core/agents/tests/test_llm.py::ProviderResolutionTests`).

**Landmine — `CART_CALCULATE_BREAKDOWN` priority IS the money order; a *tender*
must run after tax+shipping.** The filter runs handlers lowest-priority-first
(`core/hooks.py`). Each handler sees only the fields earlier ones have set, so a
handler that reads `value['tax']`/`value['shipping']` at a priority **below** tax
(20) / shipping (30) reads **zero**. The live order is: coupon/promo (10) → tax
(20) → shipping (30) → member discount (40) → **loyalty points (45)** → **gift
card (50)** → eco_impact (60). A **discount** (reduces what's owed, may precede
tax) differs from a **tender** (pays down the *final* total): gift cards and
points are tenders and MUST cap against `subtotal+tax+shipping−discount`, so they
sit at 45/50 — the last handlers. Shipping/tax/member each *recompute*
`value['total']` from the running fields, so whoever writes `total` **last** wins;
a tender at priority 50 must recompute `total` itself (nothing after it does).
(Deep-debug #7: the gift-card tender shipped inside `promotions.on_cart_breakdown`
at priority 10 and capped against the bare subtotal — the customer overpaid the
tax+shipping and the card balance was stranded. Fixed by moving it to its owner
`gift_cards.on_cart_breakdown`@50 + loyalty 15→45.) NB tax computes from the
cart's line items, not from `value['discount']`, so a tender folded into
`discount` does **not** move the tax base — but don't assume that for a new
discount type; check `tax/services.py:compute_tax_for_cart`. Guarded by
`gift_cards/tests/test_breakdown_tender.py`.

**Convention — `format: password` settings fields are write-only.** In the
shared dashboard settings-panel renderer
(`admin_dashboard/views_split/settings.py` + `urls.py`), a JSON-schema
`format: password` property renders masked, is never pre-filled with the stored
value, and a blank submit preserves the existing secret. Never echo a stored
secret (API key, SSO client secret) back as cleartext; mark secret fields
`format: password` (guarded by `test_settings_secret_masking.py`).

**Interim disable-safety (v0.45.0): every remaining shell→optional-plugin
read is gated on `app_registry.is_active(<name>)`** — the ADR 0013 shape from
`account_credits`, applied across `storefront/views/{catalog,content,home,vendor}.py`
(book_product, metafields, product_videos, cms, crm, consent, marketplace) and
`admin_dashboard/views_split/*` + `forms/*` (cloudflare, seo, cms, ai_assistant,
ai_content, analytics, product_videos, metafields, marketing, draft_orders).
Views that only exist *for* a plugin (coupons, theme builder, video CRUD,
`orders/new`, email-template edit) return **404** when it is off. This is not
the end state — a `try/except`+`is_active` in a shell is still a shell→plugin
import (the pairs stay in the boundary baseline) — but the surface now
disappears on disable, which is what the litmus test demands. Guarded by
`storefront/tests/test_disable_safety.py` (toggles each plugin, GETs every
page, and asserts three surfaces vanish) + `admin_dashboard/tests/test_disable_safety.py`.
The right end state is still a contribution per surface (PDP gallery/facets,
journal, settings panels) — `docs/plans/boundary-debt-2026-07.md`.

**Known debt to repay (still fails the disable test):**
the storefront account *summary* is fixed — `_account_summary` is now
assembled entirely by `ACCOUNT_SUMMARY_FIELDS` subscribers (orders,
loyalty, gift_cards, digital_products) — but the dedicated account
sub-pages (orders list, credits, downloads) still query plugin models
directly. The dashboard *home page* is fixed — KPIs, panels and the
setup checklist are assembled via the `DASHBOARD_KPIS` /
`DASHBOARD_HOME_PANELS` / `DASHBOARD_SETUP_STEPS` filters and the
activity feed via `ACTIVITY_FEED` (guarded by
`admin_dashboard/tests/test_home_modular.py` +
`test_activity_feed_modular.py`), and the pulse routes now live in
ai_assistant via `register_urls` — `home.py` imports no sibling plugin.

**Core → plugin imports (wrong direction; core should never import
`plugins.installed.*`):** *fixed* — `core/emails` (cms's EmailTemplate
arrives via the `EMAIL_TEMPLATE_OVERRIDE` filter; site base URL moved to
`core/utils/site.py`), and the provider-config coupling
(`core/agents/llm.py` resolves through
`core/agents/provider_registry.py`; ai_assistant's `ready()` registers the
dashboard-aware resolver); `core/brain/signals.py` (the Brain aggregator no
longer imports seo/catalog/ai_assistant/morpheus_brain — each plugin pushes its
slice through the `BRAIN_SIGNALS` filter; ADR 0031); and
`core/context_processors.cart_context` (moved to the orders plugin via
`register_context_processor` — the request-time consumer is
`plugins/context_processors.py:plugin_context`, which merges contributed
processors and skips inactive owners; this is what finally makes that mechanism
real). ***The core-boundary ratchet is at 0*** — `core/` imports NOTHING from
`plugins.installed.*`; the baseline allowlist is empty and must stay empty
(a new leak fails CI + the PostToolUse hook). Final phase (ADR 0034): the
agent run-state models (`AgentRun`/`AgentStep`/`AgentApprovalRequest`) moved
into `core/agents/models.py` — the runtime that persists them is permanently
core (ADR 0029) — via `SeparateDatabaseAndState` on both sides (tables keep
their `agent_core_*` names; zero SQL; agent_core re-exports the classes for
back-compat). **Also repaid en route:** orders agent tools
(`orders.update_status`/`cancel`/`add_note`/`refund` →
`plugins/installed/orders/agent_tools.py`, hard-gate + staging intact;
agent_core's duplicate `orders.cancel` retired; `db.recent_orders` dropped
for `orders.search`); catalog write tools (`products.update_status`/`price`
→ `catalog/agent_tools.py`, `pricing_change` staging blocklist intact); and
brand voice (core fires the `AGENT_SYSTEM_PROMPT` filter as the last
prompt-assembly step; ai_content's subscriber prepends the voice — disable
the plugin and the plain prompt flows through). The full shell-leak /
duplication debt map (still open: product_videos, metafields, cloudflare,
seo shell imports; storefront account sub-pages; catalog.py book-vertical
sites) lives in `docs/plans/boundary-debt-2026-07.md` — repay from there,
one PR per item; bookvault, customers↔orders, the channel `mapping.py`
copy-paste, and the `_trail` builder are already repaid there.

---

## How to research

**Batched, not stepwise.** Combine `grep`, `find`, `wc`, `head` into one
script and run it once. Spawn a subagent for open-ended exploration so
the noisy output doesn't burn the main context. Reach for the direct tool
only when the target is known.

Bad: 10 sequential greps probing related files.
Good: one script that pulls the 10 results into one paste.

---

## How to execute coding tasks

When the user asks for code, **don't stop until it's fully done.** That
means:

1. Make the change.
2. Compile / syntax check (`python -m py_compile <files>` for Python,
   tag balance for Django templates).
3. Smoke locally before reaching for prod. `docker compose up` boots the
   full stack (postgres + redis + worker + beat) at `localhost:8000`; the
   no-Docker `runserver` path (SQLite, in [`docs/QUICK_START.md`](docs/QUICK_START.md))
   covers sync request/response paths but **not** async ones —
   `CELERY_TASK_ALWAYS_EAGER` is on *only* under tests
   (`settings._RUNNING_TESTS`), so `.delay()` work needs Redis or the
   compose stack to actually fire.
4. Deploy + smoke prod *when the change warrants it* (rsync → `docker
   build` on tetra → `docker compose up -d --no-build --force-recreate
   web` → `migrate` → curl the public URL). Merging to `main` is itself a
   prod deploy — see the landmine below.
5. Honest report: what shipped, what didn't, what's left.

A passing type/lint/syntax check is *necessary*, not *sufficient*.
Smoke the real behaviour — locally first, then the live URL.

**Landmine — running tests locally.** Bare `python manage.py test` reads
`DATABASE_URL` from `.env` and tries to reach the Docker `db` host, so it
hangs/dies outside the container. Always pin an in-memory DB:

```bash
DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.<name>
```

**Landmine — sqlite hides Postgres migration crashes.** The in-memory
test DB types loosely: an auto-generated `AlterField` that retargets a
FK across PK types (bigint→uuid) passes every local test and then
crashes the prod `migrate` (PR #62 and PR #64 both 503'd prod this
way). Cross-type FK retargets must be `RemoveField`+`AddField`. CI's
`migrations` job now applies every migration against real Postgres —
that's the gate; don't trust a green sqlite run for migration changes.

**Landmine — merging to `main` deploys to production.** Coolify
watches the repo: every push/merge to `main` triggers a build+deploy
of dotbooks.store. There is no separate "ship" step — treat a merge as
a deploy (and don't land several merges in rapid succession; Coolify
thrashes). A broken migration or boot error on `main` is a live 503
until hot-fixed. **Because a merge *is* a deploy, every merge to `main`
MUST bump `MORPHEUS_VERSION` and add a matching dated
`docs/RELEASE_NOTES.md` entry** (ADR 0032) — Settings → Version & updates
reads both, so an unversioned deploy silently ships changes users can't
see in the changelog. **This applies to *theme* code too** — an edit under
`themes/` is a versioned change exactly like `core/`, `plugins/installed/`,
or `morph/`; theme/CSS/template polish is not exempt from the bump (ADR 0033).
Batch local commits into one deploy carrying one
bump (PATCH = fix/polish/theme tweak, MINOR = feature, MAJOR = breaking).
**Don't hand-edit the two files — run `python manage.py release`:**
`release --minor "Headline" -m "bullet" -m "bullet"` bumps
`MORPHEUS_VERSION` *and* prepends the dated `docs/RELEASE_NOTES.md` entry
atomically (add `--commit` to also commit; `--set vX.Y.Z` for an explicit
version). `release --check` (a blocking CI step + usable pre-push) fails when
app/theme code changed vs `main` without a bump, or when the version and the
newest notes entry desync — so a forgotten bump is caught on the PR, not as a
post-deploy 503. On push to main the **`release` workflow** mirrors the version
to GitHub (annotated tag `vX.Y.Z` + a GitHub Release whose body is that notes
section); it no-ops if the tag already exists. The
`deploy-smoke` workflow polls `/readyz` after every main push and fails
red if prod never converges on the pushed `MORPHEUS_VERSION` — stuck-queue
recovery (zombie `in_progress` builds wedge Coolify's whole app queue) is in
`docs/OPERATIONS_RUNBOOK.md`.

**Landmine — a native dep that loads at settings-import is deploy-critical.**
A provider app in `INSTALLED_APPS` (e.g. allauth's `openid_connect` / `saml`
for staff_sso) hard-imports its package — `pyjwt[crypto]`, `python3-saml`
(native `xmlsec`/`lxml`) — at *settings import*, before any plugin toggle runs.
Ship the `requirements.txt` pin in the same commit or the deploy boots 503
(not a crash — the build just hasn't pip-installed it). Such deploys also have
a *longer* 503 window while the image rebuilds the native wheels; wait it out,
don't mistake the gap for a boot failure.

CI gates a change with `ruff check .`, `ruff format --check .`,
`python manage.py check` (blocking — fails on model-relation errors like
`fields.E301/E300/E307` that crash the prod boot; PR #62 once 503'd prod
because this step was `|| true`'d), `python manage.py makemigrations
--check --dry-run` (fails every prod boot if you ship a model without
one), the `migrations` job (applies every migration on real
Postgres — catches casts sqlite silently accepts), the **core-boundary
guard** (`scripts/check_core_boundary.py` — baseline-and-ratchet: blocks any
*new* `core/ → plugins.installed.*` import and any *stale* allowlist entry, so
the wrong-direction-coupling debt in `scripts/core_boundary_baseline.json` can
only shrink; also a PostToolUse hook), the **plugin-boundary guard**
(`scripts/check_plugin_boundary.py` — the *requires-aware* sibling: a plugin may
import another only if it declares it in `requires`; blocks any *new* undeclared
`plugins.installed.<A> → plugins.installed.<B>` import against
`scripts/plugin_boundary_baseline.json`, which starts at 122 pairs and can only
shrink — repay a pair by declaring the dep or inverting it via `core.hooks`),
and the **disable-test gate** (runs
`admin_dashboard/tests/test_disable_guards.py` as its own fast step).

---

## Think before coding

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop, name what's confusing, ask.

---

## Simplicity first

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or configurability that wasn't requested.
- No error handling for impossible scenarios.
- No backwards-compat shims for code you can just change.
- 200 lines that could be 50 → rewrite.

Test: would a senior engineer say this is overcomplicated? If yes, simplify.

---

## Surgical changes

Touch only what you must. Clean up only your own mess.

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style even if you'd do it differently.
- Notice unrelated dead code? Mention it. Don't delete it.
- Linter / autoreplace drift in unrelated files: revert it before
  staging your own changes.

When your changes create orphans:

- Remove imports / variables / functions that **your** changes made unused.
- Don't remove pre-existing dead code unless asked.

Test: every changed line traces directly to the user's request.

---

## Goal-driven execution

Define success criteria up front. Loop until verified.

- "Add validation" → "Tests for invalid inputs pass."
- "Fix the bug" → "Reproducer test passes."
- "Refactor X" → "All tests still pass."

For multi-step work, state a brief plan with verifiable checkpoints:

1. \[Step] → verify: \[check]
2. \[Step] → verify: \[check]

Strong success criteria let you loop independently. Weak criteria ("make
it work") force the user to check your work for them.

---

## Subagents and context hygiene

- Use subagents for noisy operations (test runs, log greps, full-repo
  searches, web research). Pass back a summary; keep the main window clean.
- Compact at ~70% context, not at the forced 83%.
- Plans don't survive `/clear` or `/compact`. If a plan is load-bearing
  across turns, write it to `docs/plans/<feature>.md` and reference it.
- Long sessions degrade through repeated compaction. End-and-restart
  beats pushing a 90%-full window through another phase.

---

## Verifying AI-generated code

LLM-generated code ships measurably more security and correctness bugs
than human-written code (~1.7× more major issues; 29-45% has known
vulnerability classes; ~20% of suggested third-party packages are
hallucinated). Treat AI output as untrusted-third-party-code:

- **Verified-Output rule.** Before adding a dependency: confirm the
  package exists on PyPI / npm registry, and that we already use it
  elsewhere in the repo, OR explicitly justify the new dep in the
  commit message.
- **Contract-test against real APIs.** Mocks pass while phantom methods
  fail in prod. Hit the actual interface in tests.
- **Feed errors back verbatim.** Don't paraphrase a stack trace into the
  agent — paste it. After a fix, ask whether the rule that would have
  prevented it belongs in this file.

Rules in `CLAUDE.md` are *advisory* — the runtime can ignore them.
**Hooks are the enforcement layer** (PostToolUse hooks for ruff, mypy,
forbidden-import grep). When you find an advisory rule being ignored
repeatedly, promote it to a hook.

---

## Living document

**Code and docs ship together.** Any change that alters architecture, a
convention, a public contract, a count, or a landmine must update the
relevant Markdown *in the same commit* — not "later." Which doc:

| You changed… | Update… |
|---|---|
| `core/` structure, a subsystem's job, the request lifecycle | `docs/ARCHITECTURE.md` |
| a plugin's purpose / deps / the plugin contract | `docs/PLUGIN_DEVELOPMENT.md` (+ that plugin's `app.py`) |
| a house rule, landmine, or convention | this file (`CLAUDE.md`) |
| the public API / MCP / GraphQL surface | `docs/MORPHEUS_API.md`, `docs/MCP_SERVER.md` |
| a skill's behaviour | `docs/SKILLS.md` + the skill's `SKILL.md` |
| the updater, `core/updates.py`, or how a deployment upgrades | `docs/UPDATING.md` — and keep its "verified against the running deployment" claims true or delete them |
| anything an out-of-tree app author must change to upgrade | `docs/MIGRATING.md` (a section per release) + the `Breaking changes shipped` table in `docs/API_STABILITY.md` |
| **`MORPHEUS_VERSION`** — bump on **every** deploy (merge = deploy) | **`docs/RELEASE_NOTES.md`** — add a dated `## vX.Y.Z — YYYY-MM-DD` entry (newest first); it's the source of truth for **Settings → Version & updates** (`release_notes` plugin). Torsor ADR 0019 + **0032** + **0033** (every production deploy bumps — app code *and* theme code). |

Prefer pointing at the source of truth over hard-coding volatile facts:
a plugin *count* in prose rots (it drifted to 47/49/54 across three docs
while the real number was 61) — write "see `MORPHEUS_DEFAULT_APPS`."

Every time AI-assisted work ships a wrong assumption, the fix-up commit
should also patch this file. If a rule is here twice, consolidate. If a
rule has stopped being violated for 6 months, consider deleting it.
