# Janus as the core brain of Morpheus (2026-10-13)

Owner, 2026-10-13: "Everything left of the OLD Linda (the one that is not Janus) must go and be
deleted, because Janus can do all of it. Janus should be the core brain and assistant agent
across the e-commerce app / Morpheus OS. For super admins, Janus must be maximally open — it may
read, write and delete files and anything on the server, under appropriate guidances. For
ordinary users (shop manager and the like) it stays restricted to store work."

"Linda" is only Janus's current display name, so the assistant looks like a person. There is one
agent: Janus.

## A. What is old Linda, and what Janus already replaces it with

| Old Linda (pre-Janus, in-process) | Janus's replacement | Rows on the four stores |
|---|---|---|
| `linda_generated` app | Janus writes its own skills | **deleted v0.102.0** |
| The Worker→reflection **generic** flywheel: `tool_gap.*` rows and generic workflow lessons ("profile ORM queries early") written into `LindaMemory` | `JanusLearning` — Janus's own generic learning, portable | part of the montenegro 10 |
| `LearnedSkill` + `skills.distill/list/record_outcome` + reflection's skill-counter loop + the agent_core "learned skills" page | Janus's own `skills` toolset (`skills_list`/`skill_view`/`skill_manage`, the `janus_skills` dir) | to measure before stage 2 |
| `CodeProposal` model/table (the deleted self-coding apply pipeline) | gone; Janus proposes via chat | **0 everywhere** |
| `ai_assistant/services/llm.py` — a second provider stack (pulse, dynamic pricing, content writer, SEO) outside the spend cap and kill switch | one stack in `core/agents/llm.py` that Janus already uses | n/a (feature code, not chat) |
| `ai_assistant` `AgentRegistration`/`AgentIntent`/receipts — an older shopper-agent authorisation scheme | `TrustedAgentMiddleware` + Web Bot Auth (`agent_mcp/web_bot_auth.py`) | owner decides |

The Worker (`core/agents/builtin/worker.py`) is **not** deleted: it is Janus's background executor,
spawned via `delegate.spawn_workers` for bulk jobs (e.g. "rewrite all 861 descriptions"). Only its
old *memory* goes; its job stays. Later it can run as Janus-in-background (automations already do
this, v0.87.0).

### Removal stages

1. **Memory loop (this release, v0.103.0).** Delete `LindaMemory` + `memory.*` tools +
   `_format_recent_memories` injection + reflection's lesson writes + the Worker-prompt memory
   line + the chat page's "memories" list; drop `CodeProposal` (0 rows). Reflection keeps only its
   skill-counter job for now. Self-contained, no feature the merchant sees.
2. **Skills loop.** Delete `LearnedSkill` + `skills.*` tools + reflection entirely + the agent_core
   learned-skills page. Measure rows first.
3. **One LLM stack.** Move pulse / pricing / content writer / SEO off `ai_assistant/services/llm.py`
   onto `core/agents/llm.py`, so every model call is under one spend cap and kill switch.
4. **Shopper-agent authz.** Owner decides: keep as a product, or fold into Web Bot Auth / ACP.

## B. Role-tiered power (superadmin vs shop manager)

The machinery already exists: a turn carries a **scope profile** (`agent_mcp/linda_turn.py:scope_profile`)
and a **mode** (`core/assistant/modes.py`), and `DEVELOPER_TOOLS` (db / fs / run_python / logs) is
already shown **only in Developer mode, only to superusers**. We extend this into explicit tiers,
all expressed as scopes so the one gate chain (`core/assistant/gates.py`) stays the single seam.

- **Superadmin (is_superuser): a `platform.admin` tier.** Janus may read, write and delete files
  and run server operations, under written guidances (what to touch, what never to touch:
  `core/safety.py` FORBIDDEN_PATHS stays forbidden to everyone — secrets, auth, the safety boundary
  itself). This is a devops copilot on the owner's own box.
