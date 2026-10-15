# Wave 0: consent, AI guardrails, per-request cost, latent defects

**Status:** shipped in v0.113.0.
**Source:** `docs/plans/apps-consolidation-2026-10.md`, Wave 0 items 3, 8, 9 and 10 (items 1, 2, 4–7
shipped in v0.101.0). The facts below were re-checked against the tree on 2026-10-15.
**Ships as:** one MINOR release. Wave 1 (deletions) and the Wave 2 merges are separate sub-projects.

## Goal

Four problems each touch live stores today:

1. Shopper data leaves the store without the shopper's consent.
2. Six model callers skip the AI kill switch and the daily spend cap.
3. Every crawler hit costs a database write and a cookie.
4. Three latent defects would misbehave as soon as a merchant uses the feature:
   - webhooks delivered twice,
   - ad spend overstated ~31×,
   - staff-entered URLs posted without the private-network check.

Fix all four in one release without changing what a store that runs no consent, no AI and no
webhooks sees.

## Success criteria

- On a store that manages consent, none of these sends without a recorded "yes":
  - the five server-side conversion APIs and server-side GA4 (one check, `core/consent.py`),
  - `meta.sync_audience`,
  - the Google Ads purchase tag.

  A store with consent switched off, or the consent app off, sends exactly as today.
- With the kill switch on, every model call in the tree is refused. That includes the six direct
  callers, embeddings and text-to-speech.
- Model calls made outside an agent run count toward the daily spend cap.
- A cookie-less GET of the home page, a listing page and a product page answers with no
  `Set-Cookie: sessionid`. Expired sessions are cleared daily.
- One POST per endpoint per event, sent after the transaction commits, and never following a
  redirect.
- The attribution page's spend and revenue equal one 30-day total, not the sum of every daily
  snapshot.
- Each fix has a test that failed before it. The full suite and every CI gate are green.

## A. Consent before anything leaves the store (item 3)

### Facts

- Five apps send sha256(email) plus the purchase on `ORDER_PAID`, with no consent check:
  - `meta_commerce/services/capi.py`
  - `tiktok_commerce/services/events_api.py`
  - `pinterest_commerce/services/capi.py`
  - `snapchat_commerce/services/capi.py`
  - `reddit_ads/services/capi.py`

  Meta and TikTok also send on `ADD_TO_CART` and `BEGIN_CHECKOUT`, and Pinterest also sends on
  `ADD_TO_CART`.
- `ORDER_PAID` passes only the order. It fires from the Stripe and PayPal webhooks, the staff
  "mark paid" action and agentic checkout, so no visitor's request exists at that point.
- The order stores no consent.
- `tracking` sends GA4 Measurement Protocol events server-side for purchase, refund, add/remove
  from cart, begin checkout, view item, sign-up, login and search. None of them checks consent.
- The consent decision is the `morpheus_consent` cookie, read by
  `consent.services.read_consent_from_cookie`. It is necessary-only by default and under `Sec-GPC`.
- The store-level switch is `core.context_processors._gdpr_enabled()`
  (`StoreSettings.gdpr_enabled`, default True).
- The browser-side rule since v0.91.0 is `not consent.managed or consent.marketing`.

### Design

**New `core/consent.py`.** Core cannot import the consent app, so the app answers through a new
filter, `MorpheusEvents.CONSENT_DECISION`. The filter's value is `None` and its kwarg is
`request=` (a request or `None`).

- The consent app answers with `{'managed': _gdpr_enabled(), 'analytics': bool, 'marketing': bool}`.
  When the request is `None` there is no visitor, so `analytics` and `marketing` are `False`.
- With the consent app off, nothing answers. The bus skips inactive owners, so the value stays
  `None`, which means the store does not manage consent. This matches the template rule, where
  `consent` is absent from the context.

`core/consent.py` defines three functions:

- `decision_for(request) -> dict` returns the answer, normalised. When nothing answers it returns
  `{'managed': False, 'analytics': False, 'marketing': False}`.
- `stamp(request) -> dict` is `decision_for(request)`, the shape stored on an order.
- `allowed(category, *, order=None, request=None) -> bool`. `category` is `'marketing'` or
  `'analytics'`. The first rule that applies decides:
  1. **The order carries a stamp** (`order.metadata['consent']`): allowed when the stamp says
     `not managed`, or says that category is `True`.
  2. **A request is given:** the same rule, applied to `decision_for(request)`.
  3. **Neither:** the same rule, applied to `decision_for(None)`. A managed store therefore
     refuses when it has no evidence (a draft order, an order placed before this release, an
     event fired without a request), and an unmanaged store allows.

**The order records the choice.**
- `OrderService.create_from_cart` gains the keyword `consent: dict | None = None`, and
  `_order_metadata` stores it as `metadata['consent']`.
