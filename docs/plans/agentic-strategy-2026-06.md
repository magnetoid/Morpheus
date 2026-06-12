# Agentic commerce strategy — positioning + 90-day sequence (2026-06)

**Status:** direction-setting. Sits between `CHARTER.md` / `ENTERPRISE_ROADMAP.md`
(ambition) and `docs/plans/morph-backlog-2026-06.md` (execution). Where this
conflicts with CHARTER.md, CHARTER.md wins.

**Origin:** distilled from the 2026-06-10 working session that shipped PRs
#56–#61 (payments-webhook fix, CI repair, modular-OS debt repayment) — the
findings below are informed by what that session surfaced.

---

## 1. The positioning call

Don't fight Shopify on ecosystem breadth, Saleor/Medusa on headless APIs, or
Woo on cheap-plus-WordPress. None of them is **agent-native**; Shopify's
Sidekick is a copilot bolted onto a human-operated platform. Morpheus's
differentiator is already in the architecture:

- hooks bus + per-plugin `contribute_agent_tools()`
- approval workflow (`AgentApprovalRequest`) + scoped MCP tokens
- UCP manifest + MCP JSON-RPC server + trusted-agent attribution
  (see `docs/plans/architecture-2026-audit.md` §1 — this plumbing exists)
- the self-improvement loop + safety boundary (`core/safety.py`)

**The product is not a store with AI features — it is a workforce of
accountable agents that happens to ship with a store.** Everything that
enforces accountability (hooks, scopes, approvals, audit, tests, the
disable contract) is product, not plumbing. Commerce features are table
stakes, added lazily.

## 2. What "agentic" must mean to win

1. **The store runs itself, measured in dollars.** Agents own outcomes —
   pricing, reordering, cart rescue, SEO, fraud triage — with budgets and
   approval gates, and a dashboard showing *attributable revenue lift per
   agent*, not chat transcripts. Nobody buys a chatbot; they buy "my store
   made 12% more while I slept."
2. **Best seller-side counterparty for buyer agents.** The 2026 wave is
   agent-to-agent commerce (UCP, Agentic Commerce Protocol, AP2-style
   payments): shopping assistants that discover, compare, and check out
   programmatically. Extend the existing MCP/UCP surface into a public,
   scoped buyer-agent surface: machine-readable feeds, signed quotes,
   tokenized agentic checkout. Greenfield no incumbent owns.
3. **Trust as a feature.** The 2026-06-10 session is the cautionary tale:
   six production bugs (a payment-webhook crash among them) lived
   undetected because CI was red and fail-soft blocks swallowed errors.
   An autonomous platform needs a *higher* reliability bar than a
   human-operated one — exactly-once money semantics, a complete audit
   trail, and **undo for agent actions** (a trust feature competitors
   can't retrofit).

## 3. Beachhead

Books / digital goods — the vertical already built out (book_product,
bookvault, audiobooks, flipbook, digital_products; dotbooks.store as the
live proof). Win "the agentic digital-goods store" first; generalize after.
Open-source core + hosted offering is the Medusa/Saleor playbook; the
self-improvement loop is what makes *hosted* defensible.

## 4. The 90-day sequence

1. ✅ **CI green and gating** (PRs #56–#57, hardened further by the
   `manage.py check` gate). Keep it that way — red CI is how autonomous
   bugs reach production unnoticed.
2. **Harden the money path.** Contract tests against real Stripe test
   mode (mocks pass while phantom methods fail — CLAUDE.md rule);
   idempotent checkout end-to-end; tests for the plugins that ship none
   (payments-adjacent first).
3. **Finish `contribute_agent_tools()`.** Migrate `core/assistant/tools/*`
   into the owning plugins (the wrong-direction-imports item in
   CLAUDE.md). Strategically this is not cleanup: when every capability
   is a plugin-contributed, scoped tool, the agent's capability surface
   grows automatically with the ecosystem — that is how you out-scale
   Sidekick. Spec first.
4. **Ship the buyer-agent surface** as the headline feature: public MCP
   endpoint + product feed + agentic checkout (tokenized cart, signed
   quotes). Track UCP / ACP / AP2 developments before freezing formats.
5. **Outcome dashboards.** Agent runs → attributable revenue lift; the
   approval queue as a first-class UX. This is the demo that sells.
6. **Test floor.** Permission-boundary tests per staff view (skill
   exists); suites for the remaining bare plugins.

## 5. Non-negotiables this strategy inherits

- The plugin contract + disable litmus tests (CLAUDE.md) — agents can only
  safely install/modify/generate plugins because the contract is enforced.
- Docs ship with code; this document is updated when the sequence shifts.
- A failing money-path test blocks everything else. Reliability is the
  moat; see §2.3.