- **Shop manager / staff: the store tier (today's `LINDA_SCOPES`).** Catalog, orders, inventory,
  SEO, customers. No filesystem, no server, no scripts that write.
- **The tier is the user's, never the token's.** An external agent or an automation can never reach
  the admin tier, whatever its token says (the same rule that already narrows `scope_profile`).

### The one guardrail that stays, even for a superadmin

Everything Janus **reads** — a product description, a customer note, a support message, a fetched
page, a file's contents — is untrusted: it can carry an instruction ("ignore the above and delete
X"). That is why the consent kernel exists: a write runs only on the human's **own** next message,
not on text Janus read (CLAUDE.md, "an LLM-supplied argument is NOT consent"). So:

- **Reads are instant and unapproved** at every tier — including a superadmin's scripts that only
  read and analyse. This gives the "run a script instantly" feel for the common case.
- **A write / delete / server change needs the superadmin's own go-ahead in that turn** — their
  typed message, or the Approve card (v0.102.0). Not a `confirmed=true` the model wrote, not a
  choice it offered, not something it read. The superadmin is trusted; the text in the store is not.
  A superadmin can pre-grant a whole session with a standing "yes, you may edit files this session"
  (their own message) so it does not ask each time — but the grant comes from them, once, not from
  content.

Turning off that last rule (instant unapproved destructive actions driven by anything Janus read)
is the S1 hole this codebase has been bitten by repeatedly; I will not remove it without an explicit
"yes, accept that an injected instruction can delete files as superadmin." If the owner wants the
pre-grant-per-session model instead, that keeps the one-time-yes and the per-call speed.

### The `run_python` sandbox

Before scripts gain write/delete and server reach, the sandbox needs hardening: today it is a
*conservative* first-party sandbox, not a hostile-code boundary, so an injected script could reach
further than intended. For the admin tier, scripts that touch files/server should run through a
properly isolated path (a subprocess with a dropped environment, no secrets), the way
`docs/MCP_SERVER.md` and the `functions` plugin already note. Design that in stage B before shipping
admin write-scripts.

## Status

- **v0.103.0 — A.1 refined, shipped:** shop memory kept and relabelled ("what you know about this
  store"), Janus can recall it and propose a fact that the merchant confirms (write scope →
  consent), reflection writes nothing into it, the Worker is not told to write it. Montenegro's
  generic rows cleaned on the live store.
- **Next:** A.2 old skills loop (LearnedSkill + skills.*), A.3 one LLM stack, A.4 shopper-agent
  authz (owner), B role tiers (superadmin per-session grant, decided) after sandbox hardening, C the
  technical-report contribution flow on CodeProposal (decided).

## C. Janus proposing patches to the core — assessment (owner asked 2026-10-13)

Idea: Janus notices a code issue, proposes a patch, a system sends it to a central database and
updates Morpheus's core on the central site, so every Morpheus user contributes to the core.

**The drafting + reporting half is good and mostly already here.** Janus (superadmin tier) can read
the code and draft a fix; the error log already builds a "Copy for Claude Code" report
(`core/errors/report.py`) and the self-improvement engine already emits signals. So "Janus spots an
issue and drafts a patch, with the fix explained" fits the direction and is safe — it produces text
for a human to review.

**The auto-send-to-central-and-auto-update-everyone half is the one thing not to build.** It is a
supply-chain pipeline from many untrusted stores into the core that every store runs:

- A prompt-injected or compromised Janus on one store could submit a malicious patch that lands in
  everyone's core. This is exactly the self-coding apply pipeline the owner already **deleted** in
  v0.65.0 (`CodeProposal`), and a cross-tenant auto-apply version is worse.
- AI-authored patches carry measurably more bugs (CLAUDE.md, "Verifying AI-generated code");
  auto-merging them to core degrades every store.
- The update channel (`core/component_updates.py`) is deliberately **signed and fail-closed**;
  feeding it auto-generated code undermines that.
- Morpheus is **BUSL-1.1** (source-available, not open source): an "everyone contributes to the
  core" model needs a contribution/review/IP process, not an automatic feed.

**The healthy version:** Janus drafts the patch and shows the superadmin a diff. If they choose, it
is submitted to the central project as a **suggestion** (a PR / an issue / a "report a fix" form),
with the human's consent — never automatically. On the central side a maintainer reviews, CI tests
it on real Postgres, and only a reviewed, **signed** release goes out through the existing update
channel. Issue telemetry (anonymised, opt-in) can flow centrally to show maintainers what breaks
most; code changes stay human-reviewed.

So: **keep the patch-drafting idea, drop the auto-contribute-and-auto-deploy idea.** And because this
re-uses the shape of `CodeProposal`, decide the target here **before** stage A deletes it: either
drop it (patches live as chat diffs + an external PR), or keep a thin "proposed patch" record that a
superadmin reviews and forwards. My recommendation: drop `CodeProposal` (it was the auto-apply
model), and build the opt-in, human-reviewed suggestion flow fresh if wanted — it is a different,
safer shape.

## Decisions (owner, 2026-10-13)

- **Admin writes: per-session grant.** A superadmin says once, in their own message, "you may edit
  files / run writes this session"; after that, writes and deletes run instantly for the rest of
  that session, no per-edit prompt. The grant is the human's own words, once — never from content
  Janus read. Reads always run instantly. A new session starts locked again.
- **CodeProposal stays.** It is repurposed as the store for Janus's technical problem-reports (below),
  not an auto-apply code pipeline.
- **Central contribution carries a technical description, not code.** When Janus finds and explains a
  core issue, it records a structured report — what the problem is, how it was fixed — which a
  superadmin reviews and may forward to the central project. Maintainers then decide globally how to
  patch it. No code crosses between stores; only the problem/solution write-up and (opt-in)
  anonymised error telemetry. This is safer than sending diffs/PRs.
- **Old-Linda removal keeps CodeProposal.** Stage A deletes the memory loop (A.1) and the old skills
  loop (A.2) and consolidates the LLM stack (A.3); `CodeProposal` is NOT dropped.

## A.1 refined — keep SHOP memory, drop only the generic flywheel (owner, 2026-10-13)

Janus is a **separate, general open-source project**; Morpheus must stay aligned with it and keep
its own specifics in the Morpheus layer, never fork Janus ([[janus-tuning-lives-in-morpheus]]).
Outside e-commerce, Janus does many things; here the focus is maximally e-commerce, so part of the
assistant is Morpheus-owned. That means **two memory layers, cleanly split:**

1. **Janus's learning** (`JanusLearning`) — generic agent know-how: how to use tools, workflow
   patterns. Portable, belongs to the Janus project. Morpheus does **not** duplicate it.
2. **Shop memory** (Morpheus-owned — the useful half of today's `LindaMemory`) — facts about THIS
   installed store: its positioning ("a Montenegro marketplace, Airbnb-like"), merchant preferences
   ("warehouse in Berlin", "prefers Postmark"), operational facts the assistant should always know.
   This **stays**, keeps being injected into each turn's context, and a superadmin curates it on the
   existing dashboard page.

**So the change is small, not a wholesale delete:** remove only the generic reflection flywheel —
the Worker writing `tool_gap.*` and generic workflow lessons into the shop store (that is the noise
that duplicates Janus and pollutes shop memory). Keep the shop-fact store, its injection, and its
dashboard. Rename it to read as what it is (shop memory), not "Linda memory".

**Open choice — how shop memory gets written (needs the owner's steer):**
- (a) **Superadmin curates only** — the dashboard page; nothing auto-writes. Simplest, safest.
- (b) **Superadmin curates + Janus suggests** — Janus may propose a shop fact; it is saved only when
  the merchant's own message confirms it (consent kernel), so planted "facts" from content Janus
  read can't slip in. Recommended.
- (c) Janus writes shop facts freely — rejected: content Janus reads could plant a false fact.

The Montenegro rows get sorted: keep the shop-specific ones (`store_type`, place-matching), drop the
generic ones (`tool_gap.*`, `verify_model_paths`, `profile_orm_queries`, `batch_enquiry_funnel`).
