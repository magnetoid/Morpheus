# Morpheus × Janus — platform alignment, app lifecycle and agent coverage (Nov 2026)

## Context

**The ask (owner, 2026-11-15).** Morpheus is an agentic-first commerce platform whose features come from apps a store can switch on. Much of it is built and runs on five live stores (v0.171.0). Find the gaps, fix and improve them without changing the core idea. Janus, the agent behind Linda, is a separate open-source project (`magnetoid/Janus-Agent`); whenever it moves, Morpheus must stay aligned with it. Research how to connect the two and build a plan.

**Method.** Three read-only explorations (the Janus seam inside Morpheus; the Janus repository, read over the GitHub API; the app system and agent coverage), one design pass, and spot-checks of the strongest claims in the code on `origin/main` (0b433b93).

**Status:** approved by the owner on 2026-11-15. P1 (Janus truth patch) is v0.171.1, live on all five stores since 2026-11-16. P2 (conformance suite) is v0.171.2, live on all five since 2026-11-16. P5 (app toggle reaches every process) is v0.172.0, live on all five since 2026-11-16. P7 (one settings coercer) is v0.173.0, live on all five since 2026-11-17. P3 (pin bump by pull request) is v0.174.0 and the first bump v0.175.0, both live on all five since 2026-11-17. P3b (the self-updater retired) is v0.175.1, live on all five since 2026-11-18. P4 (tool search) is v0.176.0, live on all five since 2026-11-18. The two obligation releases that come first in the merged order, F1 (v0.177.0) and F2 (v0.178.0), are live on all five since 2026-11-18. P6 (manifest compatibility and upgrades) is v0.179.0, live on all five since 2026-11-19. A10a (v0.180.0) and F3 (v0.181.0), which the merged order puts between P6 and P8, are live on all five since 2026-11-20. P8 (agent-coverage ratchet) is v0.182.0, in review: 237 staff write views found, 6 covered, 231 in the baseline. Update this line as each release ships.

