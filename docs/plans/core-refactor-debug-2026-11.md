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
| SI3 | medium | `seo_gap` flags a product or page whose description the head fills from a fallback field; page gaps have no healer | open |
| SI4 | medium | The meta-description healer slices raw HTML | **fixed** |
| SI5 | medium | A class with no healer can be auto-applied or approved, then fails as `no_healer` out of the merchant's sight | **fixed** |
| SI6 | medium | The synonym healer writes to `catalog.SearchSynonym`, a model that does not exist | **fixed** |
| SI7 | medium | The nightly run keeps calling the model after a failure, swallows Celery's soft time limit, and `daily_token_budget` has no reader | **fixed** |
| SI8 | low | `code_quality` and `upstream_drift` collect nothing in the image (no ruff, bandit or git) and still record `ok` | open |

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
| D6 | low | Self-update (git installs only) migrates after a failed backup, and nothing stops two applies at once | open |
| D7 | low | `restore.spawn` passes `--confirm <name>`; a store or user name starting with `-` fails argparse and records nothing | **fixed** |
| D8 | low | `pg_dump` and `psql` ignore the configured `sslmode` | open |

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
| A4 | medium | The spend cap misses compaction calls, the daily briefing, timed-out runs and fallback answers | open |
| A5 | medium-low | After the tool lookup the runtime keeps the model's spelling (`catalog__update_product`) for approvals, usage counts and the audit trail | open |
| A6 | low-medium | The Worker gets the Developer-mode tools (`fs.*`, `logs.search`, `system.*`) | open |
| A7 | low | The breaker's response cache keeps empty replies for an hour and reports the original tokens again on a hit | **fixed** |
| A8 | low | `OpenAIProvider` always sends `max_tokens` and `temperature`, which o4-mini and gpt-5 are said to reject | open |

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
| G4 | medium | On the admin MCP `run_python` reaches `memory.recall` and other tools kept off tokens; Developer-mode tools are listed for plain tokens | open |
| G5 | medium | Under rbac `enforce`, only the admin role keeps the `system.read` tools | verified by the reviewer; owner's call |
| G6 | medium-low | `consume` reads then deletes: two concurrent identical calls can both spend one grant | **fixed** |
| G7 | low | Any staff member can apply a staged proposal; a double POST overwrites `applied` with `failed` | open |
| G8 | low | `fs.search_files` passes the query to grep without `--` | **fixed** |

Refactor candidates: `linda_turn.catalogue` rebuilds `gates.linda_tool`; `consent.clear()` hashes with
the wrong function and only a test calls it; `morph_ask` template tag is dead; docstrings that still
say `confirmed=True` means consent.

### Kernel seams

| # | Severity | Finding | Status |
|---|---|---|---|
| K1 | medium | The circuit breaker trips once: a failed half-open probe never re-opens it, so every later call waits out the provider | **fixed** |
| K2 | medium | loyalty_points registers its `ORDER_PAID` handler untagged, so points are still earned while the app is off | **fixed** |
| K3 | medium | `core/embeddings.py` calls `app_registry.get_plugin`, which does not exist, so the dashboard key is never used; hash-vector fallbacks are stored as real embeddings | open |
| K4 | medium-low | `StoreSettings.primary_currency` and `core_language` are on the settings form and nothing reads them; three rules for "store currency" disagree | verified by the reviewer; owner's call |
| K5 | low | Async hook handlers never run (the resolver walks the wrong path), and the SDK README documents a `mode='async'` argument `register_hook` does not take | open |
| K6 | low | The outbox drain releases its row locks before publishing (dormant: no `NATS_URL`) | open |

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
| E6 | medium | Settings → General → Permalinks saves templates nothing reads | verified by the reviewer; owner's call |
| E7 | medium-low | `audit.record` takes an unvalidated IP; on Postgres a junk value drops the row (`safe_db`) | **fixed** |
| E8 | low | `translation_problem` ignores a spec's `applies`; `i18n.translate_product` skips the check | open |

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

1. **Janus turn lifecycle (J1, J3, J5, J6, J7, J4).** A turn that outlives its HTTP stream, spend
   across a compressed session, a per-home lock, the unmapped-provider error. Needs the conformance
   suite, so it is its own release. The `janus_engine.py` split along its five seams belongs here.
2. **Spend accounting and the runtime's names (A4, A5, A6).** One helper for step saving and run
   finalisation (`agent_core/services.py` and `core/assistant/tools/spawn.py` hold two copies), which
   closes A4's gaps in one place.
3. **Self-improvement, second pass (SI3, SI8)** and its unreachable surface: policy classes with no
   producer, `Healer.propose()`, the `dead_link` healer.
4. **Owner's calls.** K4 (which of three "store currency" rules is the one), E6 (wire or remove
   Permalinks), G5 (which roles read `system.*` tools under enforce), K3 (embeddings would start
   calling the provider on stores whose key is in the dashboard), the `morph_i18n` template tags
   (unused here, but a theme outside this repository could load them).
5. **Smaller open items.** G4, G7, D6, D8, K5, K6, E8, A8, the five copies of version parsing, the
   two provider stacks, the approval machinery nothing resolves, `catalog/services/_helpers._download`
   (its own copy of the outbound check, and it follows redirects).

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