- The storefront checkout mutation (`orders/graphql/mutations.py`) passes
  `core.consent.stamp(request)`.
- Agentic checkout (`agentic_checkout/views.py`) passes `stamp(request)` too. An agent's request
  carries no consent cookie, so on a managed store its order records no consent.

**Senders.**
- Each of the five apps checks `allowed('marketing', order=order)` in its `ORDER_PAID` handler.
- Each checks `allowed('marketing', request=request)` in whichever `ADD_TO_CART` and
  `BEGIN_CHECKOUT` handlers it has.
- `tracking._fire` checks `allowed('analytics', order=…, request=…)` for every event.
- Storefront fire sites that have a request but don't pass it now add `request=request`:
  `ADD_TO_CART` in `storefront/views/cart.py`, plus `REMOVE_FROM_CART` and `SEARCH_PERFORMED`
  wherever they lack it.
- `customers/signals.py` fires `CUSTOMER_REGISTERED` with no request. On a managed store, the
  server-side `sign_up` event therefore stops, which is correct, since there is no evidence of
  consent.
- Browser-side pixels are already gated (v0.91.0). The plan verifies that Snapchat's
  advanced-matching hash sits inside that gate.

**`meta.sync_audience`.**
- The scope changes from `analytics.read` to `crm.write` (the scope `customers.write` maps to in
  `gates.py`), and the tool gains `requires_approval=True`.
- `audiences._segment_emails` never includes staff or superusers.
- On a managed store:
  - `purchasers` uses only orders whose stamp says `marketing: True`.
  - `all_customers` uses only customers whose most recent `ConsentLog` says `marketing`. The
    consent app answers a second filter, `CONSENT_MARKETING_CUSTOMERS` (value `None`, which means
    no restriction), with a set of customer ids, so meta_commerce never imports consent.

**`tracking` app.**
- The Google Ads purchase tag (`tracking/templatetags/tracking.py`) becomes `takes_context` and
  renders nothing when `consent.managed and not consent.marketing`. The check sits inside the tag,
  so all four themes' `order_confirmation.html` are covered.
- The second banner is deleted:
  - the `tracking_consent_banner` tag and its template,
  - the `show_consent_banner` setting,
  - the three theme `base.html` references.

  The consent app is the one banner.

## B. Every model call obeys the kill switch and the spend cap (item 8)

### Facts

- v0.104.0 guards `ai_assistant`'s `LLMGateway.complete` with `__init_subclass__` +
  `guardrail_refusal()`.
- Six callers still call `core.agents.llm` providers' `respond()` directly, outside any agent run:
  - `admin_dashboard/views_split/products.py` (`content_fill_one`)
  - `core/assistant/page_help.py`
  - `core/brain/analyst.py`
  - `morpheus_brain/services.py`
  - `dynamics/autopilot.py`
  - `core/self_improvement/recommend.py` and `verify.py`
- `agent_core/tools/content.py` calls `respond()` from inside tools. Those calls run inside
  Worker runs and inside Linda's MCP tool calls, and Linda's tool calls are not runs.
- The paid calls with no guard at all:
  - `core/embeddings.py` (OpenAI embeddings)
  - `ai_assistant` `LLMGateway.embed`
  - ElevenLabs text-to-speech in `audiobooks/services.py:_tts`
- `agent_mcp` is not in `core/safety.py:PROTECTED_PLUGINS`. Disabling it unmounts `/mcp/`, and
  every Linda turn then has zero tools.

### Design

**The guard moves into core.** `core/agents/guardrails.py` gains:
- `AIPaused(RuntimeError)`. ai_assistant re-exports it, so its callers keep working.
- `model_call_refusal() -> str` (the body of today's `guardrail_refusal`; ai_assistant's function
  calls it).

**Provider-level guard.** `LLMProvider.__init_subclass__` wraps every `respond` a provider
defines, the same pattern as v0.104.0.
- Before the call: raise `AIPaused(reason)` when `model_call_refusal()` refuses.
- After the call: record the response's tokens.
- Two context variables decide when the wrapper does nothing:
  - `run_scope()`: `AgentRuntime.run` enters it. A run already checks both caps at its start, and
    its tokens already count through `AgentRun`, so calls inside a run are neither re-checked nor
    re-counted.
  - A nesting depth: only the outermost wrapped call checks and records.
    `FallbackProviderRouter.respond` calls a provider's `respond`, which would otherwise count
    twice.

**Usage outside runs is counted.**
- New core model `ModelUsageDay(day, model, prompt_tokens, completion_tokens)`, unique per
  `(day, model)`, incremented with `F()`. It comes with a core migration.
- `guardrails.daily_spend_usd` adds today's rows.
- Linda's own tokens still come from `AssistantMessage`. Model calls her tools make are now counted
  too. They were spend that no cap saw before; they are not counted twice.

