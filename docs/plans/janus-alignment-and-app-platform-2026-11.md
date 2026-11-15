# Morpheus × Janus — platform alignment, app lifecycle and agent coverage (Nov 2026)

## Context

**The ask (owner, 2026-11-15).** Morpheus is an agentic-first commerce platform whose features come from apps a store can switch on. Much of it is built and runs on five live stores (v0.171.0). Find the gaps, fix and improve them without changing the core idea. Janus, the agent behind Linda, is a separate open-source project (`magnetoid/Janus-Agent`); whenever it moves, Morpheus must stay aligned with it. Research how to connect the two and build a plan.

**Method.** Three read-only explorations (the Janus seam inside Morpheus; the Janus repository, read over the GitHub API; the app system and agent coverage), one design pass, and spot-checks of the strongest claims in the code on `origin/main` (0b433b93).

**Status:** approved by the owner on 2026-11-15. P1 (Janus truth patch) is v0.171.1. Update this line as each release ships.

**Owner's decisions (2026-11-15).**
1. Janus updates arrive as a **pull request with a test**: CI takes the newest Janus, runs the contract and a real `janus chat` against a stub model, and opens a PR that moves the pin. The owner merges; all five stores get the same verified version through a normal deploy. The runtime self-updater is retired.
2. Changes in the **Janus repository are allowed when general** (nothing Morpheus-specific), as a separate optional track. Morpheus never depends on one landing.
3. Apps: fix the **lifecycle inside a deployment** (enable/disable, dependencies, versions, compatibility). Installing apps that are not in the image stays with the morpheus.direct session.
4. **Platform first** (about nine releases), then back to commerce (A10 order editing, C4 returns, C1 post-purchase…).

The existing plan of record, `docs/plans/platform-gap-analysis-2026-11.md`, stays in force for commerce; this plan sits in front of its remaining rows.

## What the research found

### The Janus seam (Morpheus side)

- **The self-updater never runs on a shipped image.** `janus_runtime.source()` returns `None` when the build ref is a commit sha, and both Dockerfile refs are shas (a test asserts it). So the `auto_update` setting, "Check now" and the rollback machinery do nothing on the five stores. `docs/UPDATING.md:184` and `docs/ARCHITECTURE.md:121-123` still say Janus keeps itself current.
- **The fallback is the same commit.** `JANUS_REF` and `JANUS_KNOWN_GOOD` are both `eafb7aba…`, so a contract failure at build time "falls back" to the build that just failed.
- **The contract checks names, not behaviour.** It greps Janus's source for config keys, env vars, strings and table columns. It passes when a tool disappears from a toolset, ignores the CLI's exit code, and treats the hooks Linda's activity stream depends on as optional. It never proves that `-t` keeps the default 56-tool set out (the real safety boundary), that the turn token reaches the MCP header, or what `state.db`, stdout and the hook payloads contain.
- **Nothing in CI runs the real Janus.** Tests point `JANUS_BIN` at a missing path and use a fake. Only the weekly audit installs the pinned Janus, for `pip-audit`.
- **No turn records which Janus answered it.** `AgentRun.metadata` has no version or commit, and three numbers already read from `state.db` (reasoning tokens, API calls, cost) are dropped.
- **The child environment passes every inherited `JANUS_*` variable** (four reserved names excepted), which is wider than the allowlist the docs describe.
- **Tool schemas are the token cost.** One live turn used about 180k input tokens because every schema is resent on every call. Janus already has lazy tool loading (`tools.tool_search`, default `auto`) and Morpheus writes no key for it, so whether it is active today is unknown.

### The Janus repository

- It is a rebranded snapshot of Hermes Agent (2026-06-08) with no shared history upstream; changes from upstream are re-implemented by hand.
- **No release discipline:** 78 commits since the pin, all at version `0.18.0`; no changelog, no releases, one tag (`morpheus-known-good`). `state.db` gained two tables without a schema-version bump, and a config default changed (`approvals.mode` `manual` → `smart`). So drift has to be caught on the Morpheus side.
- **Surfaces Morpheus does not use yet:** lazy tool schemas, per-server tool filters, a Python API (`AIAgent`), structured events over the TUI-gateway JSON-RPC and API-server SSE, and (on main) hooks that can fail closed.
- **Still missing for an embedder:** JSON output for `chat -q`, a machine-readable version or capabilities command, a switch that stops `delegate_task` taking `acp_command` (confirmed: it reaches `subprocess.Popen`), and a headless `clarify` policy.

