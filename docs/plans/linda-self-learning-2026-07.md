# Linda: semantic memory, self-learning, proactive briefing, self-coding

**Status:** BUILT — R1+R2+R3 implemented & tested 2026-07-03 (v0.2.27,
pending ship) · autonomy level: **propose-only**
**Owner surfaces:** `core/assistant/`, `core/agents/`, dashboard contributions
**ADR trail:** ADR 0011 (one agent, grown via skills/tools), ADR 0014 (apply
engine, branch-only), ADR 0027 (agent-write governance)

## Goal

Upgrade Linda from a reactive chat assistant into a self-improving, proactive,
memory-bearing operator — by *wiring and awakening* primitives that already
exist (`LindaMemory.embedding`, `LearnedSkill` outcome counters,
`CodeProposal` → consensus → apply pipeline), not by rewriting the agent
kernel. Everything stays bounded by `core/safety.py`; no code Linda writes
ever reaches the repo without superuser approval, and never lands on `main`
by her hand.

## Non-goals

- No new agent classes (ONE Worker rule stands).
- No pgvector migration yet — plain-Python cosine over the bounded LindaMemory
  table; pgvector is a later drop-in when row counts warrant it.
- No auto-merge of self-written code at any autonomy level (owner chose
  propose-only).
- No unbounded "self-modification": `MORPHEUS_SELF_UPDATE_ENABLED` remains the
  master kill-switch for the apply step; the safety boundary is untouched.

## Release 1 — memory + self-learning

### 1a. Query-aware semantic recall (and fix the double injection)

Today memories are injected **twice per turn** — `build_system_prompt()` →
`_inject_memories()` adds a `[MEMORY]` section, and `runtime._to_llm_messages`
appends a second `REMEMBERED FACTS` system message via
`get_recent_memories()`. Both rank purely by recency/confidence
(`relevance_score()`); neither looks at what the merchant is asking.

Change:

- `get_recent_memories(limit, *, query='')` gains a query parameter. When a
  query is given, blend the existing `relevance_score()` with cosine
  similarity of the current user message against `LindaMemory.embedding`
  (same `_SEMANTIC_FLOOR=0.25` pattern `memory.recall` already uses; rows
  without embeddings fall back to decay-only score). Bounded candidate scan
  (≤ 4× limit, as now).
- `runtime._to_llm_messages` passes the user message as the query. The
  `REMEMBERED FACTS` system message becomes the **single** injection point.
- `prompts._inject_memories` is removed from `build_system_prompt()` (kept as
  a deprecated no-arg wrapper for one release in case anything imports it).
- Embedding backfill already exists (`backfill_memory_embeddings` management
  command) — verify it, wire nothing new.

### 1b. Reflection loop — close the learning circuit

`LearnedSkill.uses/successes/failures` exist but nothing writes them; Linda
learns skills and never finds out if they work.

New module `core/assistant/reflection.py`:

- `reflect_on_worker_run(run)` — called fire-and-forget at the end of
  `spawn._execute_worker_run` (both success and failure paths). One cheap
  no-tools LLM call (temperature 0, ~300 tokens) over the run's objective +
  final text + error, returning JSON:
  `{outcome: 'success'|'failure'|'unclear', lessons: [{key, value}], tool_gaps: [str]}`.
- Outcome updates each `LearnedSkill` named in the job's `skills` list:
  `uses += 1`, `successes`/`failures` per verdict, `last_used_at`.
- Lessons are written to `LindaMemory` with `source='inferred'` (existing 0.6
  confidence weight and decay handle quality control), capped at 2 per run.
- `tool_gaps` are stored as `LindaMemory` rows under scope `merchant`, key
  prefix `tool_gap.` — Release 3 turns these into `CodeProposal` drafts.
- **Auto-disable:** counter updates + auto-retire delegate to the existing
  `record_skill_outcome` (`core/assistant/tools/skills.py` — threshold:
  `uses >= 5 and success_rate() < 0.5`, unregisters from the live registry,
  signals self-improvement). Reflection adds a `skill_disabled.*` memory row
  (so Linda can tell the merchant why) and a `record_ai_decision` audit row.
- Linda conversation turns are NOT reflected on every turn (cost); only
  Worker runs, which have a crisp objective/outcome shape.
- Fail-soft everywhere: reflection errors never affect the run result.
  Reflection is skipped when no LLM provider is configured.

### Verification (R1)