**Callers.** Each of the six direct callers, and the content tools, handle `AIPaused` the way they
already handle a provider error:
- The dashboard's fill button shows the guard's message.
- Background jobs log the refusal and skip.
- Nothing returns a 500.

**Embeddings and TTS.**
- While the kill switch is on:
  - `core/embeddings.py` uses its existing hash fallback,
  - `LLMGateway.embed` raises `AIPaused`,
  - `audiobooks._tts` raises `AIPaused`, and the audiobook job records the failure.
- These calls are not counted toward the dollar cap, because `core/agents/pricing.py` prices none
  of these models.

**`agent_mcp` becomes protected.** It is added to `PROTECTED_PLUGINS` in `core/safety.py`, the
non-editable list, rather than the manifest.

**Changed from the chat design.** The design gave the MCP Bearer door a spend-cap check. That is
dropped. An external agent pays for its own model, so a tool call spends the store's model money
only when the tool itself calls a model, and that call now meets the provider-level guard. A cap
check at the door would refuse an external agent's free reads once the merchant's own AI hit its
limit.

## C. Per-request cost (item 9)

### Facts

- `ai_assistant/middleware.py:AIContextMiddleware` runs on every request.
  - It writes `session['ab_cohort']`, which nothing reads. Because sessions are database-backed,
    each cookie-less request (every crawler hit) costs an INSERT plus `Set-Cookie: sessionid`.
  - The `sessionid` cookie is in `storefront/middleware.py:_PRIVATE_COOKIES`, so the visitor's
    later pages lose edge caching.
  - For signed-in users it also queries `AgentMemory`. Its only reader,
    `get_memory_context_string`, has no callers.
- Nothing schedules `clearsessions`.
- `environments/middleware.py` runs 2 queries per request (none of the domains match, then the
  production fallback). Nothing reads `request.environment`.

### Design

**`AIContextMiddleware`.**
- The `ab_cohort` session write and the `AgentMemory` query are deleted.
- So are the orphans this leaves: `AIContext.ab_cohort`, `.memories`,
  `get_memory_context_string` and `_attach_customer_memories`.
- The agent-token path, the only part with readers, stays.

**`EnvironmentMiddleware`** is removed from `MIDDLEWARE` in `morph/settings.py`. The app itself
goes in Wave 1.

**Clearing sessions.**
- New core task `core.tasks.clear_expired_sessions`, which calls
  `SessionStore.clear_expired()`. It runs daily from `_CORE_BEAT_SCHEDULE` in `morph/celery.py`
  under its registered name (`test_beat_schedule.py` checks it).
- After deploy, a one-time `manage.py clearsessions` runs on each live store, and the
  `django_session` row counts before and after are reported.

**Left out of Wave 0.** The `markets` middleware costs 1–2 queries per request, and Wave 2 deletes
that app.

## D. Latent defects (item 10)

### Webhooks: one trigger, one POST

**Facts.**
- Core's `HookRegistry._dispatch_remote` posts every subscribed event through
  `core.tasks.dispatch_webhook`. It sends after commit and honours `'*'`.
- `webhooks_ui` subscribes 12 events and enqueues its own delivery:
  - It has a log, retries, a dead-letter state, replay and an `X-Morpheus-Delivery` header.
  - Its enqueue happens synchronously during the hook, so the POST can run before the transaction
    commits, or for a transaction that rolls back.
  - It ignores `'*'`.
  - Its body shape is `{"event", "data"}`, while core's is the bare payload.
- So an endpoint gets two POSTs in two shapes. No live store has an endpoint yet.

**Design.**
- Core's `_dispatch_remote` is the only trigger.
- For each matching endpoint, after commit, it asks a new filter,
  `MorpheusEvents.WEBHOOK_DELIVER` (value `False`, kwargs `endpoint`, `event`, `payload`), whether
  a delivery owner takes it.
  - `webhooks_ui` answers by creating its `WebhookDelivery` row, enqueueing its task, and
    returning `True`. The merchant keeps the log, the retries, the dead-letter queue and replay.
  - When `webhooks_ui` is off, nothing answers and core posts itself.
- `webhooks_ui` drops its 12 fan-out subscriptions.

**One body shape.**
- `webhooks_ui`'s deliverer sends core's body, built by `core.tasks._canonical_payload` and
  signed by `compute_hmac_signature`.
- The `X-Morpheus-Event` header is the same on both paths.
- `X-Morpheus-Delivery` and `X-Morpheus-Attempt` stay as extra headers.
- `docs/WEBHOOK_RECIPES.md` gains the body shape.
- The change is recorded in `docs/MIGRATING.md` and in the "Breaking changes shipped" table in
  `docs/API_STABILITY.md`. A receiver built against `{"event", "data"}` must read the bare
  payload; no live store has an endpoint.

