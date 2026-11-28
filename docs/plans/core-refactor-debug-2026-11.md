# Core refactor and debug, November 2026

Owner's request (2026-11-27): "refactor whole core app and debug and fix". This is the register:
what an audit of `core/` found, what was verified, what shipped and what waits.

## How it was done

- Eight read-only reviewers, one per subsystem, read every non-test file under `core/` on
  `main` at `954be7f3` (v0.196.0). Each finding names the file, the trigger and the caller chain.
- Every finding is checked against the code, and reproduced with a failing test where one can be
  written, before it is fixed. A finding that could not be reproduced is listed as such.
- Refactors change no behaviour, keep every public name (`docs/API_STABILITY.md`) and come only
  with evidence: dead code proven by a repo-wide search, duplicates cited copy by copy.

## Size of `core/` (non-test lines)

| Subsystem | Lines | Tests |
|---|---|---|
| assistant | 9,183 | 6,956 |
| agents | 3,671 | 2,042 |
| self_improvement | 3,384 | 1,540 |
| errors | 2,159 | 557 |
| management commands | 1,553 | in `core/tests` |
| i18n | 1,418 | 756 |
| top-level modules | 9,782 | in `core/tests` (10,846) |
| auth, utils, templatetags, brain, emails, audit | 3,119 | in `core/tests` |

Seventeen functions are over complexity 10; the worst are `morph_bench.handle` (24),
`apply_component_update` (21) and `apply_platform_update` (20).

## Findings

Status: **fixed** (in v0.197.0, with a test that failed before the fix), **open** (reported by a
reviewer with a trigger and a caller chain, not fixed in this release), **owner's call** (the fix is
a product decision).

### self_improvement

| # | Severity | Finding | Status |
|---|---|---|---|
| SI1 | high | `run_analyzer` slices the top 50 clusters before it drops those that already have an open recommendation, so a store with 50+ standing gaps never gets a new recommendation | **fixed** |
| SI2 | medium | Rejecting or snoozing a recommendation older than 30 days writes no suppression (its evidence signals are pruned), so it returns the next night | **fixed** |
| SI3 | medium | `seo_gap` flags a product or page whose description the head fills from a fallback field; page gaps have no healer | not fixed here: self-improvement moves to Janus (owner, 2026-11-28) |
| SI4 | medium | The meta-description healer slices raw HTML | **fixed** |
| SI5 | medium | A class with no healer can be auto-applied or approved, then fails as `no_healer` out of the merchant's sight | **fixed** |
| SI6 | medium | The synonym healer writes to `catalog.SearchSynonym`, a model that does not exist | **fixed** |
| SI7 | medium | The nightly run keeps calling the model after a failure, swallows Celery's soft time limit, and `daily_token_budget` has no reader | **fixed** |
| SI8 | low | `code_quality` and `upstream_drift` collect nothing in the image (no ruff, bandit or git) and still record `ok` | not fixed here: self-improvement moves to Janus (owner, 2026-11-28) |

Refactor candidates: the weekly digest that sends nothing (`digest_weekly`, `weekly_digest_v1`,
`digest_recipients`); policy classes and the `dead_link` healer with no producer; `Healer.propose()`
(four implementations, no caller); duplicate `_parse_json` in `recommend.py` and `verify.py`;
docstrings that promise a suppression pass, a pre-plan filter and a `register_collector` hook
that do not exist.

### Deploy, restore and updates

| # | Severity | Finding | Status |
|---|---|---|---|
| D1 | medium | `morph_backup --dest` accepts a folder under `MEDIA_ROOT`; the backups app passes its staff-editable `backup_dir`, and `/media/` is public | **fixed** |
| D2 | medium | The migration gate misses an `AlterField` that changes `db_column` (a column rename) and `AlterOrderWithRespectTo` (a NOT NULL `_order` column) | **fixed** |
| D3 | low | The gate's file pattern (`\d{4}_\w+\.py`) skips a hand-named migration file that Django still loads | **fixed** |
| D4 | low | A backup on an engine that is neither postgres nor sqlite (`postgis://`) writes no dump and exits 0 | **fixed** |
| D5 | low | `release` writes `settings.py` before it builds the notes entry, so a notes failure leaves the version bumped alone | **fixed** |
| D6 | low | Self-update (git installs only) migrates after a failed backup, and nothing stops two applies at once | **fixed** (v0.200.0) |
| D7 | low | `restore.spawn` passes `--confirm <name>`; a store or user name starting with `-` fails argparse and records nothing | **fixed** |
| D8 | low | `pg_dump` and `psql` ignore the configured `sslmode` | **fixed** (v0.200.0) |