- Unit tests: query-aware ranking (semantic beats stale-recency), single
  injection (no `[MEMORY]` section in `build_system_prompt()` output),
  reflection JSON parsing (via mock provider), counter updates, auto-disable
  threshold, fail-soft on provider error.
- `DATABASE_URL='sqlite:///:memory:'` run of `core.assistant` +
  `core.agents` suites.

## Release 2 — proactive daily briefing

**Overlap audit vs Linda's Pulse** (`ai_assistant/services/pulse.py`): Pulse is
rule-based — six hard-coded signals produce ranked alert *cards*; the LLM only
rephrases copy. The briefing is an *agentic* review — a tool-using Worker run
producing a narrative + delegable actions, discovering things no Pulse rule
covers. Distinct concepts, distinct owners: Pulse stays in the ai_assistant
plugin (disable-able alert cards); the briefing belongs to Linda herself
(core, like `ai_page_help`). Both render on home; neither imports the other.

- New Celery beat task `core.assistant.tasks.daily_briefing` (default 06:00
  store-local, registered in `morph/celery.py`). Skips when disabled or no
  provider configured.
- Spawns one Worker (existing spawn machinery, read-only tool set) with the
  objective: review last 24h — orders/revenue, new errors
  (`core.errors`), low stock, pending reviews, LLM spend — and produce a
  short briefing + up to 3 proposed actions.
- Result stored in a new small model `AssistantBriefing(date, body,
  actions_json, run_id)` (core/assistant, migration required).
- Dashboard home panel contributed via the existing `DASHBOARD_HOME_PANELS`
  filter (owned by core assistant, which is always-on, so the disable-test
  concern doesn't apply; still rendered only when the feature toggle is on).
- Proposed actions render as buttons that **prefill the Linda chat** with the
  action ("Ask Linda to do this") — reusing the existing two-step
  confirmed-write gates rather than building a parallel approval path.
- Master switch: `StoreSettings.ai_daily_briefing` (BooleanField,
  default False → opt-in; migration), surfaced next to `ai_page_help` in
  Settings → General.

### Verification (R2)

- Task unit test with mock provider; panel renders on home when enabled,
  absent when disabled; briefing survives provider failure (records a
  "skipped" row, no crash loop).

## Release 3 — self-coding (propose-only) + evals

### 3a. Approval queue UI

- Dashboard page **Settings → Developer → Linda's proposals** (superuser
  only), listing `CodeProposal`s: source (read-only, syntax-highlighted or
  `<pre>`), static-scan findings, consensus verdicts per provider, status.
- Buttons: **Run consensus review** (calls `consensus.evaluate`),
  **Approve** (calls `proposal.approve(user)`; apply-to-branch only runs when
  `MORPHEUS_SELF_UPDATE_ENABLED=true` — otherwise approve records the human
  verdict and the UI says the apply gate is off), **Reject**.
- Every decision audited (`AuditEvent`).

### 3b. Tool-gap flywheel

- Weekly beat task reads `tool_gap.*` memory rows; for gaps seen ≥ 2 times,
  Linda drafts a proposal via the existing `code.draft_tool` path (static
  scan included) and notifies the owner. Propose-only: nothing executes.

### 3c. Evals harness

- `core/assistant/evals/` — golden tasks as YAML (objective, allowed tools,
  success predicate over final text/tool trace), ~20 seed tasks.
- Management command `run_assistant_evals` runs them against the configured
  (or mock) provider and prints/stores a success-rate report; used before/after
  prompt or skill changes. Not wired into CI initially (provider cost) — CI
  runs the harness itself against the mock provider only.

### Verification (R3)

- Queue page permission tests (staff-but-not-superuser gets 404/403), approve
  flow test, evals harness runs green on mock provider.

## Risks

- **Reflection cost:** one small LLM call per Worker run. Bounded (max_tokens
  ~300, temp 0); skipped when unconfigured. Spend is visible in existing
  token accounting.
- **Inferred-memory pollution:** capped at 2 lessons/run, 0.6 confidence,
  60-day half-life decay + existing `decay_assistant_memories` cleanup.
- **Briefing hallucination:** Worker is tool-grounded and read-only; actions
  are proposals routed through existing confirm gates.
- **sqlite/Postgres migration drift:** two new migrations (StoreSettings
  field, AssistantBriefing) are additive-only — no FK retargets; CI
  real-Postgres migration job is the gate.