### The app system

- **A runtime toggle reaches one process.** `activate()`/`deactivate()` change the gunicorn worker that handled the click; the other three workers and the Celery containers keep the old state until a restart. The code's own comment admits the lag.
- **Three behaviours for one action.** The dashboard toggle activates in memory; `plugins.toggle` and `plugins.enable` only write the database; `plugins.disable` does both. None checks `requires` or warns about dependants; `plugins.toggle` does not check the app exists.
- **`requires` is advisory** (a missing dependency is logged and the app activates anyway). There is no compatibility field, `PluginConfig.installed_version` is never written, `morpheus.__version__` is a hard-coded `'0.1.0'`.
- **`settings.set` validates nothing against the schema** (only bool/int coercion), and three separate coercers exist (dashboard POST, panel builder, MCP argument check).
- The API-stability check covers a fraction of the surface an app author uses (not the SDK doors, tool names, contribution fields or 94 of 135 events).

### Agent coverage

- 278 tools; **49 of 98 apps have none** (23 of them have POST views, 17 only a settings panel, 9 no write surface).
- The house rule "every merchant action ships with an agent tool" is prose only; no check enforces it.
- **An app cannot add a Janus skill**: Janus loads SKILL.md files only from `core/assistant/janus_skills`; `contribute_skills` feeds Worker agents.
- Edge gaps: `customers.read/write` are missing from `AVAILABLE_SCOPES` (a tool scope that cannot be granted); `/agents.md` says the storefront MCP needs no auth while `tools/call` requires a Bearer; `memory.recall` sits in the storefront tool whitelist although external agents must never see the shop memory.

## The design: how Janus stays aligned

One source of truth and three layers of proof.

- **Truth:** `ARG JANUS_REF` in the `Dockerfile`. Everything else (the companion pins, the audit workflow, the page) reads from it or from `janus_runtime.PINS`. The `morpheus-known-good` tag in the Janus repo stops mattering.
- **Layer 1 — static contract** (`core/assistant/janus_contract.py`, exists): tightened so a lost tool, a failing CLI and missing hooks fail it. Runs at image build.
- **Layer 2 — behavioural conformance** (new): the real `janus chat`, wired by the engine's own code, talks to a stub model on loopback and to the store's real MCP edge. It asserts what Morpheus actually relies on. Runs in CI on every change to the seam.
- **Layer 3 — canary bump** (new): a scheduled workflow resolves the newest Janus commit, runs layers 1 and 2 against it and opens a draft PR that moves the pin, with a contract diff in the body. A human merges. Delivery is a normal, versioned, rollback-guarded deploy.
- **Observability:** every Linda turn records the Janus version and commit, so a regression can be tied to a bump.

Rules that stay: all Morpheus-specific tuning lives in this repo; a new Janus surface enters the contract in the same change that starts using it; `delegation`, `web` and `vision` stay off; no persistent volume for Janus state; the repository and ref never come from a setting.

## Release sequence

One release in flight at a time, each from a fresh worktree off `origin/main`, each versioned with `manage.py release`, merged only on the owner's explicit yes (a merge deploys five stores; Croatia is queued by the Coolify API afterwards).

| # | Release | Bump | Size | Why here |
|---|---|---|---|---|
| P1 | Janus truth patch | patch | S, 1–2 d | makes the current state honest; everything later measures against it |
| P2 | Conformance suite | patch | M, 3 d | nothing can prove a bump before it exists |
| P5 | App toggle reaches every process | minor | M, 3 d | a live correctness bug, independent of Janus |
| P7 | One settings coercer | minor | M, 3 d | `settings.set` must validate before settings count as agent-covered |
| P3 | Pin bump by pull request | minor | S, 2 d | needs P2 |
| P3b | Retire the self-updater | patch | S, 1 d | only after the first bump has merged |
| P4 | Deferred tool schemas | minor | S–M, 2 d | needs P2's recorded request and P1's per-turn numbers |
| P6 | Manifest compatibility and upgrades | minor | M, 3 d | needs P5 |
| P8 | Agent-coverage ratchet | minor | M, 3 d | needs P7 |
| P9 | App skills for Linda | minor | S, 2 d | needs P5 (the active set is true everywhere) |
| P10+ | Tool batches | minor each | M each | shrink the P8 baseline |