Refactor candidates: version parsing in five places with different rules (`core/deploys.py`,
`scripts/deploy_guard.py`, `release.py`, `core/update_sources.py`, `plugins/compat.py`; the update
channel's `is_newer('1.0.0', '1.0')` is True); `morph_sign_manifest` writes keys no client reads and
omits the ones the client needs; `_ships_with_core` checks themes by git alone; a dead
`except SystemExit` in `morpheus.py`; `morph_backup`'s stale docstring.

### Request path, auth and email

| # | Severity | Finding | Status |
|---|---|---|---|
| R1 | high | `core/net.py`: `http://127.0.0.1:PORT\@example.com/` passes the outbound check as example.com and `requests` connects to 127.0.0.1; 100.64.0.0/10 counts as public | **fixed** |
| R2 | high | `StorefrontCacheMiddleware` (outer) marks cart, checkout and cookie-carrying pages `public` once a store has saved Settings → Caching; it has no cookie check | **fixed** |
| R3 | high | `serve_media` answers a sold file to staff with no `Cache-Control`, so the CDN in front of `/media/` may cache it | **fixed** |
| R4 | medium | `_safe_next` accepts `/\evil.example` (open redirect after the emailed-code sign-in); staff_mfa has the same copy | **fixed** |
| R5 | medium | The first `X-Forwarded-For` entry is used unvalidated as the client IP: a junk value is a `DataError` 500 on Postgres and rotates the rate-limit key | **fixed** |
| R6 | medium | The OpenTelemetry scrubber writes to an immutable attribute map after the span ended; the error is swallowed and nothing is scrubbed | **fixed** |
| R7 | medium-low | The sign-in code email is sent with `fail_silently=True` and no `EMAIL_TIMEOUT` | **fixed** |
| R8 | low | With Redis down, `cache.incr` returns None and a wrong code answers 500; guessing is unthrottled | **fixed** |

Refactor candidates: `core/utils/cache.cache_graphql_query` (no callers) and the `rest:*` pattern nothing
writes; `HasScopePermission` (no callers); `core/images.py` drops the config cache on every read;
`safe_db` has no savepoint; about 14 modules derive the client IP on their own.

### Agents runtime

| # | Severity | Finding | Status |
|---|---|---|---|
| A1 | high | An open circuit, a failed fallback and an unconfigured provider answer with their message as reply text; the content-fill view and `catalog.fill_missing_content` save it as product copy | **fixed** |
| A2 | high | `run_python`'s validator blocks dunder attributes only; frame attributes (`gi_frame`, `f_back`, `f_globals`) are a way out (Developer mode, superusers) | **fixed** |
| A3 | medium | The Gemini key rides in the URL (`?key=`), and `requests`' error text carries the URL into `AgentRun.error`, API answers and Janus's context | **fixed** |
| A4 | medium | The spend cap misses compaction calls, the daily briefing, timed-out runs and fallback answers | **fixed** (v0.199.0) |
| A5 | medium-low | After the tool lookup the runtime keeps the model's spelling (`catalog__update_product`) for approvals, usage counts and the audit trail | **fixed** (v0.199.0) |
| A6 | low-medium | The Worker gets the Developer-mode tools (`fs.*`, `logs.search`, `system.*`) | **fixed** (v0.199.0) |
| A7 | low | The breaker's response cache keeps empty replies for an hour and reports the original tokens again on a hit | **fixed** |
| A8 | low | `OpenAIProvider` always sends `max_tokens` and `temperature`, which o4-mini and gpt-5 are said to reject | **fixed** (v0.200.0) |

The July item: the reaper exists (`agent_core.sweep_stuck_runs`); `awaiting_approval` can still stick,
and a live spawned Worker older than 15 minutes is swept while it runs.

Refactor candidates: two provider stacks (`core/agents/llm.py`, `ai_assistant/services/llm.py`) that
have drifted; approval machinery nothing ever resolves (`AgentApprovalRequest` is never approved);
step saving copied in `agent_core/services.py` and `core/assistant/tools/spawn.py`.

### Janus engine and learning

| # | Severity | Finding | Status |
|---|---|---|---|
| J1 | high | A turn whose HTTP stream ends early (tab closed, worker recycled) loses its answer and its spend; the Janus child can outlive its deadline | **fixed** (v0.198.0) |
| J2 | high | An external agent's turn hydrates and harvests the store's Janus learning, and every API token shares one `USER.md` | **fixed** |
| J3 | medium | Context compression opens a continuation session; this turn's spend on the parent session is not counted | **fixed** (v0.198.0) |
| J4 | medium | A store provider Janus has no mapping for (openrouter, apikey, packy, moonshot, ollama) falls through to Janus `auto` | **fixed** (v0.198.0) |
| J5 | low-medium | Two turns of one conversation at once: the second hydrate wipes the first turn's unharvested notes | **fixed** (v0.198.0) |
| J6 | low | Two harvests creating the same new path roll each other back (`IntegrityError`) | **fixed** (v0.198.0) |
| J7 | low | The Janus connection test runs a real turn outside the kill switch and the spend cap | **fixed** (v0.198.0) |

Refactor candidates: `janus_engine.py` splits along five seams (binary, provider wiring, home and
config, state.db reader, turn runner), with about 45 test patches that must keep resolving;
`_provider_wiring` resolved three times a turn; `bundled_skill_names()` and the JSON-envelope branch
of `_turn_result` are dead; three state.db helpers each open their own connection.

### Assistant gates, consent and tools

| # | Severity | Finding | Status |
|---|---|---|---|
| G1 | high | A declined proposal stays pending for its 10 minutes, so the next "yes" (to another proposal) approves it too | **fixed** |
| G2 | high | `delegate.spawn_workers` and `delegate.invoke_agent` need only `system.write`: a narrowed token can start the every-scope Worker | **fixed** |
| G3 | medium-high | "yes, but not that one", "ok except the second" read as a yes | **fixed** |
| G4 | medium | On the admin MCP `run_python` reaches `memory.recall` and other tools kept off tokens; Developer-mode tools are listed for plain tokens | **fixed** (v0.200.0) |
| G5 | medium | Under rbac `enforce`, only the admin role keeps the `system.read` tools | owner's call; belongs with role grants and the enforce dry-run (row 17 of the platform order) |
| G6 | medium-low | `consume` reads then deletes: two concurrent identical calls can both spend one grant | **fixed** |
| G7 | low | Any staff member can apply a staged proposal; a double POST overwrites `applied` with `failed` | **fixed** (v0.200.0) |
| G8 | low | `fs.search_files` passes the query to grep without `--` | **fixed** |

Refactor candidates: `linda_turn.catalogue` rebuilds `gates.linda_tool`; `consent.clear()` hashes with
the wrong function and only a test calls it; `morph_ask` template tag is dead; docstrings that still
say `confirmed=True` means consent.

### Kernel seams

| # | Severity | Finding | Status |
|---|---|---|---|
| K1 | medium | The circuit breaker trips once: a failed half-open probe never re-opens it, so every later call waits out the provider | **fixed** |
| K2 | medium | loyalty_points registers its `ORDER_PAID` handler untagged, so points are still earned while the app is off | **fixed** |
| K3 | medium | `core/embeddings.py` calls `app_registry.get_plugin`, which does not exist, so the dashboard key is never used; hash-vector fallbacks are stored as real embeddings | **fixed** (v0.200.0) |
| K4 | medium-low | `StoreSettings.primary_currency` is on the settings form and nothing reads it (`core_language` beside it came with the localization plan and has no reader yet either); three rules for "store currency" disagree: `settings.STORE_CURRENCY` (`core.pricing`), the currency most active products carry (`plugins/dropshipping/importer.py`, which shipping rates use), and the unread column | owner's call |
| K5 | low | Async hook handlers never run (the resolver walks the wrong path), and the SDK README documents a `mode='async'` argument `register_hook` does not take | **fixed** (v0.200.0) |
| K6 | low | The outbox drain releases its row locks before publishing (dormant: no `NATS_URL`) | **fixed** (v0.200.0) |

Refactor candidates: `core/channels.py` per-channel pricing has no caller; `LLM_BREAKER`,
`WEBHOOK_BREAKER` and `CDN_BREAKER` have no users; webhook signing exists three times; every `fire()`
serialises its payload before it knows whether an endpoint wants it; events documented and never
fired (`SEO_ENTITY_ADAPTERS`, `SEO_SITEMAP_SOURCES`, `AI_DESCRIPTION_GENERATED`, `CART_CALCULATE_TOTAL`).

### Errors, audit and i18n

| # | Severity | Finding | Status |
|---|---|---|---|
| E1 | high | The server fingerprint uses the three outermost frames (Django's handler and middleware), so every error of one class on any app page lands in one group | **fixed** |
| E2 | high | The anonymous client-error endpoint rate-limits on the forgeable first `X-Forwarded-For` entry, and an undecodable body is a 500 | **fixed** |
| E3 | medium-high | One view exception is stored twice: by the middleware and by the `django.request` log handler | **fixed** |
| E4 | medium-high | Redaction misses `?key=AIza…`, `client_secret=`, `redis://:pw@`, `Cookie:`, the whole `lt1.` token; the client page URL is stored raw | **fixed** |
| E5 | medium | Anonymous text is fenced with three backticks in "Copy for Claude Code" and can close the fence | **fixed** |
| E6 | medium | Settings → General → Permalinks: only the travel app's menus read the templates (`booking_marketplace/context_processors.py`); an override changes the link and no route follows it. The reviewer's "nothing reads them" was wrong | owner's call |
| E7 | medium-low | `audit.record` takes an unvalidated IP; on Postgres a junk value drops the row (`safe_db`) | **fixed** |
| E8 | low | `translation_problem` ignores a spec's `applies`; `i18n.translate_product` skips the check | **fixed** (v0.200.0) |

Refactor candidates: the `morph_i18n` template tags and `translated()` / `get_translation()` have no
users; `PermalinkResolver` and `core/graphql/types.ErrorType` have no callers; `core/errors/services.py`
does five jobs.

## What v0.197.0 shipped

Thirty-eight findings fixed, each with a test that failed first: all the high ones except J1, and
the contained medium and low ones. Refactors, all without behaviour change: one JSON parser for
model replies (`core.llm_parsing.parse_llm_object` replaces four hand-rolled copies), one rule for
both cache layers (`core.storefront_cache.may_be_public`), one validated client-IP helper
(`core.ratelimit.client_ip_address`), one stand-down rule in the analyzer, and dead code removed
(per-channel pricing helpers, a cache decorator, two money helpers, three unused breakers, the
synonym healer, the weekly digest that sent nothing, `consent.clear`, `bundled_skill_names`).

Dismissed: `core/graphql/types.ErrorType` is used (orders' GraphQL); `HasScopePermission` is a
documented extension point (`SKILLS.md`); the `morph_assistant` tag library is loaded by the
dashboard shell.

## Next batches

Batches 1 to 4 are shipped (v0.197.0 to v0.200.0; see the sections below). What is left is not a
batch of fixes:

1. **Self-improvement moves to Janus** (owner, 2026-11-28; the section below). SI3, SI8 and the
   unreachable surface (policy classes with no producer, `Healer.propose()`, the `dead_link`
   healer, the weekly digest that sends nothing) are not fixed in place.
2. **Owner's calls.**
   - K4: which rule is "the store currency". Making the dashboard's field win would re-price a
     store whose field still holds its `USD` default, so it needs each store's values first.
   - E6: route the permalink templates, or keep them to the travel menus and say so on the page.
   - G5: which roles read the `system.read` tools under enforce; planned with role grants.
   - The `morph_i18n` template tags: unused here, but a theme outside this repository could load
     them.
3. **Not code.** Forwarded client addresses (`CF-Connecting-IP`, `X-Forwarded-For`) can be forged
   only by reaching the origin past Cloudflare. A list of trusted proxies in the app would not help
   on these servers: every request reaches Django from the same reverse proxy, forged or not. The
   fix is at the network: let only Cloudflare's ranges reach the origin's ports.
4. **Left as they are.** The five version parsers read different things (a release tag, an app
   version with a pre-release, a manifest's); the one wrong answer among them is fixed. The two
   provider stacks (`core/agents/llm.py`, ai_assistant's gateway) are both guarded and counted;
   merging them is a project of its own. Dead code named by the reviewers (`core/channels.py`
   pricing, the three unused breakers, `morph_ask`, `bundled_skill_names()`) stays until someone
   needs the file: three of their "dead" claims were wrong, and E6 made four.

## Direction for self-improvement (owner, 2026-11-28)

The owner's rule: Janus controls self-improvement, and Morpheus only displays the results. When
Janus is updated, or arrives in a Morpheus install as the external app it is, it brings the skills
and plugins that do this work for a store.

What that means for `core/self_improvement/` (about 3,300 lines without tests: collectors, the
analyzer, healers, policies, the nightly task):

- Nothing new is added there, and nothing is polished. Only a defect that breaks a store is fixed.
- The scans (SEO gaps, search misses, code quality, upstream drift) and the fixes become Janus's:
  a store skill per job (`core/assistant/janus_skills/`, an app's own `janus_skills/`), run by an
  automation on the store's clock, working through the store's tools under the one gate chain, so
  a write still needs the merchant's yes.
- Morpheus keeps the record and the page that shows it: what was found, what was proposed, what
  was applied (`SiRecommendation`, the dashboard's self-improvement page in
  `admin_dashboard/views_split/self_improvement.py`), written by Janus through tools.

Not designed yet, and to be decided there: which collectors become skills and which become plain
tools Janus calls; what runs when Janus is switched off (today the loop runs without it); how the
spend of a nightly Janus run is capped; and what happens to the safety boundary's readers
(`core/safety.py` stays core).

## From the security review of the fix (no critical or high finding)

- The client IP comes from `CF-Connecting-IP`, then the first `X-Forwarded-For` entry. Neither is
  authenticated when the origin can be reached without Cloudflare, so a per-address rate limit can
  be rotated there. The per-email lock on emailed codes and the store-wide cap on browser error
  reports still hold. Trusting the header only from a known proxy range needs the deployment's
  proxy addresses: open, owner's call.
- The store-wide cap on anonymous browser error reports (300 a minute) can be used up by a caller
  with several addresses, which drops real visitors' reports for that minute. Chosen over an
  unbounded table.
- The wider negation list refuses some real approvals ("ok, that's not a problem"). It fails
  closed: the change is proposed again and the Approve button always works.

## What v0.198.0 shipped (batch 2, the Janus turn lifecycle)

J1, J3, J4, J5, J6 and J7, each with a test that failed first (`core/assistant/tests/test_turn_lifecycle.py`
and additions to the engine, learning and janus app suites).

- A turn whose reader left is drained in the background, so its answer, usage, run and learning are
  stored. Still lost: the reply of a turn whose web worker is recycled or redeployed mid-turn (the
  drain thread dies with the process). Its spend is billed by the conversation's next turn.
- Janus starts under coreutils `timeout`, so it stops at its deadline when its parent is gone.
- Spend is the home's total less what was billed; one turn per home; the journal's first entry of
  the day no longer rolls a second harvest back; an unmapped store provider is refused; the
  connection test obeys the kill switch and the spend cap.

Not done: the `janus_engine.py` split. The fixes changed about 320 lines of that file and need the
conformance suite's verdict first; moving 1,300 lines in the same release would hide them in the
diff. It is the next refactor, on its own.

Before deploying: a store whose AI provider is openrouter, apikey, packy, moonshot, ollama or hermes,
with Janus on "the store's provider", gets the refusal on every message until a provider is chosen
under Settings → AI → Janus. Those turns ran on Janus's `auto` before.

## What v0.199.0 shipped (batch 3: what a run spends, tool names, the Worker, the engine split)

A4, A5 and A6, each with a test that failed first, and two refactors without behaviour change.

- **A4, spend.** The runtime adds every provider answer to a meter the caller owns
  (`core/agents/usage.py`), the compaction summary included. One module saves a run
  (`core/agents/run_store.py`: steps, audit rows, the end of the run) for `run_agent` and the spawned
  Worker, which each had a copy. A run that timed out or raised now keeps its tokens and its model,
  and the thread a timeout leaves behind writes its last tokens when it ends. A run answered by the
  fallback router's secondary keeps the split in `metadata['usage_by_model']` and is priced per
  model. The daily briefing, and a run whose row could not be created, are counted in
  `ModelUsageDay`.
- **A5, names.** After the tool lookup the runtime uses the tool's registered name for the trace,
  the audit trail, the events and the approval request. Tool schemas go to the model under the
  provider-safe spelling (`catalog__update_product`), so that is what models answer with: until now
  every approval request, usage count and audit row of a Worker run carried it, and an approved
  request could never be found by the resolver, which looks up the dotted name.
- **A6, the Worker's tools.** The Worker is never offered `gates.DEVELOPER_TOOLS`. It held seven of
  them (`fs.list_dir`, `fs.read_file`, `fs.search_files`, `logs.search`, `system.disk_usage`,
  `system.git_log`, `system.server_info`), and so did the briefing's read-only Worker.
- **Found on the way.** A run was counted against the daily run cap by its own row whenever its
  caller did not put the row in the context (a spawned Worker), so the cap was one lower for those.
  A spawned Worker's run never said when one of its steps could not be saved.
- **The engine split.** `janus_engine.py` (1,398 lines) is the turn runner (632); `janus_binary`,
  `janus_providers`, `janus_home` and `janus_sessions` hold the rest. All 86 top-level definitions
  moved unchanged (compared by syntax tree), every name still resolves on `janus_engine`, and eight
  test patches moved to the leaf whose function reads the patched name.

Left alone, noticed during the split:

- `_mcp_endpoint({'mcp_public': True})` returns `https:///mcp/admin/v1/` when `ALLOWED_HOSTS` holds no
  concrete host, so an automation's turn would get a URL with no host instead of an error.
- Three tests patch `engine_root` on a path that never reads it once `janus_cmd` is mocked.
- Three near-identical read-only `sqlite3.connect` blocks in `janus_sessions`; `_settings()` cannot
  return None, so its `if s else` branches are dead; `engine_root()` also checks
  `BASE_DIR/vendor/janus`, which its docstring does not list.
- The approval flow can now find an approved request by name, but nothing re-invokes a paused run,
  so the standing rule holds: never flag an everyday write.
- An error raised inside a moved function gets a new error-group fingerprint once, because the file
  name is part of it.

Not verified outside CI: the conformance suite (the pinned Janus against a stub model) skips
locally; CI's `janus-conformance` job is the proof that the split changed nothing for a real turn.

## What v0.200.0 shipped (batch 4: the small open items)

D6, D8, A8, G4, G7, K3, K5, K6 and E8, each with a test that failed against the old code (37 of the
171 tests in the touched modules failed or errored there), plus three found on the way.

- **G4.** An API token is never offered `run_python` (`gates.NOT_FOR_TOKENS`). Its script bridge
  falls back to the whole default catalogue for a caller that is not an agent run and checks no
  scope there, so a token with `system.read` alone read orders, customers and the shop memory. The
  other Developer tools a token can list (`db.*`, `platform.capabilities`, `plugins.describe`,
  `delegate.list_agents`) only describe the platform and stay.
- **G7.** A proposal is approved by a staff member whose role allows the change, while roles are
  enforced, and approval is one swap in the database, so two clicks apply once.
- **D6, D8.** A self-update (platform, app or theme) stops when its backup fails, runs alone, and
  `pg_dump` / `psql` connect with the TLS options Django uses.
- **A8.** The OpenAI provider asks again with `max_completion_tokens` and the default temperature
  when a model refuses the older parameters, and remembers the model. Checked against the
  reports for o4-mini and GPT-5: both refuse `max_tokens` and a set `temperature` with a 400.
- **K3.** Embeddings read their key in one place. The store's key is used only once the merchant
  switches ai_assistant's `embeddings_use_store_key` on (off by default: it starts paid requests
  the spend cap does not count), and a vector is kept only when it is comparable with the others.
- **K5, K6.** An async hook handler runs; the outbox drain locks each row for its own publish.
- **E8.** A translation its page would never show is refused, also by `i18n.translate_product`.
- **Found on the way.** catalog's file download checked only the first host, by name, and followed
  redirects on its own (`core.net.outbound_request(max_redirects=)` now carries it). The update
  channel read `1.0.0` as newer than `1.0`. A scheduled turn on a store that names no host got
  `https:///mcp/admin/v1/`; it now fails with the reason.

- **Both provider stacks.** ai_assistant's gateway sent the same older parameters; both now ask
  through `core.agents.llm.chat_completion`.

From the security review of this batch (one pass over the whole diff; no critical or high finding),
fixed before it shipped: a 400 about the value of `max_tokens` read as the refusal, and the model
was remembered before the second call had worked; Reject overwrote an applied proposal's status;
`changes` stored as something other than a list of objects raised in `approve` and `apply`; the
update lock file was opened through a link; a refused redirect was left open, and a followed one
would have carried a body or a credential to another host (only a plain GET follows now).

Left as they are, from the same review:

- `OpsProposal.apply()` still accepts a proposal that is only 'proposed'. The view always approves
  first; a new caller must too, or it skips the capability check.
- The dashboard and Linda's `updates.apply` have no way to update without a backup; only the
  command line does (`--allow-without-backup`). Meant: the door that skips the backup is the one
  an operator types.
- Two async handlers of one event with the same name (two lambdas from one function) resolve to
  the first.

Not verified outside tests: no self-update was run on a git install, no OpenAI reasoning model was
called, and no store has `embeddings_use_store_key` on.
