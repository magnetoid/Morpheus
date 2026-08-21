# MCP + GraphQL surface hardening — 2026-08-21

Deep audit of the agent/API surfaces (three read-only analysis agents +
verification against the torsor ADRs). This file is the finding ledger:
what shipped in **v0.55.0** and what is deliberately deferred (with why).

Torsor rules that governed the work: ADR 0027 (MCP gate chain: scope →
approval → rate-limit → audit), ADR 0011/0029 (one generic agent; agent layer
is core), API_STABILITY (MCP tool **names** + `/api/graphql/` are STABLE —
additions only), scope vocabulary single-sourced in `agent_mcp/scopes.py`,
`core/pricing.apply_price_filter` on **both** the displayed and charged price.

---

## Shipped in v0.55.0

### Tool ownership (the live boot-log collisions)
- **`inventory.adjust_stock`** had an UNGATED twin in `agent_core` shadowing the
  inventory plugin's `requires_approval=True` original; last-writer-wins served
  the ungated one, so the MCP/Linda approval gate never fired on stock writes.
  Deleted the twin. `inventory.set_stock` (agent_core, sole owner) gained
  `requires_approval=True` for parity (an absolute write is the same blast
  radius as a delta).
- **`analytics.top_products`** had three owners; **`analytics.summary`** two.
  Orders owns both names (it aggregates Order/OrderItem). Deleted agent_core's
  weaker `top_products`; renamed the analytics plugin's rollup pair to
  `analytics.traffic_summary` / `analytics.top_viewed_products` (genuinely a
  different concept — traffic, not sales).
- `register_tool` is now **first-owner-wins** and RAISES under DEBUG/tests on a
  cross-plugin duplicate (was warn-and-overwrite). Collision baseline emptied.
  A deliberate test swap passes `replace=True`.

### MCP scope model (was fail-open in several places)
- **Token dashboard preserved scopes across saves.** `_load_entries` dropped
  `mcp_scopes`/`graphql_scopes`/`approved_tools`/`rate_limit`; because a missing
  `mcp_scopes` reads as wildcard, every create/revoke silently promoted every
  other token to full access and wiped approval grants. Now preserves the whole
  dict.
- **Deny-first bearer resolution.** `apply_bearer_user` stashes empty scope sets
  the moment a token is presented, before any fallible work — a half-completed
  resolution can no longer fall through to a wildcard default. A *no-token*
  request is left untouched so session-authenticated staff keep the is_staff
  fallback.
- **Malformed scope value → deny.** `token_scopes` returns `set()` for a
  present-but-garbage `mcp_scopes` (bare string / int / null); only a truly
  absent key (or a legacy raw-string token) inherits wildcard.
- **Scope vocabulary completed.** 22 scope ids used by real tools were missing
  from `AVAILABLE_SCOPES` (incl. `system.write` → plugins.enable/disable,
  `system.read` → 23 tools, cms/crm/seo/tax/shipping/b2b/affiliates/…). A token
  could not be scoped to them in the dashboard, so merchants fell back to
  wildcard — the scope system was decorative. All added, grouped, sensitive ones
  flagged. New `ScopeVocabularyTests` asserts `{tool scopes} ⊆ AVAILABLE_SCOPES`.
- **Kill-switch parity.** `_handle_tools_call` now refuses `requires_approval`
  tools when `agents_paused()` (the merchant kill switch previously stopped Linda
  and the Workers but left the Bearer path live). Reads + buyer cart/checkout
  stay up.

### GraphQL authorization
- **Any Bearer token = full admin (CRITICAL).** `has_scope` returned True for
  every scope when the user is staff, and every MCP/agent token resolves to a
  shared `is_staff=True` service user — so a `catalog.read` token passed
  `admin:seo`, `read:orders`, `cms.write`, … Now: when a token stashed its
  graphql scope set, authorize against THAT (honouring wildcard/legacy) and never
  fall through to is_staff. A genuine session-staff user (no token) is unchanged.
- **Vendor IDOR ×2.** `myVendorOrders` / `myVendorPayouts` returned *every*
  vendor's financials despite the `my*` naming — no `vendor=` filter. Now scoped
  to `vendor__owner = current_customer` unless `admin:marketplace`.
- **`metricSeries` leaked all channels.** `qs.filter(channel__isnull=True) | qs`
  OR'd the unfiltered queryset back in (a no-op). Fixed to the intended filter.

### Cache + price parity
- **Invalidation guard pointed at dead code.** The GraphQL response cache is
  written by `api/middleware.py`; the `api/cache.py` SchemaExtension was never in
  `api/schema.py`'s `extensions=[...]` — dead code the guard read as source.
  A middleware key change would go uncaught while every purge matched zero keys.
  Repointed the guard at the real writer; **deleted `api/cache.py`**.
- **Price-seam parity.** `ProductVariantType.price` and
  `AgentProductMetadata.price_amount` read `self.price` raw, skipping
  `apply_price_filter`, while the PDP headline and the charged leg both apply it —
  so a pricing rule moved the headline but not the variant picker or the agent
  feed (displayed ≠ charged). Both now route through the seam.