### P1 — Janus truth patch

- `core/assistant/janus_contract.py`: `_check_toolsets` also fails when a reviewed tool is gone; `_check_cli` requires exit code 0; `_check_imports` adds `primp`; the `pre/post_tool_call` hook checks and `mcp_servers.*.tools.resources/prompts` and `model.default` join the checks; `main()` writes `commit` and `fallback` into the report. New checks ship `required=False` and are promoted in P2, once the job has run them against the real pin.
- `Dockerfile`: when `JANUS_REF == JANUS_KNOWN_GOOD`, a contract failure fails the build; a real fallback records itself in the report.
- `core/assistant/runtime.py` (`_finish`, `_record_run`): `AgentRun.metadata` gains `janus_version`, `janus_commit`, `reasoning_tokens`, `api_calls`, `cost_usd`. Reuse `janus_runtime.installed_build()` and `janus_engine._turn_usage` / `_USAGE_COLUMNS`.
- `janus_engine._child_env`: no `JANUS_*` variable is inherited any more. *As shipped:* none of the five stores sets one (names read from the containers, 2026-11-15), and `JANUS_INFERENCE_MODEL` is read by Morpheus when it writes the config, not by the child, so the named list is empty.
- Janus page (`plugins/installed/janus/views.py`): says "pinned build, updates arrive with Morpheus releases" when `janus_runtime.source()` is `None`.
- Agent edge: add `customers.write` to `agent_mcp/scopes.py::AVAILABLE_SCOPES` and make `test_every_tool_scope_is_in_the_catalog` walk `linda_turn._all_tools()` (*as shipped:* no tool declares `customers.read` and no GraphQL resolver asks for either, so neither the read scope nor a `_CAPABILITY_FOR_SCOPE` entry was added); keep the shop memory from every token (*as shipped, wider than first found:* `memory.recall` joins `gates.NOT_FOR_TOKENS`, which `_public_tools()` now applies on every server, so the storefront and cart clusters, `/mcp/v1/` and the admin server stop offering it, and an external turn carries no shop memory); make `/agents.md` (`agent_mcp/app.py`) say that listing is open and every `tools/call` needs a token.
- Docs: `docs/UPDATING.md`, `docs/ARCHITECTURE.md`, the `janus_runtime` docstring, the "10 tool steps" comment in `janus_learning.py`; this plan lands as `docs/plans/janus-alignment-and-app-platform-2026-11.md` with a pointer from the gap analysis.
- Tests: `core/assistant/tests/test_janus_contract.py`, `test_janus_engine.py`, `test_janus_updates.py` (it counts pins in the Dockerfile; keep the counts or edit in the same change), `agent_mcp/tests/test_scopes.py`, `test_servers.py`. No migration.

### P2 — Conformance suite

- New `core/assistant/tests/conformance/`: a stdlib stub of `POST /v1/chat/completions` (streamed and not) and `GET /v1/models`, scripted by request index: a tool call naming `mcp_morpheus_admin_<tool>`, then final text; an empty reply; one 500.
- The suite uses the engine's own wiring, not a copy: janus settings `model_source=custom`, `provider=openai`, `base_url` = the stub; overrides for `JANUS_BIN`, `LINDA_JANUS_HOME`, `LINDA_MCP_URL`; the real `/mcp/admin/v1/` served by Django's `LiveServerTestCase` (no new dependency).
- It asserts: the request's `tools` array holds only store tools plus `turn_toolsets()` (proves `-t`), and records its size; the MCP view saw the turn token; `session_id:` on stderr; `--resume` and the "Session not found" retry; `state.db` has the usage columns; `progress.jsonl` carries every field `janus_progress_hook.py` reads; an empty reply is an error; `SOUL.md` and `.no-bundled-skills` are in effect; a `requires_approval` tool returns the gate's refusal; `MEMORY.md` round-trips with `\n§\n`.
- CI: a `janus-conformance` job in `.github/workflows/ci.yml` installs the pinned Janus the way `audit-weekly.yml:37-47` does (ref read from the Dockerfile), cached on ref + pins, path-filtered to `Dockerfile`, `core/assistant/**`, `agent_mcp/**`, `janus/**`; also run weekly. Tests skip unless `JANUS_CONFORMANCE_BIN` is set, and **the job fails when zero conformance tests ran** (a skip is not a pass). Advisory for a week, then required.
- CLAUDE.md: the sentence "tests must never spawn a real model" names this one exception (real Janus, stub model on loopback, env-gated).
- Promote P1's new contract checks to required.