**Order from 2026-11-18 (owner).** P6, P8, P9 and P10 now run interleaved with the obligation and commerce releases, in the merged order in [platform-gap-analysis-2026-11.md](platform-gap-analysis-2026-11.md#order-of-work-from-2026-11-18):
- two obligation releases (AI marks, claims check) come before P6;
- the cancel-and-refund rules and the withdrawal function come between P6 and P8;
- P10's batches follow the features they serve.

"Platform first" no longer holds.

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

From 2026-11-18 the rows left (P6, P8, P9, P10+) take their places in the merged order (see the status note above).

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

*As shipped (v0.171.2):*
- Seven tests in `core/assistant/tests/conformance/test_janus_conformance.py`, driven through `Assistant().stream` (turn token, edge, harvest and `AgentRun` are the production ones), against the pinned Janus `eafb7aba`. The stub (`stub_model.py`) streams only, because Janus always streams; every other path answers 404, `/v1/models` included, so Janus falls back to its default context length.
- No path filter and no weekly run: the pin moves only in a PR, which runs the job, and P3's bump workflow runs the suite on a schedule. With no path filter the owner can make the job required without it sitting pending.
- The job runs on Postgres, as the stores do, so the live server and the test each have their own connection. The suite also takes the stores' loopback path to the edge: the store's host and the https scheme travel as configured MCP headers, under `SECURE_SSL_REDIRECT`.
- Janus is installed fresh on every run, never from a cache: its own dependencies float, an image build resolves them afresh, and a cached venv would keep testing the versions of its first install.
- Every P1 check is required now, except the two notice strings (`SOFT_NAMES`), which only affect what the chat strips.
- The first run found two defects, fixed in the same release:
  - an empty model reply ended in Janus's explainer ("⚠️ No reply: …") with exit 0, and the merchant got that line as Linda's answer. The config now sets `display.turn_completion_explainer: false`, so Janus prints `(empty)`, which the engine already treats as a failure;
  - `janus chat -q` records its sessions with source `cli` whatever `--source` says, so `_session_started_since` and `_recover_reply` (filtering on `linda`) never matched: a timed-out turn's tokens were never counted toward the spend cap, and the v0.68.0 recovery of a reply lost to swapped streams could not work. Both accept `cli` and `linda` now.
- Also proved: Janus fences every store tool result as `<untrusted_tool_result source="…">` data; MCP discovery finishes before the first model call; the 500 from the model reaches the chat as a `retry` event carrying only the status.
- Measured for P4 (written to the job's step summary): 11 Janus tools beside 238 store tools, about 140 KB of tool schemas per model call, no deferral at the stub's context length. A turn takes about 20 s locally before the model answers, most of it Janus starting up.
- The full serial suite with the five opt-in apps ran in CI's `test` job, not locally: the laptop had under 1 GB free and the suite fills `media/`.

### P5 — App toggle reaches every process

- `plugins/registry.py`: split `activate`/`deactivate` into in-memory `_apply_active`/`_apply_inactive` and the persisted pair (which also writes the database, bumps a version token and, on disable, runs `on_disable()`). New `reconcile()`: one cache read of the token; unchanged → return; otherwise, under a lock, diff `_get_enabled_from_db()` against `_active`, apply in `_topo_sort` order and call `_refresh_urlconf()` once. It never writes the database, never bumps the token, never runs `on_disable()` and never deactivates a protected or system app.
- Hook points: `plugins/middleware.py::PluginMiddleware` (already in `MIDDLEWARE`, a no-op today) before the response, and `task_prerun` in `morph/celery.py`. A 60-second database re-read covers a cache outage (off under tests). Token pattern: the one in `booking_marketplace/search.py` (`cache.add` + `bump`), copied, not imported.
- One writer: new `plugins/services.py::set_enabled(name, enabled, actor)` (existence, `requires`/`conflicts`, dependants, protection), called by the dashboard toggle (`admin_dashboard/views_split/apps.py`), `plugins.toggle` (`core/assistant/tools/admin_ops.py`) and `plugins.enable/disable` (`core/assistant/tools/plugins.py`). Tool names unchanged. The "needs restart" hint goes; a changed beat schedule still needs one, and the page says so.
- Tests: new `core/tests/test_registry_reconcile.py` (acts as the second process: URL 404s, hooks skipped, no database write, `on_disable` not called, middleware order); extend `test_registry_url_disable.py` and `admin_dashboard/tests/test_disable_guards.py`. No migration.
- Risk: `ready()` now runs at request time in processes that never activated the app; it runs under the lock, and a failure leaves the app inactive there and logs at ERROR.
- Shipped as v0.172.0. Decided while building: a process does not mark its own bump as read (a switch flipped elsewhere a moment before would hide behind it), and the first `reconcile()` of each process always reads once, because boot reads the switches before the cache is reachable. An app with no stored row is left as it is. `set_enabled` also refuses a system app (reconcile would never follow that switch), stores nothing when `ready()` raises, and writes an `app.enabled` / `app.disabled` audit row. `manage.py morpheus enable|disable` goes through it too. Found on the way: bookvault's settings save set its own switch to on, which a reconcile would now spread within a minute; it leaves the switch alone. The review before the PR found five more, all fixed in it: a switch the database did not save was reported as done (and this worker's next reconcile undid it), so the persisted pair now raises and changes nothing; one re-entrant lock per process now covers `activate`, `deactivate` and `reconcile`, and the token is marked read only once applied, or two threads could run one app's `ready()` twice; `hook_registry.register` swaps in a new list instead of sorting in place (a request firing that event saw no handlers mid-sort); the switches are read from the primary, never a replica; and the tear-down follows the store's switch, so it still runs when the app's start-up failed in the clicking worker, whose Apps page now marks it "Did not start". Left as it was: staff_sso's `ready()` syncs its provider rows in every worker at once, as it already did at boot.

### P7 — One settings coercer

- New `plugins/config_schema.py` (`coerce`, `validate`, `is_secret`, `redact`), extracted from the three partial ones: the settings POST (`admin_dashboard/urls.py`), `_build_panel_fields` (`admin_dashboard/views_split/settings.py`), `_validate_one_arg` (`agent_mcp/views.py`), and the redaction helpers in `core/assistant/tools/ecommerce.py`.
- `Plugin.set_config` validates through it; `settings.set` coerces by schema; new read tool `settings.describe` returns the redacted schema with defaults.
- Schema flag `x-agent-writable: false`, honoured by `settings.set`; default false for `format: password`; set on janus `api_key`, `base_url`, `model_source`, `provider` (otherwise Linda can point her own inference at any host).
- First release: an unknown key or type passes with a warning, so nothing accepted yesterday is refused. Validation on write only; no migration.
- Tests: `plugins/tests/test_config_schema.py`, settings-tool tests, the dashboard POST tests as the golden reference.

*As shipped (v0.173.0):*
- `plugins/config_schema.py`: `properties`, `coerce`, `validate`, `errors`, `clean`, `is_secret`, `looks_secret`, `redact`, `agent_writable`, `field_kind`, `report`. `validate` keeps the MCP edge's messages exactly; it does not check list items, so tool arguments are refused for nothing new. Tests sit in `plugins/tests_config_schema.py`, the shape of the other package-root tests.
- Ruling: `set_config` only logs (`settings: <app>.<key>: …`) for a value its declared setting would refuse, and is silent for an undeclared key, because apps keep internal state there (AliExpress's `_access_token`, the setup guide's dismissal, an AI provider's fetched model list). `settings.set` refuses a declared value that does not fit; an undeclared key keeps the old true/false/digits reading and comes back with a warning, unless its name reads like a secret.
- Ruling: `x-agent-writable: false` also on every ai_assistant `*_base_url` (the store's key for that provider goes there), openai_shopping's `push_endpoint` (its push token goes there) and the whole staff_sso schema (who signs in); the flag can sit on a whole schema.
- Found on the way: the settings panel rendered a list as Python's `[60, 1440, 4320]` and saved that text, so cart recovery and subscription dunning failed to read their delays, kept their defaults and ignored `require_marketing_consent` after them. The panel now edits a list as comma-separated text (JSON when an item has a comma in it or is not plain) and saves a list; both readers also read the old text.
- From the independent review: ai_assistant reads `<provider>_base_url` for every provider but declares ten, so `gemini_base_url` and `anthropic_base_url` were still writable and an agent could send the store's key to any server (reproduced). An undeclared key ending in `_url`, `_endpoint` or `_host` is now the merchant's, tested over every provider in `provider_registry._DEFAULT_BASE_URLS`. Also made the merchant's: agent_core's guardrails (an agent could loosen its own limits), `rbac.enforcement_mode`, `backups.backup_dir` (a folder under `/app/media` would publish the nightly dump) and janus's `model`, `fallback_providers` and `extra_instructions`. When both schemas declare a key, either can now make it secret or the merchant's. The AI page's Disconnect clears `ai_provider` with None instead of `''`, which its enum lacks.
- Left as it is (review): the merchant may approve a `settings.set` that the tool then refuses, because the flag is read inside the tool after the edge's consent; the skill tells Linda to read `settings.describe` first. Moving the check into `gates.py` would special-case one tool in the one gate chain.
- Found, not fixed (separate bug): the subscribe-and-save block reads `settings.allowed_cadences_days`, and nothing passes a `settings` variable to a storefront block, so the picker lists no cadences whatever the app's setting says.
- Not done: the local full serial suite (the disk had 300 MB free). A broad local run (4,053 tests) passed; CI's full suite with all five opt-in apps is the gate for this release.

### P3 — Pin bump by pull request, and P3b — retire the updater

- `scripts/bump_janus.py`: a pure text change (`JANUS_KNOWN_GOOD` ← old `JANUS_REF`, `JANUS_REF` ← new sha). `audit-weekly.yml` reads the companion pins from `janus_runtime.PINS`.
- `.github/workflows/janus-bump.yml`: scheduled and manual; `contents` and `pull-requests` write only; repository read from the Dockerfile's `ARG JANUS_REPO`, never an input; resolves `main` with `git ls-remote` and requires 40 hex characters; runs the contract, the conformance suite and `pip-audit` **inside the same run** (a PR opened with `GITHUB_TOKEN` triggers no workflows); opens or replaces one draft PR with a contract diff. No auto-merge, no `pull_request_target`. A human pushes the release commit, which triggers normal CI.
- First bump (78 commits): check `approvals.mode` (`manual` → `smart`), `clarify` gaining `questions`, the new `platform_toolsets` default (conformance must still prove `-t`), the `config.yaml.last-good` fallback (assert the generated config is the one in effect), the new `state.db` tables, hooks `on_failure`.
- **P3b**, its own yes, after the first bump is live: delete `janus_updater.py`, the `maybe_update` calls, `LINDA_JANUS_AUTO_UPDATE`, the rollback machinery and the `auto_update` setting (a setting with no reader is a lie). Keep `installed_build`, `contract_report` and `upstream.py` (the page shows "N commits behind"). Rewrite CLAUDE.md's "Janus also updates itself" paragraph and close phases 5–6 of `janus-replaces-linda` as not needed.
- Tests: `core/tests/test_janus_bump_script.py`, `test_janus_updates.py`.

*As shipped (v0.174.0):*
- `scripts/bump_janus.py` (standard library only): `env` prints the pin for `$GITHUB_ENV` (repository, slug, ref, fallback, and `janus_runtime.PINS` read without importing it); `bump <sha>` rewrites only the two ARG lines; `title` and `body` write the pull request. CI's conformance job and the weekly audit read the pin through it, so no workflow keeps its own copy of the repository URL or the companion pins.
- `.github/workflows/janus-bump.yml`, Tuesdays and by hand, in four jobs, so the new Janus never shares a job with a write token or with what is said about it:
  - `resolve` (read-only) takes the newest commit of the Janus repository's main with `git ls-remote`, or, by hand, a `commit` input that must be 40 hex, on that main and newer than the pin (GitHub serves any commit of a fork network by its sha). It is the only input; the repository comes from the Dockerfile. It also hands on the pin it read.
  - `candidate` runs the new Janus, so it has a read-only token that is not left in `.git/config`, and restores and saves no cache (a scheduled run's cache is main's, which every branch restores). It installs the commit as the image does (a failed install is a result, kept in `install.txt`), then runs the contract, the conformance suite, pip-audit (after the suite, so the auditor's packages cannot change what was tested) and the contract on the current pin, for the diff. It uploads the raw results, whatever happened.
  - `describe` (read-only, never runs Janus) fetches the commit range itself and judges and words the results with this repository's script (`bump_janus.py verdict`, `title`, `body`): the contract must report `ok: true`, and the conformance suite must run tests, end OK by its last summary line and skip none. The description says the results are the candidate's own report, which CI on the release commit and the image build check again.
  - `pull-request` runs no Janus and is the only job with `contents` and `pull-requests` write. It runs only when `describe` passed the candidate, never for a pull request event, and not when main's pin moved during the run. It commits the bump as `github-actions[bot]` on `janus/bump` with `--force-with-lease`, and opens or updates one draft pull request, never a fork's of the same branch name. A branch carrying a commit a person authored or committed is left alone. Nothing merges.
- A change to the workflow or the script runs it on its pull request as a dry run: nothing is opened, and a failing candidate is a warning there.
- `release --check` counts the `Dockerfile` as versioned, so a bump pull request cannot merge without the release commit a person pushes onto it (which is also what starts CI on it).
- The `morpheus-known-good` tag in the Janus repository no longer matters.
- Not done here: the GitHub setting that lets Actions create pull requests was off on 2026-11-17 (`can_approve_pull_request_reviews: false`). Until the owner turns it on, a run pushes the branch and stops with a link to open the pull request by hand.

*First bump (v0.175.0):* `eafb7aba` → `cc4620c0` (78 commits, still 0.18.0), opened by hand from the run's branch because of the setting above. The contract and the conformance suite pass on it. What the review of the commits found:
- `approvals.mode` now defaults to `smart`, but approvals only guard `terminal` and `execute_code` commands, and no turn loads either. Nothing written.
- Hooks gained `on_failure` (`warn`, the default, or `block`, which turns a failed `pre_tool_call` into a refused call). Linda's hooks are a display, so `activity.hooks_config` writes `warn` on each, and the contract fails a Janus whose parsed hooks would block. The release before reads only `command`, `matcher` and `timeout`, so the key is harmless on the fallback.
- `config.yaml.last-good` is used only when `config.yaml` fails to parse. The store tools and the `(empty)` reply in the conformance suite come from the generated config, so it is the one in effect. Harvest never reads the file.
- `state.db` gained `delivery_obligations` and `delegations` (the gateway's ledger and background delegation). `sessions` and `messages` are unchanged.
- Off by default and left off: memory provenance (`memories/provenance.db`), memory flush before compaction, skill versions (`skills/.versions/`, a dot-dir harvest skips), background and worktree delegation. First-run setup and the learning offer skip a scripted query.
- `clarify` takes several questions now; no turn loads it. MCP progress notifications reach the CLI spinner only; the store sends none.
- Janus's `mcp` extra moves from mcp 1.26.0 / starlette 1.0.1 to 1.28.1 / 1.3.1. pip-audit still reports mcp (fixed in 1.30.0) and pillow (12.3.0); reported, not blocking.

*P3b as shipped (v0.175.1):*
- Deleted `core/assistant/janus_updater.py`, `janus_runtime`'s `maybe_update`, `record_turn` (the rollback after three failed turns), `active_bin`, `source`, `summary` and the engine dir, the `LINDA_JANUS_AUTO_UPDATE` setting, the Janus app's `auto_update` setting with its checkbox, and the page's "Check now", "In use", "Last check" and "Commits it would not use". `janus_engine.janus_cmd()` runs `JANUS_BIN`, else the `janus` on PATH, else a source checkout; no file a turn can write chooses it (`test_janus_updates.py::EngineBinaryTests`).
- Kept `janus_runtime.installed_build` (no longer reads the updater's marker), `contract_report`, `PINS` (read by `scripts/bump_janus.py`) and `plugins/installed/janus/upstream.py`: the page still shows the build, its contract report and whether GitHub has a newer commit, and says a newer Janus arrives with a Morpheus release.
- A stored `auto_update` value stays in the janus app's row and is ignored, as v0.76.4 did with the settings it removed. No migration.
- `docs/plans/janus-replaces-linda-2026-09.md`: phase 5 is done (build and GitHub state on the page, the build on every run) and phase 6 is not needed (Janus moves by pull request, P3).

### P4 — Deferred tool schemas

- Measure first: the `tools` array P2 records, and P1's per-turn tokens and API calls from live turns.
- The stub's context length (Janus's 256K fallback) is not what a store's model reports, so the tool-search gate must be measured against the real provider, not the suite.
- Two outbound calls per turn found by P2, both Janus's: an update check (PyPI or git, in a background thread, on every chat) and, when Janus cannot size the context, a fetch of OpenRouter's model list with a 10 s timeout. Decide here whether the config switches them off.
- About 20 s of every turn is Janus starting up (plugin discovery, MCP connect, config load) before the first model call. Measure it on a store before choosing what to cut.
- `janus_engine._config_text` writes `tools.tool_search.enabled` and `threshold_pct` from a new janus setting `tool_search` (`off` / `auto` / `on`), default = what was measured as today's behaviour; reader `janus_settings.tool_search_mode()` in the same change; both keys and the bridge tools (`tool_search`, `tool_describe`, `tool_call`) join the contract.
- Follow-ups in the same release: labels for the bridge steps in `core/assistant/activity.py` (they produce no hook steps); one prompt line when deferral is on (skills name `orders.search`, the model must look for `mcp_morpheus_admin_orders_search`); a conformance scenario with `enabled: on` proving every call still crosses `gates.py`.
- Success: input tokens per live turn before and after (baseline about 180k).

*P4 as shipped (v0.176.0):*
- Read in the pinned Janus (cc4620c0, `tools/tool_search.py`): with tool search on, every MCP tool is deferred and the model gets three bridge tools, `tool_search`, `tool_describe` and `tool_call`; Janus's own tools (skills, todo, memory, session_search) stay loaded. `tool_call` is unwrapped before the hooks, so `pre_tool_call`/`post_tool_call` carry the real `mcp_morpheus_admin_*` name and the call goes through the same MCP session and the same `gates.py` chain. `tool_search` and `tool_describe` fire a pre hook only. A found tool is never added to `tools`, so each new tool costs two or three model round trips, and a batch holding a bridge call runs one call at a time.
- Ruling: the janus setting `tool_search` offers `off` and `on` only, default `off`, and every turn writes `tools.tool_search.enabled`. Janus's own default `auto` sizes the context from the config's `model.default`, which Morpheus writes as `auto`, so it fetched OpenRouter's catalogue (10 s timeout) on every turn: when openrouter.ai answered, the model reported 2M and every schema went; when it did not, Janus fell back to 256K and deferred them. A turn's tool list depended on a third party answering. `off` is what an answered fetch gave, so the default keeps today's normal behaviour and drops the fetch. No `threshold_pct` (it only matters for `auto`). Reader `janus_settings.tool_search_enabled()`; a stored value other than `on` reads as off.
- Measured in the conformance suite against the real pin (stub model): off, 250 tools (239 of them the store's), 140,271 bytes of schema per model call; on, 14 tools, 18,503 bytes.
- With it on, the system prompt's tool line becomes `prompts.TOOLS_ON_REQUEST` (search, describe, call; a dotted name in a skill is a store tool to search for), and the activity reader shows each lookup as a finished step (`activity._NO_END`), since no end line follows.
- Each home gets `.install_method` reading `docker`, which makes Janus skip its PyPI update check (every 6 hours per home). A soft contract check: losing it only brings back a check whose result nobody reads.
- Contract: `tools.tool_search.enabled` joins `CONFIG_KEYS`; the three bridge names join `NAMES`; the install stamp and the docker skip join `SOFT_NAMES`.
- Conformance: three scenarios with tool search on (only the bridge is offered; a bridged `orders.search` reaches the edge and shows as its own step; a bridged write still returns `approval_required`).
- Not measured: live input tokens per turn before and after, and Janus's start-up time on a store. Both need a read of live `AgentRun` rows, which waits for the owner's yes. Until then `on` is a per-store choice the merchant makes on Settings → AI → Janus, worth trying with a model whose input is expensive or whose context is small.
- Left for later, read but unchanged: Janus waits 0.75 s for MCP discovery before the first call; it probes the model server (`/api/show` and friends) every turn, and downloads models.dev's 6.7 MB catalogue hourly per home (`model.context_length` would skip both, but Morpheus has no reliable value to give it); a cost estimate fetches `GET /models` after the first response; per-server `tools.include`/`exclude` filters and `plugins.disabled` exist and are unused.

### P6 — Manifest compatibility and upgrades

- `plugins/base.py`: optional `min_morpheus` / `max_morpheus` (tuple compare, no dependency; missing = compatible; protected and system apps ignore it) and a no-op `on_upgrade(previous)`.
- Registry: an incompatible app, or one with an unmet `requires`, is not activated and is recorded in `registry.skipped[name]` with a reason, shown in `plugins.list` and on the Apps page. `PluginConfig.installed_version` written by compare-and-swap so `on_upgrade` runs once across processes.
- `morpheus.__version__` reads the real version; `scripts/check_api_stability.py` widens to the SDK doors, tool names, `MorpheusEvents` and contribution fields; `morph_create_plugin` scaffolds `help.md`, an agent-tools stub, `migrations/__init__.py` and a test; `docs/PLUGIN_DEVELOPMENT.md` corrected (`.plugin` → `.app`, protected count points at code, the `plugins.describe` promise).
- Tests: `core/tests/test_plugin_manifest.py`, including "every in-tree app is compatible with the current version". No migration.

**P6 as built (v0.179.0).**
- The live stores were read first (2026-11-18, read only): no app on any of the five has a missing or switched-off requirement and `installed_version` is empty everywhere, so the skip rule starts no outage and every store's first upgrade call gets `previous=''`.
- Upgrades run on `post_migrate`, not at boot: `safe_migrate` starts Django before it migrates. Only apps that are on and have a stored row, in dependency order. A raising step rolls back with its version write (the next deploy retries; the deploy never fails on it); a release put back records the lower version and runs nothing.
- A bound compares as many parts as it names (`'0.179'` = every 0.179.x). Protected, system and theme-required apps always start (`_keeps_running`), with an ERROR. A skipped app is retried on every switch-on pass (`_start_in_order`, also at boot, since a dependency cycle falls back to alphabetical order), and its reason is dropped when it is switched off.
- `check_api_stability.py` gates five surfaces; the baseline grew to 1,086 names, with no removal against the old one.
- The review changed four things: a requirement whose `ready()` raised no longer skips its dependents (storefront is not protected and requires orders); the version write and the step share one transaction (a container killed mid-step lost the step); app versions compare with their own key ('1.0' = '1.0.0', a pre-release before its release); a switch-off runs no `on_disable()` for a skipped app. Left as known limits: a store that updates in place without a container runs the step at its next migrate, and at boot a theme-required app counts as protected only once themes load (first request).

### P8 — Agent-coverage ratchet

- `scripts/check_agent_coverage.py` (stdlib `ast`, the shape of `scripts/check_plugin_boundary.py`): lists staff-gated views that accept POST; a view is covered by a module-level `AGENT_TOOLS = {'view': 'tool.name' | 'none: reason'}` whose tool must exist. Settings keys count as covered by `settings.set` after P7.
- Baseline `scripts/agent_coverage_baseline.json`, shrink-only, in the `ci.yml` lint job, with the count printed in the CI summary.
- Same release: agent_core's `orders.mark_fulfilled`/`mark_shipped` and GraphQL `markOrderFulfilled`/`markOrderShipped` go through `orders/fulfilment.py:create_fulfillment` (until v0.182.0 they recorded no parcel), by way of `mark_order`, which keeps each transition's own source statuses so an unpaid order is never walked forward.
- **As built (v0.182.0).** The scan also counts `request.FILES`, `request.body` and a `DashboardPage(view='dotted.path')` the router serves to staff; tools are found by name in `@tool`, `Tool(...)` and `register_tool` calls. Covered in this release: the settings panel (`settings.set`), the fulfil and refund forms (`orders.fulfill_lines`, `orders.refund`), and three security surfaces with a reason (a staff member's own account, the second-factor setup, API tokens). The Janus settings page stays in the baseline: it holds the key and the knobs `settings.set` may change, which P10 splits. So does the order notes form: it replaces or clears the notes, and `orders.add_note` only appends (review on PR #194).
- Not done here, by rule: flagging everyday writes `requires_approval` (the Worker cannot resume an approved call).

### P9 — App skills for Linda

**Status:** v0.187.0, in review (2026-11-22). Built as below; the staged folder is `<home>/store-skills/` with `core/` and one folder per app, and the Janus page's skills switch turns off both.

- `janus_engine._prepare_home` rebuilds `<home>/store-skills/` each turn from `core/assistant/janus_skills` plus `<app>/janus_skills/` of every active app, and `skills.external_dirs` points only there. A convention, not a hook: a disabled app's skills are gone next turn, and an agent's edit cannot outlive the turn or reach another conversation (today the external directory is the writable `/app` tree).
- Tests: `LindaCatalogueTests.test_prompt_and_skills_name_only_tools_linda_has` extends to app skill folders (a skill may name core tools and its own app's); staging tests in `test_janus_engine.py`. `docs/PLUGIN_DEVELOPMENT.md` gains the convention.

### P10+ — Tool batches

Each batch removes entries from the P8 baseline, ordered by merchant value: store operations (returns_portal, post_purchase, digital_products, cart_abandonment), compliance (consent, gdpr), channels and suppliers, developer (webhooks_ui, importers, cloudflare, tracking). From 2026-11-18, the returns_portal and post_purchase tools ship with C4 and C1, consent and gdpr come next, then the rest. Security surfaces (staff_mfa, Janus keys) and apps with no write surface are exempt with a stated reason.

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
9. `reasoning_tokens` read from Chat Completions' `usage.completion_tokens_details` too (today only `output_tokens_details`, so it is 0 for most providers).
10. `janus chat -q` honouring `--source` when it records the session (today always `cli`).
11. A switch for the "You run on Janus Agent… load the `janus-agent` skill" guidance that is appended after `SOUL.md` on every turn (`agent/system_prompt.py`), so an embedding product can drop it.
12. A `post_tool_call` hook for `tool_search` and `tool_describe`, like every other tool.
13. Promote a tool found by `tool_search` into `tools` for the rest of the turn, so a second call costs no lookup.
14. A config switch for the update check (today only the `.install_method` stamp skips it).
15. A configurable MCP discovery wait before the first model call (today a fixed 0.75 s).

Later, unscheduled: keep one subprocess per turn but speak the TUI-gateway JSON-RPC, which would give token streaming and a real mid-turn `clarify`.

## Out of scope

Installing apps that are not in the image, the app catalogue and licensing (morpheus.direct session; the static `data/apps_registry.json` is left alone). Uninstall with data removal. Any fork or patch of Janus for Morpheus.

## Afterwards: commerce

Superseded on 2026-11-18. Commerce no longer waits for this plan: the merged order in `docs/plans/platform-gap-analysis-2026-11.md` interleaves both, and Phase F adds the obligation and reach rows. From P8 on, each commerce row ships its agent tools under the ratchet.

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
- Janus starts the first model call after waiting 0.75 s for MCP discovery (read in its code, not observed live). With tool search on, a store tool that is not discovered in time would simply not be found; the conformance suite has not seen it miss.

## Flags for the owner (no action is taken on these without you)

- **Licence notice in the Janus repo.** The original "Copyright (c) 2025 Nous Research" line was replaced; MIT asks that it stay. Not legal advice; worth restoring.
- **Two Morpheus/Linda comments in the Janus repo** break the "Janus stays general" rule.
- **GitHub setting** "Allow GitHub Actions to create and approve pull requests" must be on for P3.
- The Janus repo has 13 open PRs and no version bump since the pin; item 6 of the upstream track is what makes future bumps readable.
- **P4's live effect is unmeasured.** Input tokens per turn before and after tool search need a read of live `AgentRun` rows, which waits for your yes. Until then `tool_search` stays each store's choice, off by default.
