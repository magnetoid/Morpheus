# AI × Commerce strategy — 2026–2031

**Status:** direction-setting, living document. Revisit quarterly (the forecasts
and the protocol landscape move fast). Sits *above* the 90-day
[`agentic-strategy-2026-06.md`](agentic-strategy-2026-06.md) (which it supersedes
as the long-horizon frame) and *below* `CHARTER.md` (ambition). Where this
conflicts with CHARTER.md, CHARTER.md wins.

**Origin:** three research sweeps on 2026-07-21 — a trends/forecast scan, a
competitive-landscape scan, and a read-only inventory of Morpheus's own AI
surface. This doc is the synthesis; the Horizon-1 execution plan it points to is
where the code gets written.

---

## 1. Thesis

Morpheus is the **self-hosted counterparty to the agentic web**: maximally
legible and transactable to every AI shopping surface, while the merchant is
never intermediated — they keep the customer relationship, the checkout, the
data, and the margin. The agent runtime and its safety harness (approvals,
staging, audit, scoped tokens, the self-improvement loop) are **the product**;
commerce breadth is table stakes.

This is the same call the 90-day doc made ("a workforce of accountable agents
that happens to ship with a store"). What the 2026 research *adds* is the
external validation and the timing: the industry ran the "AI owns checkout"
experiment and it failed; the durable pattern is **discover in AI, buy on
site** — which is exactly the architecture Morpheus already has. The strategic
job for five years is to be the store the agents can find, read, trust, and
transact against, without giving up sovereignty.

**The one-sentence position:** *your AI, your data, your audit trail, your
checkout* — the counter-position to every SaaS platform that intermediates the
agent surface and meters the merchant for it.

---

## 2. What the research established (load-bearing facts)

- **"Discover in AI, buy on site" won.** OpenAI retired in-chat Instant Checkout
  in March 2026 (~30 merchants live, converting ~3× *worse* than the merchant's
  own site, 4% fee on top of platform fees, no multi-item carts, unresolved
  sales tax) and pivoted to *merchant-controlled* checkout — merchants run their
  own experience inside the assistant and keep checkout. (Digital Commerce 360,
  Mar 2026; Forbes/Goldberg, Mar 2026.)
- **AI-referred traffic is real, high-intent, and growing.** Adobe: holiday-2025
  AI-referred retail traffic **+693% YoY**, converting **+31%** vs other
  channels, revenue-per-visit **+254%**, bounce −33%; it **doubled again YoY by
  June 2026**. But most retail sites are not machine-readable enough to be cited.
- **UCP is the presumptive lingua franca.** Google + Shopify, launched Jan 2026,
  REST + MCP bindings, merchant stays Merchant-of-Record; Tech Council includes
  Amazon, Meta, Microsoft, Salesforce, Stripe. ACP (OpenAI+Stripe, Apache-2.0)
  survives as the checkout-execution layer. **Structured syndication beats
  scraping** — Shopify's Catalog feed converts at ~2× scraped data.
- **Payments converge on cryptographic scoped mandates.** AP2 (60+ partners,
  FIDO-governed), Visa Trusted Agent Protocol, Mastercard Agent Pay / AP4M — all
  bind *cardholder + registered agent + spend/scope constraint* into one
  credential. The mandate trail doubles as the liability record. x402
  (machine/API micropayments, Linux Foundation Apr 2026) is **not** retail-
  relevant yet (~$50M cumulative, ~$0.30 avg txn).
- **Web Bot Auth is standardizing.** IETF BCP (RFC 9421 HTTP Message Signatures +
  Ed25519 + `Signature-Agent` + JWKS registries) targeted ~**Aug 2026**. Backed
  by Cloudflare, Amazon, Akamai, OpenAI.
- **EU AI Act Art. 50** (chatbot disclosure, AI-content labeling) is legally
  effective **Aug 2, 2026**. High-risk (Annex III) obligations likely slip to
  Dec 2, 2027 via the Digital Omnibus — *not yet formally adopted*, so Aug 2026
  stands today. Fines to €35M / 7% turnover.
- **Forecast band:** 10–25% of online retail agent-orchestrated by 2030–31
  (McKinsey up to $1T US / $3–5T global; Bain 15–25%; Morgan Stanley 10–20%).
  Gartner: **$15T B2B agent-intermediated by 2028** (90% of B2B buying); machine
  customers influence $30T of purchases by 2030. **B2B moves faster and bigger
  than B2C.**
- **Adoption reality-check.** SMB willingness-to-pay for AI clusters at
  $25–100/mo and concentrates on tools *embedded in software they already use*
  (price accordingly — AI inside the dashboard, not a separate SKU). Consumers
  are split on trusting agents; **staged/confirmable** agent actions (Sidekick's
  model, and Morpheus's) beat autonomous free-run; human escalation stays
  mandatory for support/sensitive issues.

---

## 3. Competitive map + whitespace

**Benchmark — Shopify.** Sidekick (staged writes, weekly-active up 4× YoY,
third-party app tool-use), **Catalog** (zero-setup syndication to
ChatGPT/Copilot/Gemini/Shop), **Storefront MCP** (GA early 2026, auto-enabled on
Plus), Universal Cart, UCP co-author. Their real moat is **distribution** —
enrolling millions of merchants into every AI surface by default — and the 2×-
converting first-party feed pipe. We cannot match scale; we must win on depth and
sovereignty.

**Enterprise — Salesforce Agentforce Commerce, Adobe CX Coworker.** Native
ChatGPT/Gemini integration, multi-agent branding. Irrelevant as a direct
competitor to a self-hosted SMB platform; relevant as a signal of where
agent-channel integration budgets flow.

**Open-source neighbors.** WooCommerce (MCP proxy, "OS of the agentic web"
manifesto — but AI bolted on via plugins, no native runtime), Medusa ("commerce
for agents *and developers*" — agent tooling for *developers*, not a merchant-
facing runtime), Shopware (declared "open commerce infrastructure for the
agentic era", strongest EU open-source play). **No one open-source ships a
permissioned merchant-facing agent runtime with staged writes, approval gates,
tool scoping, and an audit boundary. Morpheus already does.**

**Ecosystem economics.** The in-chat checkout toll-booth failed its first test;
Perplexity's zero-fee, merchant-of-record model is the counter-pattern. Toll
extraction is migrating from checkout-fee to *discovery placement* — and 75% of
consumers say sponsored AI results would cost their trust, so even that is
fragile. For a direct-merchant platform this is **bullish**: the merchant's own
checkout stays the conversion surface.

**The four whitespace pillars to own:**
1. **Sovereignty + EU compliance as a product.** `core/safety.py` + approval/
   audit trail *is* the AI-Act evidence artifact. Productize it.
2. **Model choice incl. local.** Open-weight models at production-token parity;
   no incumbent lets a merchant point the platform's agent at their own
   Ollama/vLLM endpoint. Morpheus's 11-provider registry already does.
3. **Zero-config agent-readiness.** Emit schema.org, feeds, llms.txt, and
   conversational Q&A by default and syndicate — the single biggest gap vs
   Shopify for a self-hosted store.
4. **Data ownership of the AI exhaust.** The corpus of how customers ask and
   decide stays with the self-hosted merchant, not the platform.

---

## 4. Build-vs-skip register (binding until revisited)

**Build:**
- UCP endpoint + merchant-of-record agentic checkout, deepened over time (carts,
  promo, loyalty, post-purchase as the spec adds them).
- Agent-readiness / GEO surface (llms.txt, agents.md, dense schema, merchant-
  owned Q&A, AI-referral analytics).
- AI-Act compliance pack (Art. 50 disclosure, exportable audit/decision trail,
  content provenance).
- Bring-your-own-model everywhere, per-task routing (cheap model for enrichment,
  strong model for the operator).
- Continuous background agents as inference cost falls (enrichment, catalog QA,
  self-improvement) — a differentiator no metered SaaS can match.
- Merchant-facing guardrails (spend caps, price-change bounds, ROAS floors, kill
  switch) over the existing enforcement seams.
- B2B machine-customer endpoints (where the trillion-dollar numbers are).

**Skip (with reasons):**
- **In-chat checkout integrations as a priority bet** — the model just failed;
  implement only the *catalog-feed* side; revisit ACP native checkout in 2027.
- **A consumer-facing shopping agent of our own** — that war belongs to
  OpenAI/Google/Perplexity; be the best *counterparty* instead.
- **A specialist agent zoo** — one generic Worker + Skills + scopes is cheaper
  and matches the "harness > model" finding (also existing ADR 0011 policy).
- **AI site-gen as a headline feature** — commoditized by Wix/Squarespace; a
  storefront bootstrap flow is enough.
- **Sponsored / ad-influenced AI recommendations** — 75% trust-loss poisons the
  well.

---

## 5. Five-year timeline (table-stakes by when)

**2026 (now → H2):** schema-dense catalog + product feeds + llms.txt/agents.md;
MCP storefront endpoints that actually transact; a UCP and/or ACP checkout
endpoint; AI-referral analytics; Web Bot Auth verification (BCP ~Aug 2026); EU AI
Act Art. 50 disclosure + AI-content labeling; agentic support with human
escalation. **← Horizon 1, this plan.**

**2027:** UCP native checkout with multi-item carts + loyalty linking +
post-purchase; delegated-payment mandates (AP2 / Visa TAP / Agent Pay) accepted
via gateway plugins; agentic ad-ops with guardrails (spend caps, ROAS floors,
drift monitors, kill switch) as standard merchant tooling; a GEO measurement
stack (citation share across surfaces); EU high-risk compliance prep
(Dec 2027). B2B seller-side counteroffer agents begin (Forrester: 20% of B2B
sellers forced to respond).

**2028+:** B2B procurement majority agent-intermediated; agent-to-agent
negotiation; **machine customers as a named segment** with their own pure-API
storefront; programmable / x402-style payments scale beyond APIs; generative
per-shopper UI mainstream.

**2030–31:** 10–25% of online retail agent-orchestrated; $30T machine-customer
influence; the storefront-for-humans is one of several equal surfaces alongside
the agent surface.

---

## 6. Horizon roadmap (what Morpheus builds, per horizon)

**Horizon 1 — 2026 H2 (detailed execution: this plan's Deliverable 2).**
Art. 50 disclosure → agent-readiness pack → real MCP cart/checkout + Web Bot Auth
→ guardrails + compliance export → B2B quote slice. Closes the biggest promise-
vs-shipped gaps (empty MCP cart/checkout clusters, no llms.txt, no native agent
verification, no guardrail knobs) and hits the Aug 2026 compliance deadline.

**Horizon 2 — 2027.** UCP checkout depth (carts/loyalty/post-purchase tracking
the spec); delegated-payment mandate acceptance via `payments` gateway plugins;
**pgvector RAG** (the current Python-cosine retriever won't scale past hundreds
of chunks); **durable agent job queue** (replace thread-based fan-out so parallel
work survives restart); agentic ad-ops guardrails on the channel plugins
(PMax/Advantage+ tool-use with spend caps); **C2PA content provenance** in the
media plugin (near-zero adoption today = early-mover differentiation).

**Horizon 3 — 2028+.** B2B negotiation/counteroffer agents; the machine-customer
pure-API storefront as a first-class surface; x402 acceptance for the
`digital_products` plugin (selling API/content access to machines — cheap
optionality on an existing plugin); generative StorefrontBlocks where ROI is
proven (virtual try-on: +35% conversion / −15–35% returns; per-shopper blocks).

---

## 7. Ten strategic implications (the standing guidance)

1. **We bet correctly on UCP — go deep, not wide.** Track the spec's cadence;
   keep ACP a thin adapter, not a peer investment.
2. **Merchant-controlled checkout won** — our architecture is validated; the next
   surface is a packaged "merchant app inside the assistant" per store.
3. **Feed quality is the new SEO, and syndication beats scraping** — "agent-ready
   by default" is the single biggest gap vs Shopify.
4. **Verify agents at the door** — native Web Bot Auth before Aug 2026; self-
   hosting means the *merchant* controls admission policy.
5. **Payments: support scoped mandates, watch x402** — the mandate audit trail is
   the liability record; x402 fits `digital_products`, not retail checkout.
6. **The operator agent is parity; guardrails are the moat** — productize
   approvals/staging/safety as merchant-facing knobs.
7. **B2B is where the trillion-dollar numbers are** — grow machine-customer
   endpoints on the b2b plugin.
8. **Compliance is a feature for self-hosted** — Art. 50 disclosure, C2PA
   signing, agent-decision audit export; "your AI, your data, your audit trail."
9. **Spend generative-UI effort where ROI is proven** — try-on and per-shopper
   blocks; skip speculative whole-page-per-query until the data plumbing is done.
10. **The strategic risk is distribution, not features** — we can't match
    Shopify's scale, so win on zero-config agent-readiness, depth of agentic
    control, and the merchants who explicitly refuse to be intermediated.

---

## 8. Forecast table + sources

| Source (date) | Forecast |
|---|---|
| Gartner (Nov 2025) | $15T B2B agent-intermediated by 2028; 90% of B2B buying |
| Gartner (Oct 2025) | Machine customers influence $30T by 2030; 20% of transactions programmable by 2030 |
| McKinsey (Oct 2025) | Up to $1T US orchestrated retail by 2030 (18% of B2C); $3–5T global |
| Morgan Stanley | $190–385B US, 10–20% of online retail by 2030 |
| Bain | $300–500B, 15–25% of e-commerce by 2030 |
| Adobe (Jan/Jun 2026) | AI retail traffic +693% YoY holiday '25; +31% conversion; doubled again by Jun 2026 |

**Consensus band: 10–25% of online retail agent-orchestrated by 2030–31; B2B
larger and faster than B2C.**

Primary sources (dated): Stripe/OpenAI ACP (Sep 2025); Digital Commerce 360 OpenAI
checkout pivot (Mar 2026); Forbes/Goldberg checkout retreat (Mar 2026); Google UCP
+ Universal Cart (Jan/May 2026); PYMNTS UCP (2026); American Banker Visa/Mastercard
(2026); Mastercard AP4M (Jun 2026); Cloudflare/IETF Web Bot Auth registry (2026);
Adobe holiday + Jun-2026 AI-traffic (2026); Shopify Spring '26 Edition; Salesforce
Agentforce Commerce (Jul 2026); Adobe CX Coworker (Apr 2026); BigCommerce/Feedonomics
ACE (Apr 2026); Automattic agentic-web manifesto (Apr 2026); Shopware SCD 2026;
PayPal–Perplexity Instant Buy (Nov 2025); Forrester state-of-agentic-commerce
(mid-2026); Travers Smith / EU AI Act service desk on the Digital Omnibus timeline;
Darwinium agentic-commerce fraud report (2026); Epoch AI inference-cost trends;
Bluevine/Business.com SMB AI reports (2026).

---

## See also

- [`agentic-strategy-2026-06.md`](agentic-strategy-2026-06.md) — the 90-day
  positioning + sequence this doc supersedes as the long frame.
- [`architecture-debt-refactor-2026-07.md`](architecture-debt-refactor-2026-07.md)
  — the core-boundary refactor (ratchet → 0) that cleared the deck for this work.
- [COMPLIANCE.md](../COMPLIANCE.md) — EU AI Act + GDPR mapping (Art. 50 lands in Horizon 1).
- [AGENT_PROTOCOLS.md](../AGENT_PROTOCOLS.md) — MCP / UCP / Trusted Agent surface.