### Housekeeping
- Pre-existing CI `lint`/bandit failure (3× B310 urlopen, update-system files):
  the scheme is validated (`startswith('https://')` / fixed host) at each site,
  so added the missing `# nosec B310` markers next to the existing `# noqa: S310`
  (the repo's established both-linters pattern). CI green again.

---

## Shipped in v0.56.0

1. **Cart mutation IDOR — FIXED.** One ownership seam
   `orders/graphql/_ownership.py` (`may_access_cart` + `load_owned_cart` +
   `load_owned_item`), shared by `queries._resolve_cart`, all eight cart
   mutations (setShippingRate/updateCartItem/removeCartItem/applyCoupon/
   removeCoupon/applyGiftCard/removeGiftCard/completeOrder), and shipping's
   `shippingRates` (deduped onto the same predicate — shipping already declares
   `requires=['orders']`). A non-owning session gets the SAME `NOT_FOUND` as a
   missing cart (no enumeration oracle) and the cart is left untouched;
   `read:carts` tokens remain the agent escape hatch. `addToCart` now IGNORES
   the caller-supplied `session_key` (derives from the request cookie, minting a
   session when absent so the anon cart is properly owned — also closes the
   shared `''`-key cart bug); `CartType.sessionKey` returns `''`. Both
   `session_key` fields kept for API stability (deprecated, neutralized). 9
   boundary tests (`orders/tests/test_graphql_cart_ownership.py`).
2. **`orders(order_by:)` sort-key whitelist** — a raw string reached
   `.order_by()` (FieldError 500 / relation-span leak); now falls back to the
   default off-whitelist. Guarded by `test_graphql_orders_sort.py`.
3. **`journalEntries(limit:)` capped** at 100 (was uncapped → cheap DoS).

## Shipped in v0.57.0 (MCP + GraphQL robustness batch)

4. **Product-list N+1 — FIXED (the safe subset).** `ProductType.collections`,
   `.price`, `.priceStartsFrom` did `.filter()`/`.count()` on relations already
   in `_PRODUCT_PREFETCH`, discarding the prefetch cache and re-querying per
   product. Now Python-filter over `.all()` — identical semantics, no re-query,
   no pessimization. Guarded by `catalog/tests/test_graphql_n_plus_one.py`
   (query count stays flat as N grows). `reviews` (not prefetched) + its
   `customer.full_name` left as-is: an unconditional reviews prefetch would
   pessimize the common product-list path that doesn't request reviews — better
   solved by strawberry-django field-based optimization (deferred).
5. **MCP tool-argument validation — FIXED.** `_validate_tool_args` (dependency
   -free JSON-Schema subset: required/type/enum/min-max/length) runs before
   `invoke`, returns `-32602`. Tool.invoke drops unknown args silently, so an
   out-of-range/wrong-typed value used to reach the ORM as a default-valued
   success. Unknown-arg rejection deliberately omitted (schemas are often
   under-specified). Guarded by `agent_mcp/tests/test_arg_validation.py`.
8. **MCP discovery metered — FIXED.** `initialize`/`tools/list`/`resources/list`/
   `ping` now go through `_enforce_discovery_rate_limit` (240/min per token-or-IP
   bucket) in `_dispatch` — was free admin-tool enumeration + DB-amplification.

## Still deferred

2. **Response-cache vary-tuple + event coverage (its own release — risk).** The
   key hashes query+vars only — blind to market/currency/language/channel (first
   EUR/`/fr/` visitor poisons the entry for 5 min) — and invalidation binds only
   PRODUCT_UPDATED/CATEGORY_UPDATED (price/stock/seo/cms/collection/delete leave
   stale payloads). Also swap `GraphQLCacheMiddleware` after the rate limiter (a
   HIT bypasses metering) and replace the `'cart' in query` leak-guard with an
   explicit cacheable-root-field allowlist. Held back deliberately: getting the
   key or invalidation wrong serves stale/wrong data — needs dedicated cache-vary
   tests, not a batch.
3. **Eight divergent GraphQL auth patterns → one seam (design-heavy).** raise /
   silent-`[]` / payload-error / inline is_staff / queryset-scoping / none.
   `core/authz.py` (the capability seam) has zero GraphQL callers, so dashboard
   capability revocation doesn't touch this surface. Unify onto capabilities so
   GraphQL and the dashboard revoke together — touches every plugin's GraphQL
   extension; a dedicated refactor.
6. **MCP scope semantics: OR vs AND (behaviour change).** `has_any` passes on one
   required scope; the in-process runtime requires all. Reconciling (two scopes =
   both) needs a sweep of every multi-scope tool to confirm intent first.
7. **`semanticSearch` cost guard.** Unauthenticated embedding call per query.
   Requiring auth would break public storefront search; the right fix is a
   per-IP cost/rate guard for that one expensive field — a small design decision.
   (`order_by`, list caps, journal cap already shipped in v0.56.0.)
9. **`docs/MCP_SERVER.md` per-tool "Approval? no" table** — re-audit against the
   enforced gate (the endpoint/health/tool-name drift is already corrected).
   Dead `TAG_MAP` CF-purge rows: cosmetic (unmatched rows never fire); pruning
   the wrong one breaks edge-purging, so left until the live schema field names
   are introspected.
