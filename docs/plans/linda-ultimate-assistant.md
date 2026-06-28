# One Linda — the ultimate ecommerce + personal assistant

## Context

Linda is Morpheus's AI assistant. Today she is **staff-only** (admin dashboard:
floating widget + `/dashboard/assistant/`, all `@staff_member_required`). There is
**no shopper-facing assistant** on the storefront. The goal (user direction) is to
make Linda a single assistant that serves **both** staff and shoppers, is genuinely
**self-learning and self-correcting**, and is a powerful ecommerce + personal
assistant. Decisions locked with the user: audience = **both**; **engine
self-learning/self-correction first**; **one "Linda"** extended across surfaces
(scopes + persona-per-surface decide capability).

The engine is already strong (tool registry, generic Worker + parallel delegation,
multi-provider with circuit-breaker/fallback/semantic-cache, MCP/ACP surfaces). The
self-learning *scaffolding* exists but several loops aren't closed. This plan closes
them first, then builds the shopper surface on the hardened core.

**Constraints:** push-to-main auto-deploys to prod → small, independently-shippable,
test-guarded increments. Core must not import `plugins.installed.*`
(`scripts/check_core_boundary.py` enforces). Customer = AbstractUser. Tests:
`DATABASE_URL='sqlite:///:memory:' python manage.py test <path>`.

**No new dependencies needed** (verified): `core/embeddings.py` (`embed()` +
`cosine_similarity()`, OpenAI w/ deterministic hash fallback) serves semantic
memory; `core/self_improvement` `emit_signal` + `SIGNAL_SOURCES` is the feedback
bus; `core/assistant/consensus.py` extends to answers.

## Key file anchors
- Runtime: `core/assistant/runtime.py` (Assistant.stream loop, `_dispatch_tool`).
- Memory: `core/assistant/tools/memory.py`, `LindaMemory` `core/assistant/models.py:78`.
- Skills: `core/assistant/tools/skills.py`, `LearnedSkill` `core/assistant/models.py:147`.
- Signals: `core/self_improvement/services.py` (`emit_signal`), `models.py` (`SIGNAL_SOURCES`).
- Consensus: `core/assistant/consensus.py`. Persona/prompt: `core/assistant/prompts.py`.
- Surfaces: `core/assistant/views.py`, `modes.py`; storefront theme `themes/library/dot_books/templates/storefront/base.html`.

---

## PHASE 1 — Engine self-learning + self-correction (FIRST; 5 shippable increments)

Order: 1a → 1b → 1d → 1c → 1e (1d before 1c — re-distill wants the signal plumbing).

**1a — Semantic memory retrieval (keyword fallback preserved).** Add
`embedding = JSONField(default=list)` to `LindaMemory` (+ additive migration).
`memory.remember` computes `embed(f'{key}: {value}')` on write; `memory.recall`
ranks by `keyword_score + cosine_similarity(embed(query), row.embedding)` over a
bounded candidate set, with a relevance floor so it never floods junk; falls back to
substring when no embeddings. One-off `backfill_memory_embeddings` management
command. Reuse `core.embeddings` (core→core, boundary-safe). Tests use the hash
fallback + a patched `embed` to prove the semantic path deterministically.

**1b — JSON-repair + replan on tool errors.** In `runtime._dispatch_tool`, on an
*argument* error (TypeError/schema), do ONE bounded LLM re-ask ("your args were
invalid: {err}; schema is {schema}; reply corrected JSON only") then retry; keep the
existing error-feedback append as fallback. In `stream`, track
`consecutive_tool_errors`; at 2, inject a replan nudge. Do NOT repair `ToolError`
(intentional validation messages).

**1d — Linda failure → SiSignal + outcome score.** Register new `SIGNAL_SOURCES`
(`agent_failure`, `agent_dissent`, `agent_skill_health`). On failed run / repeated
tool errors, `emit_signal(source='agent_failure', …)` (core→core). Add a feedback
view (`core/assistant/views.py` + url) + thumbs-down control → `agent_dissent`. New
`LindaOutcome` model (per-turn score from tool-errors/dissent/max_steps). Capture
only — no auto-apply healer; `MORPHEUS_SELF_UPDATE_ENABLED` stays dormant. Three
permission-boundary tests on the feedback view.

**1c — Skill self-improvement (re-distill, not just retire).** In
`skills.record_skill_outcome`, when success_rate first crosses the prune threshold,
an LLM pass rewrites the skill's `system_prompt_prelude` (bump `version`, keep
enabled, `improve_count++`); only retire if it still fails a second window. Add
`improve_count`/`improved_at` to `LearnedSkill` (migration). Emit `agent_skill_health`.

**1e — Consensus/self-check on high-stakes answers (optional, ship last).** Extend
`consensus.py` with `review_answer(question, draft)` reusing `configured_providers()`
+ `aggregate()`; runtime runs it only behind a narrow high-stakes heuristic + a
default-off setting. Degrades safely with <2 providers.

---

## PHASE 2 — One Linda, shopper storefront surface (outline)
Same `Assistant` runtime, customer-session-gated storefront chat (anon + logged-in),
read-only: product discovery, recommendations, store/policy Q&A. `build_system_prompt(surface='staff'|'shopper')`
+ `LINDA_SHOPPER_PROMPT` (core, no plugin import). New `shopper` mode in `modes.py`
with a strict read-only scope allowlist (NO orders/customers/system/db/fs). Expose
`personalisation.related_to()` as an agent tool **from the plugin side** (by name,
boundary-safe). New `shopper_stream` view (session-gated, rate-limited, NOT staff).
Mount the widget via the theme's `footer_extra` storefront block, not a base.html
edit. **Critical risk: scope leakage** — a test must assert the shopper mode exposes
zero staff-scoped tools.

## PHASE 3 — Shopper personal / ecommerce power (outline)
Per-customer memory: `customer = FK(AUTH_USER_MODEL, null=True)` on `LindaMemory` +
`customer` scope, recall scoped by `request.user`. Self-service tools over the
shopper's **own data only** (order status, returns, loyalty) — customer identity is
bound from the session into `context`, **never** a tool argument (IDOR guard); each
tool re-derives `request.user`. Add-to-cart is the only shopper write. Three
permission-boundary tests per tool (other-customer invisible, anon blocked, own
visible).

## PHASE 4 — Deepen (outline)
Multi-turn Workers; explicit token budgeting/context rollup (compaction hook exists
`core/agents/compaction.py`); consensus default-on for irreversible shopper actions;
evaluation harness/A-B on the `LindaOutcome` rows (reuse `ai_assistant` `PromptVariant`
+ the langfuse skill).

---

## Cross-cutting
Every increment additive (nullable columns, new tools/sources) → safe for
push-to-main. No new `core→plugins.installed` import (memory/embeddings/signals are
core→core; persona/scopes in core; plugin tools register from the plugin side by
name) — `python scripts/check_core_boundary.py` green each PR. Every new view ships
the three mandatory permission-boundary tests.

## Verification
Per increment: targeted tests (`DATABASE_URL='sqlite:///:memory:' python manage.py
test core.assistant…`), `ruff check`, `manage.py check`, `makemigrations --check`,
`scripts/check_core_boundary.py`. Migrations clear the real-Postgres CI gate. Smoke
the live assistant after any runtime/surface change.