### P5 — App toggle reaches every process

- `plugins/registry.py`: split `activate`/`deactivate` into in-memory `_apply_active`/`_apply_inactive` and the persisted pair (which also writes the database, bumps a version token and, on disable, runs `on_disable()`). New `reconcile()`: one cache read of the token; unchanged → return; otherwise, under a lock, diff `_get_enabled_from_db()` against `_active`, apply in `_topo_sort` order and call `_refresh_urlconf()` once. It never writes the database, never bumps the token, never runs `on_disable()` and never deactivates a protected or system app.
- Hook points: `plugins/middleware.py::PluginMiddleware` (already in `MIDDLEWARE`, a no-op today) before the response, and `task_prerun` in `morph/celery.py`. A 60-second database re-read covers a cache outage (off under tests). Token pattern: the one in `booking_marketplace/search.py` (`cache.add` + `bump`), copied, not imported.
- One writer: new `plugins/services.py::set_enabled(name, enabled, actor)` (existence, `requires`/`conflicts`, dependants, protection), called by the dashboard toggle (`admin_dashboard/views_split/apps.py`), `plugins.toggle` (`core/assistant/tools/admin_ops.py`) and `plugins.enable/disable` (`core/assistant/tools/plugins.py`). Tool names unchanged. The "needs restart" hint goes; a changed beat schedule still needs one, and the page says so.
- Tests: new `core/tests/test_registry_reconcile.py` (acts as the second process: URL 404s, hooks skipped, no database write, `on_disable` not called, middleware order); extend `test_registry_url_disable.py` and `admin_dashboard/tests/test_disable_guards.py`. No migration.
- Risk: `ready()` now runs at request time in processes that never activated the app; it runs under the lock, and a failure leaves the app inactive there and logs at ERROR.

### P7 — One settings coercer

- New `plugins/config_schema.py` (`coerce`, `validate`, `is_secret`, `redact`), extracted from the three partial ones: the settings POST (`admin_dashboard/urls.py`), `_build_panel_fields` (`admin_dashboard/views_split/settings.py`), `_validate_one_arg` (`agent_mcp/views.py`), and the redaction helpers in `core/assistant/tools/ecommerce.py`.
- `Plugin.set_config` validates through it; `settings.set` coerces by schema; new read tool `settings.describe` returns the redacted schema with defaults.
- Schema flag `x-agent-writable: false`, honoured by `settings.set`; default false for `format: password`; set on janus `api_key`, `base_url`, `model_source`, `provider` (otherwise Linda can point her own inference at any host).
- First release: an unknown key or type passes with a warning, so nothing accepted yesterday is refused. Validation on write only; no migration.
- Tests: `plugins/tests/test_config_schema.py`, settings-tool tests, the dashboard POST tests as the golden reference.

### P3 — Pin bump by pull request, and P3b — retire the updater

- `scripts/bump_janus.py`: a pure text change (`JANUS_KNOWN_GOOD` ← old `JANUS_REF`, `JANUS_REF` ← new sha). `audit-weekly.yml` reads the companion pins from `janus_runtime.PINS`.
- `.github/workflows/janus-bump.yml`: scheduled and manual; `contents` and `pull-requests` write only; repository read from the Dockerfile's `ARG JANUS_REPO`, never an input; resolves `main` with `git ls-remote` and requires 40 hex characters; runs the contract, the conformance suite and `pip-audit` **inside the same run** (a PR opened with `GITHUB_TOKEN` triggers no workflows); opens or replaces one draft PR with a contract diff. No auto-merge, no `pull_request_target`. A human pushes the release commit, which triggers normal CI.
- First bump (78 commits): check `approvals.mode` (`manual` → `smart`), `clarify` gaining `questions`, the new `platform_toolsets` default (conformance must still prove `-t`), the `config.yaml.last-good` fallback (assert the generated config is the one in effect), the new `state.db` tables, hooks `on_failure`.
- **P3b**, its own yes, after the first bump is live: delete `janus_updater.py`, the `maybe_update` calls, `LINDA_JANUS_AUTO_UPDATE`, the rollback machinery and the `auto_update` setting (a setting with no reader is a lie). Keep `installed_build`, `contract_report` and `upstream.py` (the page shows "N commits behind"). Rewrite CLAUDE.md's "Janus also updates itself" paragraph and close phases 5–6 of `janus-replaces-linda` as not needed.
- Tests: `core/tests/test_janus_bump_script.py`, `test_janus_updates.py`.

