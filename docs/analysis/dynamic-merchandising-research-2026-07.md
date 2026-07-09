# AI-Driven Dynamic Product Merchandising — State of the Art 2025–26

> Research artifact behind [`docs/plans/dynamics-merchandising-2026-07.md`](../plans/dynamics-merchandising-2026-07.md).
> Method: ~250 web searches/fetches across three research agents (vendor landscape +
> algorithms-in-production + measurement). Claims carry source URLs; unverifiable
> vendor claims are flagged.

## The through-line

Every vendor that wins in 2025-26: **AI ranks by default, merchants override
surgically (pin > boost > rule), and the system can always explain itself.**
For a 100–10k SKU store, sophistication should go into the *control surface
and measurement*, not model complexity.

## 1. Vendor landscape (what their dashboards let merchants do)

- **Nosto** — per-placement weighting rules over attributes + performance
  metrics (CVR, margin, inventory turnover); category merchandising with
  drag-pins that survive re-ranking; segment targeting + preview-as-segment;
  scheduled campaigns. 2025: **Huginn** agentic layer — agents *propose*
  merchandising actions under merchant supervision.
  (nosto.com/commerce-experience-platform/…, help.nosto.com)
- **Dynamic Yield (Mastercard)** — per-widget multi-strategy slot splits;
  three rule types include/exclude/**pin** (pin overrides everything);
  AdaptML/AffinityML per-user ranking; Dynamic Allocation (bandit) with a
  recommended 10% hidden control. (dynamicyield.com/lesson/merchandising-rules/)
- **Algolia Merchandising Studio** — no-code Visual Editor over the live grid:
  multi-item drag pinning, hide, boost/bury, facet ordering; rule tags,
  dynamic ruleContexts (traffic source/season); "Layers of Ranking"
  per-user ranking visualizer. Precedence rule worth copying: **re-ranking
  never overrides a pinned product.** (algolia.com changelog + docs)
- **Constructor** — rules become features fed into the ML model, not hard
  overrides; 2026 **Merchant Intelligence Agent (MIA)**: conversational
  "why isn't X ranking for Y" + goal-directed proposed rule changes,
  human-approved. (constructor.com/blog/introducing-merchant-intelligence-agent)
- **Rebuy (Shopify)** — per-widget Data Sources: "Rebuy AI" default or rule
  compositions (product/cart/customer/URL/date/geo rules) + AI sources
  (Top Sellers, Trending, Buy It Again). (rebuyengine.com/data-sources)
- **Klevu/Athos** — drag/pin over the grid *while ML keeps ranking everything
  unpinned*; boosts ±1…±999; automated rules on margin/inventory/seasonality;
  scheduled campaigns; per-category A/B. (support.klevu.com)
- **Bloomreach Discovery** — Product Grid Editor (lock-in-place vs lock
  position #, conflict detection); **Ranking Diagnostics**: per-product
  signal-score breakdown answering "why does this rank here" (also on API).
  2026: One-to-One in-session reranking +2.2% RPV. (documentation.bloomreach.com)
- **Shopify Winter '26** — Sidekick proactive merchandising suggestions;
  **Agentic Storefronts** syndicating products into ChatGPT/Perplexity/Copilot;
  published a production generative recommender. (shopify.com/news/winter-26-edition-renaissance)

## 2. Algorithms actually in production (deep-dive bottom line)

At 100–10k SKUs the evidence overwhelmingly supports:

- **Transparent scoring pipeline**: popularity (smoothed CTR/conversion) ×
  recency decay × margin/stock business weights + session-category /
  co-occurrence personalization + content/attribute prior for cold items.
  Google Rules of ML #1 ("start without ML"); Spotify: "if ML gives you 100%,
  a heuristic gets you 50%". (eugeneyan.com/writing/first-rule-of-ml/)
- **Bandits over strategies/slots, not per-SKU**: the proven pattern (Yahoo
  LinUCB +12.5% CTR — advantage GROWS when data is scarce; Amazon promotions
  box Thompson sampling; Spotify home ε-greedy; Walmart batch-updated TS;
  Expedia module ordering). (arxiv.org/abs/1003.0146 et al.)
- **Exploration floor ε≈0.05–0.20, ~0.1 at cold start, never 0** (Azure
  Personalizer guidance; Netflix 2025 formalizes minimum exploration).
  **Etsy gives every new listing a temporary search boost** — the
  guaranteed-first-impressions pattern. (etsy.com/seller-handbook)
- **Diversity via re-ranking**: MMR/category caps are the shipped version;
  YouTube's DPP re-ranker produced substantial engagement gains.
- **Session heuristics beat transformers at small data**: session-kNN beats
  GRU4Rec in most configurations (Ludewig & Jannach UMUAI 2021); RecSys 2019
  best paper: 6/7 reproducible neural recommenders beaten by simple
  heuristics. GBDT-LTR (LightGBM lambdarank) is the first "real ML" upgrade
  once interactions cross ~10k / <99% sparsity — transformers far beyond that.
- **CF sufficiency rule of thumb**: 1,000×1,000 needs >10k quality
  interactions before CF personalization is meaningful. (shaped.ai)
- **Booking.com's 150-models lesson**: model-metric gains ≠ business gains;
  +30% latency cost ~0.5% conversion — favor precomputed simple models.

## 3. Merchant-control UX trends

- Strategy-per-slot pickers are table stakes; 2025 refinement = *composition*
  (slots within one widget mix strategies).
- **Visual drag merchandising with AI underneath** is the defining
  interaction; pin semantics beat boost semantics for merchant trust.
- **Explainability panels are the 2025-26 wave** (Bloomreach diagnostics,
  Algolia layers-of-ranking, Constructor MIA) — the feature that builds trust
  in "AI decides".
- Campaign scheduling + preview-as(segment/date) everywhere.
- **Natural-language merchandising is shipped, not vapor**: Salesforce
  Agentforce merchandising actions ("boost new arrivals" = 1 prompt vs 15
  clicks); Nosto×Sidekick; Constructor MIA. What actually ships is
  *propose-then-approve*; fully autonomous merchandising is still marketing.

## 4. Measurement (deep-dive bottom line)

- Merchandising vendors are statistically weak: Algolia = fixed-horizon
  z-tests; Constructor's "Proof Schedule" has no disclosed methodology or
  control; DY/Nosto use Bayesian P2BB + bandit allocation. **None ship
  sequential/always-valid stats, interleaving, or OPE.**
- The open-source play (all MIT prior art exists): GrowthBook-style
  **asymptotic confidence sequences + CUPED**; **RPV winsorized at p99**
  (needs 2–5× the sample of binary metrics — test add-to-cart when traffic
  is thin); **team-draft interleaving** for ranker-vs-ranker (Netflix: ~100×
  fewer users; Airbnb: A/B conclusions at 4% of traffic; Etsy ≤10%) — no
  vendor ships it; **5–10% persistent program-level holdout** (DY's
  Personalization Impact Report is the one first-class example);
  **margin/returns/latency as first-class guardrails** — documented unfilled
  niche.
- Pitfalls: novelty effects (run 3-4 weeks, segment new vs returning);
  cannibalization across placements (Etsy: better recs depressed organic
  search clicks — per-placement metrics overstate site-level lift).

## 5. Emerging

- **Agentic commerce is a merchant-side feed problem**: ACP (OpenAI/Stripe) added
  Feed+MCP; Google AP2; Shopify UCP + Catalog ("list once, syndicate to every
  AI"), AI-driven orders ~13× YoY. Protocols churn (Instant Checkout sunset
  once) — bet on the stable layer: schema.org markup, structured feed,
  llms.txt, MCP storefront (Morpheus already has agent_mcp).
- LLMs *around* the ranker, not in the serve path (Instacart query
  understanding, DoorDash/Zalando LLM-as-judge eval). LLM rerank = seconds +
  5-15× cross-encoder cost.
- Real-time context: weather targeting shipped by Nosto/DY/Bloomreach with
  credible lifts (Burton +11.6% conversions).
- Zero-party quiz data (Octane AI pattern) = strongest cold-start signal a
  small store can get (Morpheus has discovery_quiz).

## The 10 build-able features (ranked for a small-to-mid catalog store)

1. Strategy-per-slot picker with a composable score formula (weighted blends
   over the existing scorecard).
2. Visual grid merchandiser: pin-to-position + boost/bury over live AI
   ranking; pins survive re-ranking; personalization never overrides a pin.
3. Rule builder with context conditions (segment/UTM/device/geo/weather/date)
   + scheduling + priority + conflict detection; pin-beats-exclude semantics.
4. In-session personalization from session analytics (category/brand/price-band
   affinity re-weighting every slot) — the personalization mode that works at
   small traffic.
5. **"Why is this product here?"** explainability panel: per-product score
   breakdown + preview-as (segment/visitor/date).
6. Interleaving for ranker comparison + sequential stats + 5-10% holdout in
   the experiments engine.
7. Exploration floor + cold-start boost in every strategy (ε≈0.1, decaying
   new-product boost) — prevents the scorecard permanently entombing new
   products.
8. Natural-language merchandising via the existing agent → compiles to
   inspectable, versioned Rule objects, merchant approves.
9. Agent-readable storefront package (ACP-shaped feed, schema.org, llms.txt,
   MCP shopping tools).
10. Diversity + guardrail constraints in the ranking layer (category caps,
    margin floor per slot, OOS auto-bury) surfaced as toggles.
