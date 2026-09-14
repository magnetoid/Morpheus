# Janus fully replaces Linda's engine (brand stays Linda)

Status: **Phases 1–3 SHIPPED and verified live** (v0.63.1 → v0.65.0, 2026-09-14).
**Phases 4–6 remain** and need an owner decision on a Coolify persistent volume
(4, 6) and on who signs Janus release artifacts (6). Pending polish (duplicate
breadcrumb on the Janus page) is on branch `fix/janus-page-polish`; ship it with
the next release. Update this file as phases land.

## Goal

Janus (github.com/magnetoid/janus, public Python agent) is the only engine
behind the merchant-facing assistant. The merchant still sees **Linda**. The old
in-process loop and the old Linda-only surfaces are removed. Janus stays
self-updatable. The merchant configures Janus from one dedicated settings page.

## Decisions (owner, 2026-09-13)

| Question | Decision |
|---|---|
| Interim fix on prod | Patch Janus now (shipped v0.63.1) |
| Integration shape | **Subprocess per turn**, with a signed per-turn identity so the MCP edge can enforce consent, modes and audit per merchant and conversation. No Janus-repo changes required. |
| "Self-updatable" | **All three:** track upstream Janus; update Janus in-app without redeploy; Janus keeps what it learns across deploys and conversations. |
| Settings | A **separate admin settings page** that configures Janus fully. |
| Old code | **Remove old Linda code and its API pages.** Owner confirmed all four groups in Phase 3 (A–D), 2026-09-14. |

## Why the order matters

The in-process loop is today the only place these are enforced (verified
2026-09-13, `runtime.py` `_gate_reason` / `_dispatch_tool`):

- scope profile, token budget, wall-clock deadline
- **human consent** for `requires_approval` tools (`core/assistant/consent.py`)
- staged-mode exemption only for `supports_staging` tools
- `assistant.tool_write` audit with the human as actor
- mode-chip tool filtering (`core/assistant/modes.py`)

The MCP admin edge Janus calls (`plugins/installed/agent_mcp/views.py`) enforces
none of consent, budget, deadline or mode filtering, runs every call as the shared
`mcp-service` user, and cannot tell which merchant or conversation a call is for.
Its `requires_approval` check is a standing per-token `approved_tools` grant.
**So the gates move to the edge (Phase 1) before the loop is deleted (Phase 3).**

## Current state after v0.63.1

- Turns run `janus chat -Q -t morpheus_admin,skills --provider … -m … --resume <id>`.
- Janus has no shell, file, code or browser tools.
- Provider and model come from `core.agents.provider_registry`.
- **Store tools still unreachable on prod:** `LINDA_MCP_TOKEN` is unset, so the MCP
  edge returns 401. Deliberately not "fixed" with a static token — that token
  would be the consent hole above. Phase 1 replaces it.
- Restricted modes (sales/support/ops) and tests still use the legacy loop.
- Janus home is container-local `/app/.linda-janus`, one dir per conversation,
  wiped every deploy.

## Release sequence

- **v0.64.0 — Phase 1** (+ tirith fix below). Makes store tools live with consent.
- **v0.65.0 — Phases 2 + 3** (settings app, deletions). Breaking: removed API endpoints.
- **Later — Phases 4–6** (need a Coolify volume; infra change confirmed at the time).

Carry into v0.64.0: first reply of every conversation on prod starts with Janus's
"tirith security scanner enabled but not available" warning (verified live on
v0.63.1). Set `security.tirith_enabled: false` in the generated config — tirith
only scans terminal commands, which are disabled, and while enabled it also starts
a background binary download every turn.

Verified live on v0.63.1 (2026-09-14): MCP client present; provider pinned to
`deepseek` / `deepseek-v4-pro`; a two-turn smoke recalled context through
`--resume`; 5–7s per turn.

## v0.64.1 hotfix (found verifying v0.64.0 live, 2026-09-14)

Every real Janus turn since v0.63.0 raised PermissionError: homes lived under
`/app/.linda-janus` and `/app` is root-owned in the image. Earlier prod smokes
patched the home, so they never exercised it. With a writable home, v0.64.0 was
verified live: a read turn called `products.search` through the MCP edge with a
turn token and answered in 16s. A consent probe ("activate the dot_books theme")
explored seven tools and hit the 55s timeout before calling `theme.activate`.
Fix: `LINDA_JANUS_HOME` / private temp dir, `HOME` pinned, `MAX_TOOL_TURNS = 8`.
Pre-existing tool bugs seen in that run (not fixed yet): `settings.list` raises
`AttributeError: 'PluginConfig' object has no attribute 'config_data'`;
`plugins.describe` accepts a call with no `name` and raises `TypeError`.
Also: sales mode lists 1 tool — its scopes (`catalog.read`, `orders.read`, …) do not
intersect Linda's profile, which uses `system.read`; same as the old loop. Phase 2's
scope settings should address it.