### P4 — Deferred tool schemas

- Measure first: the `tools` array P2 records, and P1's per-turn tokens and API calls from live turns.
- `janus_engine._config_text` writes `tools.tool_search.enabled` and `threshold_pct` from a new janus setting `tool_search` (`off` / `auto` / `on`), default = what was measured as today's behaviour; reader `janus_settings.tool_search_mode()` in the same change; both keys and the bridge tools (`tool_search`, `tool_describe`, `tool_call`) join the contract.
- Follow-ups in the same release: labels for the bridge steps in `core/assistant/activity.py` (they produce no hook steps); one prompt line when deferral is on (skills name `orders.search`, the model must look for `mcp_morpheus_admin_orders_search`); a conformance scenario with `enabled: on` proving every call still crosses `gates.py`.
- Success: input tokens per live turn before and after (baseline about 180k).

### P6 — Manifest compatibility and upgrades

- `plugins/base.py`: optional `min_morpheus` / `max_morpheus` (tuple compare, no dependency; missing = compatible; protected and system apps ignore it) and a no-op `on_upgrade(previous)`.
- Registry: an incompatible app, or one with an unmet `requires`, is not activated and is recorded in `registry.skipped[name]` with a reason, shown in `plugins.list` and on the Apps page. `PluginConfig.installed_version` written by compare-and-swap so `on_upgrade` runs once across processes.
- `morpheus.__version__` reads the real version; `scripts/check_api_stability.py` widens to the SDK doors, tool names, `MorpheusEvents` and contribution fields; `morph_create_plugin` scaffolds `help.md`, an agent-tools stub, `migrations/__init__.py` and a test; `docs/PLUGIN_DEVELOPMENT.md` corrected (`.plugin` → `.app`, protected count points at code, the `plugins.describe` promise).
- Tests: `core/tests/test_plugin_manifest.py`, including "every in-tree app is compatible with the current version". No migration.

### P8 — Agent-coverage ratchet

- `scripts/check_agent_coverage.py` (stdlib `ast`, the shape of `scripts/check_plugin_boundary.py`): lists staff-gated views that accept POST; a view is covered by a module-level `AGENT_TOOLS = {'view': 'tool.name' | 'none: reason'}` whose tool must exist. Settings keys count as covered by `settings.set` after P7.
- Baseline `scripts/agent_coverage_baseline.json`, shrink-only, in the `ci.yml` lint job, with the count printed in the CI summary.
- Same release: agent_core's `orders.mark_fulfilled`/`mark_shipped` and GraphQL `markOrderFulfilled` go through `orders/fulfilment.py:create_fulfillment` (today they record no parcel).
- Not done here, by rule: flagging everyday writes `requires_approval` (the Worker cannot resume an approved call).

### P9 — App skills for Linda