### Attribution: one 30-day total

**Facts.**
- `analytics.services_attribution.collect_ad_spend` stores each channel's trailing 30-day spend
  every day (Meta and Google report `'days': 30`).
- `attribute_revenue` stores trailing 30-day revenue every day.
- `roas_by_channel` sums every row of the last 30 days, which counts each total up to 31 times.
- Meta's spend is keyed `meta`, while its traffic arrives as `utm_source` `facebook`, `fb`,
  `instagram` or `ig`.

**Design.**
- `roas_by_channel` reads only the newest snapshot day for spend and the newest attribution day for
  revenue.
- `_channel_of` maps `facebook`, `fb`, `instagram` and `ig` to `meta`.

**Left out.** Spend and revenue are stored as USD whatever the store's currency. That is noted, not
fixed here.

### Staff-entered URLs: the private-network check, and no redirects

**Facts.**
- `core/net.py:check_outbound_url` guards only core's and `webhooks_ui`'s webhook posts, and both
  follow redirects, which bypasses the check.
- These are unguarded:
  - the workflow `webhook_post` action (`workflows/engine.py`, which runs inline),
  - the OpenAI feed push (`openai_shopping/tasks.py`; `push_endpoint` is a setting Janus can
    write),
  - the Shopify and WooCommerce importers (staff-entered store URLs).

**Design.**
- `core/net.py` gains `outbound_request(method, url, *, require_https=True, field='url', **kw)`.
  It runs `check_outbound_url` and sends with `allow_redirects=False`.
- All six call sites use it:
  - workflows and the two webhook deliverers keep `require_https=False`,
  - the feed push requires https,
  - the importers keep `require_https=False` (a WooCommerce shop may be http), but public hosts
    only.
- A refused URL becomes the call site's existing failure result. Nothing raises into a request.

**Left out.**
- DNS rebinding between the check and the connection.
- AI provider base URLs: a local Ollama is legitimately private, so these need an allowlist.

## Testing

Each item gets a test that fails before its fix.

**Consent**
- The order stamp is written at checkout.
- For each of the five senders and for GA4:
  - a managed store with no consent: nothing is sent,
  - a managed store with consent: sent,
  - an unmanaged store: sent.
- A draft order on a managed store: nothing is sent.
- `sync_audience` excludes staff and non-consenting customers, and carries `requires_approval`.
- The Ads tag is absent without marketing consent.
- The second banner is gone from all three themes.

**Guardrails**
- Each of the six callers, and the content tool, is refused while paused, and none of them 500s.
- A run's calls are neither re-checked nor double-counted.
- The fallback router counts once.
- `ModelUsageDay` rows reach `daily_spend_usd`.
- Embeddings fall back while paused, and TTS is refused while paused.
- `is_plugin_protected('agent_mcp')` is True.

**Per-request cost**
- Cookie-less GETs of home, listing and product set no `sessionid`.
- The middleware list no longer contains `EnvironmentMiddleware`.
- The new beat entry is registered.

**Webhooks**
- One POST per endpoint with `webhooks_ui` on, and one with it off.
- Nothing is sent when the transaction rolls back.
- `'*'` reaches `webhooks_ui`'s log.
- The body is the same shape on both paths.

**Attribution**
- 31 daily snapshots of a 30-day total report that total once.
- `facebook` traffic meets `meta` spend.

**Outbound requests**
- A private address, a redirect to a private address, and a non-https feed endpoint are each
  refused, and the call site reports the refusal.

**Whole-change checks**
- The full suite with every extra app (the 4,832-test command).
- ruff check and format.
- `manage.py check`.
- `makemigrations --check`.
- The three boundary ratchets.
- Each changed template compiles.

## After deploy (live checks)

On every store:
- `curl` the home page, a listing and a product with no cookies: no `Set-Cookie: sessionid`.
- One-time `clearsessions`, with row counts.

On Montenegro, the order-confirmation page without consent renders no Google Ads tag.

`/readyz` reports the new version on all five deployments.

## Docs in the same release

**`CLAUDE.md`**
- The consent landmine: server-side sends now pass `core/consent.py`, and the order carries the
  stamp.
- Guardrails item (4): the guard sits at the provider class; `ModelUsageDay`; `run_scope`.
- The webhook rule: one trigger, `WEBHOOK_DELIVER`.

**Other docs**
- `docs/plans/apps-consolidation-2026-10.md`: Wave 0's status line.
- `docs/WEBHOOK_RECIPES.md`, `docs/MIGRATING.md` and `docs/API_STABILITY.md` (the webhook body).
- `docs/RELEASE_NOTES.md` via `manage.py release --minor`.