## Phase 1 — Per-turn identity and gates at the MCP edge

**Status: SHIPPED v0.64.0/v0.64.1, verified live.**
Landed as `core/assistant/turn_identity.py`, `core/assistant/gates.py` (the loop now
delegates to it), `plugins/installed/agent_mcp/linda_turn.py`, and the edge wiring in
`agent_mcp/views.py`. `LINDA_MCP_TOKEN` removed. Restricted modes now run on Janus.
Daily run/spend caps now refuse a new Linda turn (Linda turns themselves are not
counted — they create no `AgentRun`). Deviation from the list below: deadline stays
token expiry only; the in-process monotonic deadline is a no-op at the edge.
Also found and fixed while re-homing consent: a retry inside one turn could spend
that turn's own affirmative word ("…, ok?"). Consent now requires a human message
sent after the proposal, on both paths. Loopback MCP URL with `Host` +
`X-Forwarded-Proto` headers (plain loopback 301s on prod; public URL works but
round-trips Cloudflare).

1. **Turn token (core).** Mint a short-lived signed token per turn:
   `user_id`, `conversation_key`, resolved mode slug, turn nonce, expiry
   (turn timeout + margin). `django.core.signing` with a dedicated salt. Passed to
   Janus via env; config header uses Janus's `${ENV}` substitution, so no
   credential is written to disk.
2. **Gate chain extracted to core.** Move `_gate_reason` + `_audit_write_tool` into
   a core module callable from any dispatcher. Same order: kill switch → scope →
   mode → deadline (token expiry) → consent → staging.
3. **Edge enforcement (agent_mcp).** A request bearing a turn token resolves to the
   real staff user and conversation. `tools/list` and `tools/call` filter by the
   resolved mode. `requires_approval` goes through `consent.consume` against the
   conversation's latest stored `role='user'` message; a refusal records a pending
   consent and returns the same instruction text the loop returns today. Writes
   audit as `assistant.tool_write` with the human actor.
4. **Remove `LINDA_MCP_TOKEN`.** No static credential for Linda.
5. **Token budget.** Janus CLI reports no usage. Enforce `max_agent_runs_daily` per
   turn at `Assistant.stream`; note the USD cap gap explicitly.

Verify: port `test_enforcement.py` cases to the edge (consent single-use,
argument-bound, negation wins; scope; mode; audit of refusals). Live: a staff turn
reads orders; a refund is refused until the merchant says yes in the next message.

## Phase 2 — Janus settings page

