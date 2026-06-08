# Linda → self-learning, self-building agent (Hermes-grade uplift) — 2026-06

> Goal: give Linda the "maximum powers" of NousResearch's **Hermes Agent** — a
> persistent, self-improving agent that **creates its own skills from experience,
> writes its own modules/programs, and improves over time** — while keeping ONE
> agent (ADR 0011), a tiny core (ADR 0010), and the safety boundary intact.
> This is an UPLIFT: Linda already owns most of the substrate; we close the gaps.

## 1. What Hermes is (analysis)
Hermes Agent (NousResearch, open-source, ~180k★) is a persistent self-improving
agent. Standout mechanisms:
- **Closed learning loop:** *autonomous skill creation after complex tasks*;
  *skills self-improve during use*; agent-curated memory with periodic nudges.
- **Skills** as modular, versioned components (agentskills.io open standard);
  `/skills` + `/optional-skills`; importable.
- **Deepening user model:** FTS5 session search + LLM summarization for
  cross-session recall; dialectic user modeling; `SOUL.md` (persona) /
  `MEMORY.md` / `USER.md`.
- **Code/tool generation + execution:** writes Python scripts that call tools via
  RPC (collapsing multi-step pipelines); subagent spawning; sandbox backends
  (local / Docker / SSH / Modal / Daytona).
- **Safety:** command-approval allowlists, container isolation, per-workspace
  config, approval thresholds.
- Runs on **Hermes 3/4** (native `<tool_call>` function-calling) but is
  provider-agnostic (15+ providers).
Sources: hermes-ai.net, github.com/nousresearch/hermes-agent, nousresearch.com/hermes3.

## 2. What Linda already has (the substrate — do NOT rebuild)
- **Self-improvement engine** (`core/self_improvement/`): collectors → signals →
  cluster → `recommend` (policy-gated: confidence vs class threshold) → `verify`
  → `heal`/healers. A real propose→verify→apply loop (today aimed at platform
  healing).
- **Skills system** (`core/agents/skills.py`): `Skill` = tools-tuple +
  system-prompt prelude; `skill_registry`; Workers opt in at spawn;
  `contribute_skills()`. (Specialization = skills, enforced; no agent subclasses.)
- **155 `@tool`s / 39 files**, each scoped + `requires_approval`/hard-gate
  (`core/agents/tools.py`).