- `janus_engine._prepare_home` rebuilds `<home>/store-skills/` each turn from `core/assistant/janus_skills` plus `<app>/janus_skills/` of every active app, and `skills.external_dirs` points only there. A convention, not a hook: a disabled app's skills are gone next turn, and an agent's edit cannot outlive the turn or reach another conversation (today the external directory is the writable `/app` tree).
- Tests: `LindaCatalogueTests.test_prompt_and_skills_name_only_tools_linda_has` extends to app skill folders (a skill may name core tools and its own app's); staging tests in `test_janus_engine.py`. `docs/PLUGIN_DEVELOPMENT.md` gains the convention.

### P10+ — Tool batches

Each batch removes entries from the P8 baseline, ordered by merchant value: store operations (returns_portal, post_purchase, digital_products, cart_abandonment), compliance (consent, gdpr), channels and suppliers, developer (webhooks_ui, importers, cloudflare, tracking). Security surfaces (staff_mfa, Janus keys) and apps with no write surface are exempt with a stated reason.

## Optional upstream track (Janus repository, general only)

Each item is its own PR there, arrives through the bump PR, and only then may Morpheus use it (contract updated in the same change). In order:

1. Restore the upstream MIT copyright notice and remove the two Morpheus/Linda comments (`cron/scheduler.py`, `janus_cli/config.py`).
2. A config switch that stops `delegate_task` accepting `acp_command`/`acp_args`.
3. JSON / stream-JSON output for `chat -q`.
4. A headless `clarify` policy (today a call can stall up to 120 s).
5. `version --json` or a capabilities command, and `tools list --json`.
6. Release discipline: changelog, tags, a version bump on every interface change, `SCHEMA_VERSION` bumped with new tables.
7. Declare `memory.nudge_interval` and `skills.creation_nudge_interval` in `DEFAULT_CONFIG`.
8. A generic embedder-contract test in Janus CI.

Later, unscheduled: keep one subprocess per turn but speak the TUI-gateway JSON-RPC, which would give token streaming and a real mid-turn `clarify`.

## Out of scope

Installing apps that are not in the image, the app catalogue and licensing (morpheus.direct session; the static `data/apps_registry.json` is left alone). Uninstall with data removal. Any fork or patch of Janus for Morpheus.

## Afterwards: commerce

Back to `docs/plans/platform-gap-analysis-2026-11.md`: A10 order editing, C4 returns and exchanges, C1 post-purchase, A11 marketplace money, A9 B2B, the rest of A6, then phases B (headless contract), C (half-built apps), D (shopper-side agents: public storefront MCP, UCP) and E (hygiene). From P8 on, each of those ships its agent tools under the ratchet.

## Critical files

`core/assistant/janus_contract.py`, `janus_engine.py`, `janus_runtime.py`, `runtime.py`; `Dockerfile`; `.github/workflows/ci.yml`, `audit-weekly.yml`; `plugins/registry.py`, `plugins/base.py`, `plugins/middleware.py`; `core/assistant/tools/admin_ops.py`, `tools/plugins.py`; `plugins/installed/agent_mcp/scopes.py`, `servers.py`, `linda_turn.py`; `plugins/installed/admin_dashboard/views_split/apps.py`, `settings.py`; `plugins/installed/janus/app.py`, `views.py`.

## Verification

- Per release: ruff 0.15.8; targeted tests with `DATABASE_URL='sqlite:///:memory:'`; `manage.py check`; `makemigrations --check --dry-run`; the three boundary/standard scripts; `release --check`. Full serial suite with all five opt-in apps before P2, P5 and P7.
- P2 onward: the conformance job green against the pinned Janus, with a non-zero test count.
- P5: locally, two gunicorn workers and Redis (`REDIS_URL=redis://127.0.0.1:6379/15`); toggle an opt-in app and request its URL twenty times; every answer must agree. On a live store only with the owner's yes.
- P3: the first bump PR shows a contract diff and a green conformance run before anyone merges it.
- After each merge: all five stores reach the new commit (`/readyz` ok, home 200). Live probes: the Janus page shows version and commit; a fresh `AgentRun` row carries `janus_commit` (P1); input tokens per turn before and after (P4).

## Open risks

- Whether the current pin passes the tightened contract is unknown until P2 runs it; hence the `required=False` first step.
- The `_child_env` allowlist can break a store that sets a `JANUS_*` variable nobody listed; names are read first.
- Whether an agent can edit a skill in an external directory is inferred from Janus's code, not observed; P9 removes the exposure either way.
- P6 and P8 were designed without reading `core/component_updates.py` and the scaffold command in full; both get read before their release starts.
- The first bump crosses 78 commits at once; if it fails, bisect by resolving older shas with the same workflow.

## Flags for the owner (no action is taken on these without you)

- **Licence notice in the Janus repo.** The original "Copyright (c) 2025 Nous Research" line was replaced; MIT asks that it stay. Not legal advice; worth restoring.
- **Two Morpheus/Linda comments in the Janus repo** break the "Janus stays general" rule.
- **GitHub setting** "Allow GitHub Actions to create and approve pull requests" must be on for P3.
- The Janus repo has 13 open PRs and no version bump since the pin; item 6 of the upstream track is what makes future bumps readable.