**Status: SHIPPED v0.65.0, verified live 2026-09-14** (page renders for staff, engine installed, version shown, listed in the Settings sidebar).
Protected, catalogue-hidden `janus` app with one page at Settings → AI → Janus
(`/dashboard/apps/janus/engine/`): engine status, on/off, store-provider or pinned
provider (write-only key), tool-step cap, time limit, standing instructions,
bundled skills, and a connection test. Core reads it via
`core/assistant/janus_settings.py`. Dropped from the list below: per-skill toggles
(Janus's `external_dirs` is a directory, not a list of skills) and a "store data
Linda may read" scope picker — the catalogue's read tools declare `system.read`,
not the mode scopes, so it would have changed nothing. Settings changes are
audited as `janus.settings_changed` (key names only).

Owner: overlap audit first (`ai_assistant` owns provider settings, `agent_core`
owns guardrails, `agent_mcp` owns tokens). Default plan: a protected, system
`janus` app owning the page, config schema and update UI; the engine in core reads
it through a core accessor (the `core/agents/guardrails.py` pattern, via
`plugins.registry.app_registry`, never a plugin import).

Configurable:
- Engine on/off; installed version and upstream ref (read-only).
- Model: inherit the store AI provider (default) or override provider, model,
  base URL, API key (`format: password`, write-only).
- Max tool turns per message; turn timeout (capped under `GUNICORN_TIMEOUT`).
- Persona / extra instructions appended to Linda's prompt.
- Bundled skills on/off per skill; allow Janus to create and edit skills; memory on/off.
- Store tool scopes Linda may use (feeds the turn token).
- "Test Janus" button: one tiny turn, shows latency and provider result.

Locked, shown read-only with the reason: shell, file-write, code-execution and
browser toolsets; auto-approve (deploy-level env only, ADR 0014 posture).

Rule from CLAUDE.md: every field ships with its consumer in the same change.

## Phase 3 — Remove old Linda code and API pages

Blocked on Phase 1. **Owner approved deleting all of A–D (2026-09-14).**
**Status: SHIPPED v0.65.0, verified live** — removed endpoints return 404; staged-changes inbox 200; a real turn on the rewritten runtime called `products.search`. `CodeProposal` kept
as a retired model so its table is not dropped by a generated migration; drop it
deliberately.

| Group | What | Notes |
|---|---|---|
| A. Legacy loop | in-process `stream` loop, `_dispatch_tool`, `_repair_tool_args`, `_compact`, `_to_llm_messages`, `run_assistant`, mode fallback, loop-only tests, evals harness + `run_assistant_evals` | Required by the replacement. Gates already re-homed in Phase 1. |
| B. Legacy API | `ai_assistant`: `/api/agent-tools/openai.json`, `/api/agent-tools/anthropic.json`, `/api/mcp/tools/list`, `/api/mcp/tools/call` | Old GraphQL shim, CSRF-exempt, parallel to the real MCP server. Breaking for any external caller → `MIGRATING.md` + `API_STABILITY.md`. |
| C. Linda self-coding | proposals page, consensus, codegen, apply (`selfdev/*` branches), flywheel tool drafting | Needs `.git`; inert on the container. Janus has its own skill learning. |
| D. Unused chat JSON | `assistant/invoke/` | No in-repo caller besides a plan doc. |
| Keep | `/mcp/*/v1/` (agent_mcp), `assistant/stream/`, `history/`, `page-help/`, providers, persistence, prompts, memory/knowledge, `core/self_improvement`, the agent_core Worker | Janus depends on these, or they are not Linda. |

Verify: full suite, boundary guards, disable guards, `release --check`; grep for
dangling URL reversals and imports; compile changed templates.

## Phase 4 — Janus keeps what it learns

- One shared persistent Janus home on a Coolify volume (not per conversation);
  sessions separated by `--resume` ids in one `state.db`.
- Enable `skills` write + memory toolsets there (confined to the volume).
- Risk: prompt-injected content persisted as a skill. Mitigation: learned skills
  listed on the settings page with review/disable/delete; optional
  approve-before-use.
- Drop the history replay in the prompt once resume is reliable across deploys.
- Check `state.db` concurrency under parallel turns (Janus 4f311d03 "state.db resilience").

## Phase 5 — Track upstream Janus

Partly done in v0.65.0: the Janus page shows the installed version (`janus --version`, cached 10 min).

- Record installed Janus version and git ref at image build (build arg → env).
- Show both on Settings → Version & updates and the Janus page.
- Daily check against `magnetoid/janus` main / latest release; cached status and
  a self-improvement drift signal when upstream is ahead.

## Phase 6 — Update Janus in-app

- Persistent writable venv on the volume; `JANUS_BIN` points at it; the image's
  `/opt/janus` stays as fallback.
- Verified channel: signed manifest entry (`kind: engine`) with version + sha256 of
  a wheel. Download → verify → install into a new venv dir → `janus --version`
  smoke → atomic symlink swap → rollback on failure. Gated by `system.write` and
  an ops kill switch. **Never `janus update`:** for a non-git install it runs
  `pip install --upgrade janus-agent` from PyPI, not the owner's repo.
- Open: who builds and signs Janus wheels (GitHub Actions is billing-blocked;
  `morph_sign_manifest` on the release machine).

## Janus facts this plan relies on (verified 2026-09-13, Janus 0.16.0)

- `chat -q` counts as interactive; with YOLO off, dangerous shell commands wait
  `approvals.timeout` then deny. MCP tool calls have **no** approval path.
- Explicit `-t` replaces the default 56-tool `janus-cli` set.
- `-Q` prints only the answer to stdout and `session_id: …` to stderr.
- Bare `--continue` only finds `cli`-sourced sessions.
- MCP needs the `[mcp]` extra; headers support `${ENV}`; no `_meta`, no elicitation.
- Provider `auto` prefers OpenRouter when `OPENAI_API_KEY` exists.
- A failing turn takes ~22s locally (startup + provider call); MCP connect adds ~4s.