- **Provider-agnostic LLM** (`core/agents/llm.py`, `LLMProvider(ABC)` + circuit breaker).
- **MCP** (`agent_mcp` plugin: servers/scopes/auth) + **GraphQL** surface + **self-update**
  with backup/migrate/healthcheck/**rollback** (`core/updates.py`).
- **Worker/delegate spawn** (parallel sub-agents), **memory** (`LindaMemory`),
  **filesystem/system tools**, **safety boundary** (`core/safety.py`), `core.audit`.

## 3. Gap map (Hermes mechanism → Linda today → action)
| Hermes power | Linda today | Action (this plan) |
|---|---|---|
| Auto-create skills from completed tasks | Skills are plugin-authored, static | **Skill distillation**: turn a successful Worker trajectory into a persisted, runtime-registered `Skill` |
| Skills self-improve during use | Static skills | **Skill feedback loop**: track per-skill outcomes; refine prompt/tool-set; version |
| Writes/executes its own code | filesystem write + self-update, but no first-class codegen loop | **Self-dev pipeline**: author tool/module → sandbox-run → verify → human-gate → register/commit |
| Python-script tool composition (RPC) | one-tool-at-a-time calls | **`run_python` sandboxed tool** that calls the tool registry programmatically |
| Deepening user model + session recall | `LindaMemory` (flat) | **Merchant model + FTS session recall**: structured, evolving profile + searchable summaries |
| agentskills.io interop | bespoke `Skill` | **Adopt/import** the open skill format (portability) |
| Hermes 3/4 brain | provider-agnostic | **Add Hermes provider** (OpenRouter `nousresearch/hermes-*`) |

## 4. Architecture & placement (ADR-aligned)
- The self-learning/self-building loop EXTENDS the **core** self-improvement engine
  + `core/agents` + `core/safety` (per CLAUDE.md these are core, not pluggable —
  they're the platform's immune system).
- Sandboxed code execution reuses the **`functions` plugin** (already sandboxes
  merchant cart/pricing/shipping functions) or a dedicated core sandbox; container
  isolation optional later (Docker/Modal, mirroring Hermes).
- Persisted skills/merchant-model are new **core models** (small), surfaced on
  Linda's existing dashboard pages (Activity / Automations / Insights).
- Still ONE agent: every new power is a **tool + a loop**, never a new agent class.

## 5. The spine: propose → sandbox → verify → gate → apply → audit → rollback
Every self-modification (new skill, new tool, new module, code commit) flows
through the SAME pipeline (this is what makes a self-writing agent safe, and it
already exists for healing):
1. **Propose** — Linda drafts the artifact (skill/tool/module/patch).
2. **Sandbox** — run it in isolation (functions sandbox / container); never in the
   live process first.
3. **Verify** — `core/self_improvement/verify.py` + tests + the **security-reviewer**
   (hallucinated imports, injection, missing authz) + `core/safety.py` boundary
   (is the touched path allowed?).
4. **Gate** — `core.safety` policy decides: auto-apply (low-risk, e.g. a new
   read-only skill) vs **hard-gate** (human confirm + ack + echo) for anything
   that writes code, touches money, or commits to main.
5. **Apply** — register the skill/tool at runtime, or commit the module.
6. **Audit** — `core.audit` logs the change; **rollback** path (git ff /
   skill-disable) always available.

## 6. Phases
**Phase 0 — Hermes brain (quick win).** Add a Hermes 3/4 provider via OpenRouter;
make it selectable per scope. Validates provider-agnosticism. *(hours)*

**Phase 1 — Self-authored skills.** A `learned_skill.distill` tool: after a
successful Worker run, Linda summarizes the trajectory into a `LearnedSkill`
(name, prompt prelude, tool-set, examples), persisted to a core model + registered
in `skill_registry` at runtime. Read-only skills auto-apply; tool-bearing skills
hard-gated. *(Closes gap 1.)*

**Phase 2 — `run_python` sandboxed tool-composition.** A tool that executes
Linda-written Python in the sandbox with an RPC bridge to the tool registry (scope
-checked per call) — so Linda composes multi-tool pipelines in code, not turn-by-turn.
This is also the substrate for self-written modules. *(Closes gap 4; the user's
"connect via code".)*

**Phase 3 — Skill improvement loop.** Record per-skill outcome signals
(success/failure/latency) via the self-improvement collectors; `recommend` refines
the skill's prompt/tool-set; versioned; A/B via the `experiments` plugin. *(Closes gap 2.)*

**Phase 4 — Self-development (writes its own modules).** Extend the heal pipeline
so Linda can author a NEW tool/module/plugin (not just patch): generate →
sandbox-test → security-review → **hard-gate** → write file → run tests → (gated)
commit on a branch → PR. Bounded by `core/safety.py` (allowed paths only) +
`MORPHEUS_SELF_UPDATE_ENABLED`. *(Closes gap 3; the user's "writes its own modules".)*

**Phase 5 — Deepening merchant model + session recall.** A structured, evolving
`MerchantModel` (preferences, goals, history) + full-text searchable session
summaries for cross-session recall (mirrors Hermes SOUL/USER + FTS). Feeds Linda's
system prompt. *(Closes gap 5.)*

**Phase 6 — Open skill interop.** Map `Skill`/`LearnedSkill` to/from the
agentskills.io format; import community skills (sandboxed + reviewed before enable). *(Gap 6.)*

## 7. Safety / governance (non-negotiable)
A self-writing agent on a live store is powerful AND dangerous. Hard rules:
- Nothing self-generated runs in the live process before sandbox + verify.
- `core/safety.py` is the single boundary for what Linda may touch; self-dev cannot
  widen it.
- Code commits / money / migrations / main-branch = **hard-gate** (human ack+echo),
  never auto.
- Every self-change is audited + rollback-able; self-update already backs up + rolls
  back on healthcheck fail.
- The security-reviewer runs on every generated diff before any commit.
- Kill switch: `MORPHEUS_SELF_UPDATE_ENABLED` + per-class policy thresholds gate the
  whole loop.

## 8. Success criteria
- Linda turns a completed multi-step task into a reusable skill that a later run
  uses without re-deriving it.
- Linda composes ≥3 tools in a single sandboxed `run_python` call.
- Linda authors a new read-only tool end-to-end (sandbox→verify→gate→register) with
  zero core edits by a human.
- A self-authored change that fails verify/security-review is blocked + logged.
- Swapping to the Hermes model is a config change.

## 9. "Maximum powers" summary
Self-learning (skills from experience + improvement + deepening memory) +
self-building (writes/sandboxes/ships its own tools & modules) + connect-everywhere
(MCP + code via `run_python` + GraphQL) — all through ONE agent, one tool/scope/
audit interface, behind the propose→sandbox→verify→gate→apply→rollback spine.

## Status
- **Phases 0–3 shipped + prod-verified** (Hermes provider; self-authored skills;
  run_python sandbox; skill self-improvement/auto-prune).
- **Phase 4 — v1 shipped (DRAFT-only).** Linda can draft a new tool's source; it's
  statically safety-scanned (`codegen.scan_source`: dangerous calls, hallucinated
  imports, SQL-fstring, shape) and stored as a `CodeProposal` (status=draft). It is
  NEVER executed and NEVER written to the repo. Tools: `code.draft_tool`,
  `code.list_proposals`.
- **Phase 5 — multi-model consensus shipped.** `core/assistant/consensus.py` +
  `code.evaluate_proposal`: a proposal is reviewed by several CONFIGURED providers
  independently (a model rubber-stamps its own output), 2/3 quorum, degrade-safe
  (<2 providers → `insufficient`, defer to human). Advisory — never auto-approves.
- **Self-dev tools are Linda-only** via a `selfdev` scope the generic Worker lacks.

### Remaining (the autonomous loop's tail — gating policy SIGNED OFF 2026-06-08)
> Policy ratified in **ADR 0014** (`.torsor/architecture/decisions/0014-…`). The
> owner set the four axes: **apply target = full-auto-after-staging**, **blast
> radius = any plugin file** (never core), **approver = owner-only**, **posture =
> dormant** (build OFF behind `MORPHEUS_SELF_UPDATE_ENABLED`). All non-negotiables
> (kill switch default-OFF, hard-blocked paths, mandatory scan+security-review+
> consensus+sandbox, Linda-never-self-approves, audit+rollback, circuit breaker,
> `selfdev`-only) are locked. Build may now proceed; turning the switch ON is a
> separate deliberate owner action.
- **Phase 4 apply step — write+gate half SHIPPED (dormant).** `core/assistant/apply.py`:
  `apply_enabled()` (kill switch, default OFF) → `preflight()` (re-scan + consensus +
  path boundary via `core/safety.py` + circuit breaker) → `apply_proposal()` writes the
  source to a NEW `selfdev/*` branch via git PLUMBING (hash-object + temp index +
  commit-tree + branch) — never main, never the live working tree. Owner approval is
  `CodeProposal.approve(superuser)` via the `selfdev_approve` mgmt command; the
  `code.apply_proposal` tool adds an ack+echo hard-gate. Applied code lands in the new
  `linda_generated` plugin (disable-testable; `core/` is hard-blocked). Tests:
  `core/assistant/tests/test_apply.py` (dormant default, every gate, happy path on a
  throwaway repo). See `docs/plans/linda-selfdev-phase4-apply-2026-06.md`.
  STILL OFF until ops sets `MORPHEUS_SELF_UPDATE_ENABLED`.
- **Phase 4/7 promote (NOT built):** staging clone + auto-promote to prod via the
  `environments` plugin — the "go public" half. Wiring the applied tool into Linda's
  catalog at runtime also lands here.
- **Phase 6 — objective shape/schema self-eval SHIPPED (static, no execution).**
  `codegen._shape_findings`: a drafted tool is checked for a valid schema, a
  signature that matches the schema (params ↔ properties), and a ToolResult return —
  folded into `scan_source`, so every draft is objectively self-evaluated. NOTE:
  *functional* execution-with-inputs is deliberately NOT in-process (running a drafted
  module means importing/executing it) — that moves to P7's isolated env.
- **Phase 7 — staging→promote:** wire the `environments` plugin (Environment/Snapshot/
  Deployment — already exists, was unsurfaced) so Linda deploys a change to a STAGING
  clone, evaluates it there, then promotes to prod ("go public") behind the hard-gate.
  This is the "test itself, then go public" loop, incrementally + measured.
