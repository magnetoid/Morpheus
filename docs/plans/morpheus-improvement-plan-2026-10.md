# Morpheus improvement plan — October 2026

**Status:** proposed, 2026-10-10. Written from a code + production scan and from
market/regulatory research done the same day. This is the one page to plan
from; it carries forward the open items of
[`roadmap-reconciliation-2026-08.md`](roadmap-reconciliation-2026-08.md),
[`ecommerce-stability-2026-09.md`](ecommerce-stability-2026-09.md) (Release 3),
[`linda-sessions-automations-models-2026-10.md`](linda-sessions-automations-models-2026-10.md)
("left for later"), [`boundary-debt-2026-07.md`](boundary-debt-2026-07.md),
[`deep-debug-2026-09.md`](deep-debug-2026-09.md) and
[`irving-vendors-affiliates-prelaunch-2026-10.md`](irving-vendors-affiliates-prelaunch-2026-10.md).
The 19 strategy documents under `docs/analysis/` (June–July 2026, written before
v0.40) are background only; where they disagree with this page, this page was
checked against the code and they were not.

**How it was produced.** Five read-only scanners (plans/debt, code bugs, live
health, Irving launch, infra/CI) and eleven adversarial verifications ran as one
workflow on 2026-10-10; a read-only exploration covered the quality
infrastructure (plans, CI, tests, dependencies, assets, security scan); the
plugin inventory and the commerce-depth audit were measured with batched scripts
over the tree (two exploration agents were cut off by the session limit); ~40
web searches and spec fetches; live measurements with Chrome DevTools Lighthouse
(mobile, four home pages), `curl` (TTFB, headers) and read-only Cloudflare and
Coolify API calls. Every finding below is tagged **LIVE** (observed on a store),
**CODE** (verified in the tree at `3a4d3579`, v0.87.0) or **INFERRED**.

**Ground rules** (unchanged from the August reconciliation, still true): Morpheus
is one person plus AI. One workstream at a time; every item shippable in days,
with its own `manage.py release` bump, verified on production before the next
starts. Owner decisions are listed separately from engineering work. No
enterprise-roadmap staffing fantasies.

---

## 1. The world in October 2026 (research digest)

### 1.1 Agentic commerce — the protocols settled this year

| Protocol | State (Oct 2026) | What a merchant on a custom stack does |
|---|---|---|
| **ACP** (OpenAI + Stripe) | Instant Checkout in ChatGPT was **retired in March 2026** (about a dozen Shopify merchants ever shipped on it). The protocol continues as the discovery/checkout spec: latest stable **2026-04-17**; PayPal joined Oct 2025; Stripe's Agentic Commerce Suite Dec 2025; Salesforce support. ChatGPT shopping is now ACP-powered *discovery* plus retailer apps (Walmart, Target, Instacart). | Submit a **product feed** (apply at chatgpt.com/merchants; JSONL/CSV/TSV, refresh as often as every 15 min, pushed over HTTPS to an allow-listed endpoint). Required: `item_id`, `title`, `description`, `url`, `brand`, `seller_name`, `image_url`, `availability`, `price`; flags `is_eligible_search` (default true) / `is_eligible_checkout` (default false; needs `seller_privacy_policy` + `seller_tos`); variants via `group_id` + `variant_dict`; returns via `accepts_returns`, `return_deadline_in_days`, `return_policy`. Shopify stores are in by default (Agentic Storefronts, late March 2026). |
| **UCP** (Google + Shopify, announced NRF 11 Jan 2026; backed by Amazon, Meta, Microsoft, Salesforce, Stripe, Etsy, Target, Wayfair) | Live in the US; Stripe + Google: buy inside AI Mode and Gemini via UCP. | Publish `/.well-known/ucp` with `ucp.version` (date string; latest **2026-08-25**), `services` (transports `rest`, `mcp`, `a2a`, `embedded`), `payment_handlers`, `capabilities` namespaced `dev.ucp.shopping.checkout` / `.cart` / `.order`, `dev.ucp.common.identity_linking`, extensions `fulfillment`, `discount`; checkout = `create_checkout` / `update_checkout` / `complete_checkout`; optional `keys[]` (JWKS) for signing. |
| **AP2** (Google, Sept 2025, 60+ partners) | Signed Intent / Cart / Payment mandates; Mastercard Agent Pay and Visa Trusted Agent map onto it, parity telegraphed for mid-2026; contributed to the **FIDO Alliance on 26 May 2026**. | Nothing yet without a PSP that issues the tokens (Stripe SPT, Adyen). Watch. |
| **Web Bot Auth** (Cloudflare → IETF) | `draft-ietf-webbotauth-httpsig-protocol-00` (working-group draft, 1 Sept 2026) on RFC 9421 HTTP Message Signatures. Verified at the edge by Cloudflare, Akamai, AWS, Vercel, HUMAN; OpenAI signs ChatGPT agent requests. Visa TAP rides on it. | Verify `Signature-Input`/`Signature` against the agent's published JWKS at the origin, or trust the edge's verified-agent headers. |
| **MCP** | Revision **2026-07-28** (final 28 Jul 2026): stateless — no `Mcp-Session-Id`, no `initialize` handshake; version + client capabilities travel in `_meta`; `server/discover` is mandatory; every result carries `resultType`; list results carry `ttlMs` + `cacheScope`; `Mcp-Method`/`Mcp-Name` headers; `subscriptions/listen`; sampling/roots/logging deprecated; DCR deprecated for Client ID Metadata Documents; a 12-month deprecation window. | Negotiate versions; serve `server/discover`; keep the old handshake for old clients during the window. |
| **WebMCP** (Google + Microsoft, W3C WebML CG) | Chrome **149 origin trial** (announced at I/O, 19 May 2026); declarative (annotated HTML forms) and imperative (`navigator.modelContext`) APIs; Gemini-in-Chrome "coming". **Lighthouse now has an "Agentic Browsing" category** (agent accessibility tree, WebMCP form coverage, registered tools, schema validity, CLS, llms.txt) — measured on all four stores today. | Annotate storefront forms; register a few tools backed by the existing MCP cart server. |

Market signals: AI-referred traffic to retailers grew **393 % YoY** in Q1 2026
and converts **42 % better** (revenue per visit +37 %); ChatGPT referrals convert
at 2.47 % vs 1.82 % for paid search; Perplexity's merchant program charges
nothing and has 5,000+ merchants; Morgan Stanley puts $385 B of US e-commerce
on agentic channels by 2030. Cloudflare blocks training **and agent** crawlers by
default on new/free zones since **15 Sept 2026** — our four zones have
`ai_bots_protection = disabled` (**LIVE**, read today), so agents can reach the
stores; that must stay a deliberate, documented choice.

### 1.2 Regulation that bites a shop now

- **EU AI Act Art. 50** became enforceable on **2 Aug 2026** and was *not*
  delayed by the AI Omnibus: chatbots must disclose they are AI; synthetic text,
  image, audio and video must carry machine-readable marking; deployers using
  third-party tools are in scope; fines up to €15 M / 3 %. The AI Omnibus
  (Reg. (EU) 2026/1744, in force 27 Jul 2026) pushed Annex III high-risk duties to
  **2 Dec 2027** and product-embedded ones to **2 Aug 2028** — nothing a store
  assistant falls under.
- **Digital Omnibus (GDPR / cookies)** is stalled in first reading (1,750+
  amendments, no Council mandate as of Sept 2026). Direction if it passes:
  consent-free low-risk purposes, one-click reject, remember a refusal for six
  months, honour Global Privacy Control. Plan for it; don't depend on it.
- **European Accessibility Act**: enforced since 28 Jun 2025 for e-commerce
  sold to EU consumers (micro-enterprises under 10 staff and €2 M exempt).
  Baseline WCAG 2.1 AA via EN 301 549; 2.2 recommended (now ISO/IEC 40500:2025).
- **GPSR** (since 13 Dec 2024, no transition): every listing shows the
  manufacturer's name, postal and electronic address, an **EU responsible
  person** when the manufacturer is outside the EU, product identifiers, and
  warnings in the consumer's language. Warning letters are being sent.
- **UK DMCC Act**: the CMA enforces directly since April 2025 (fines up to 10 %
  of global turnover). First fine in 2026 (the AA, £4.2 M: a mandatory £3 fee not
  in the headline price). Five of the first eight investigations are **drip
  pricing**; fake-review probes opened March 2026; a consultation on fake
  "was" prices, invented discounts and misleading RRPs was announced 9 Aug 2026.
  Rule: the full price including every unavoidable charge, the first time a price
  is shown. (EU: the Price Indication Directive already requires the lowest price
  of the prior 30 days next to any reduction.)
- **PCI DSS 4.0.1** 6.4.3 and 11.6.1 (mandatory since 31 Mar 2025): inventory,
  authorise and integrity-check every script on the payment page, and detect
  tampering with scripts and headers. The merchant owns the parent page even
  with a PSP iframe.
- **Email**: SPF + DKIM + aligned DMARC is the floor for Gmail/Yahoo/Outlook;
  Gmail has rejected non-compliant mail since Nov 2025, Outlook since May 2025;
  no DMARC is a reputation negative at any volume.

### 1.3 The stack

- **Django 6.0** (Dec 2025; security fixes until Apr 2027): built-in Tasks
  framework, built-in CSP middleware, template partials, modern email API;
  needs Python ≥ 3.12. **Django 6.1** (5 Aug 2026): model-field fetch modes (most
  N+1 loops become two queries), database-level `on_delete`, `MAILERS`. Django
  shipped security releases on 5 May, 3 Jun (five CVEs, including SMTP STARTTLS
  and cache `Vary` leaks), 7 Jul and 4 Aug 2026 — a monthly cadence that an
  unpinned production image follows blindly.
- **Python 3.14**: free-threading is officially supported; C-extension wheels
  are still the blocker. Not for us this year.
- **Celery** is still the standard where routing/queues matter; Django Tasks is
  fine for simple jobs. Keep Celery.
- **Tailwind Play CDN** is explicitly "not for production" (it warns in the
  console) and is why the dashboard CSP still carries `'unsafe-eval'`.
- Peers: Medusa 2.18 (Jul 2026, admin Layout Composer), Saleor, Vendure, Sylius,
  Shopware — all headless/TypeScript or PHP. Shopify Summer '26 "Everywhere
  Edition" (17 Jun 2026): Horizon theme architecture with AI editing, Sidekick
  multi-step/voice/image generation in 20 languages, Payments in 16 more
  countries, "ship and carry out" POS.

### 1.4 Search and performance

- AI Overviews appear on **14 %** of shopping queries (Mar 2026, from 2.1 % in
  Nov 2025); organic CTR with an AIO fell from 1.76 % to 0.61 %; brands *cited*
  in an AIO get +35 % clicks. Complete Product JSON-LD and feed completeness are
  the lever.
- Google merchant listings 2026: `shippingDetails` + `returnPolicy` are practical
  requirements; complex return policies live on **Organization**-level
  `MerchantReturnPolicy`; 7 Jul 2026 added `category` (Google product category)
  on `Product` and documented "sale duration" (`validFrom`/`validThrough`/
  `priceValidUntil`). Merchant Center added carrier and handling/transit
  business-day attributes; one unified Shopping policy set since Sept 2026.
- **llms.txt**: adoption up 8.8× but **97 % of files get zero requests**; Google
  calls it speculative and prefers WebMCP. Keep ours; stop investing.
- Core Web Vitals: sources report INP "good" tightened to **150 ms** (April
  2026) and domain-level aggregation — treat as reported until CrUX confirms;
  43 % of sites fail INP.
- Checkout: average abandonment **70.19 %** (Baymard, 49 studies); 18 % abandon a
  long/complicated checkout; the ideal flow has 12–14 form elements vs a 23.5
  average. Passkeys see ~35 % active use in e-commerce where offered (eBay: 60 %
  of iOS sign-ins); django-allauth's `mfa` app supports WebAuthn and passkey
  login (`MFA_PASSKEY_LOGIN_ENABLED`).

### 1.5 AI security

OWASP LLM Top 10 (2025) keeps prompt injection at #1 and adds excessive agency,
system-prompt leakage, vector/embedding weaknesses and unbounded consumption;
the OWASP **Top 10 for Agentic Applications** (Dec 2025) adds memory poisoning,
tool misuse, non-human identities and inter-agent poisoning. Morpheus already has
the hard parts (consent spent only by a human turn, scope gates at the MCP edge,
audit rows, spend/run caps). Gaps: the caps are **unset on every store**;
JanusLearning harvest is untrusted text that can steer; there is no tool-use
anomaly signal; nothing segregates "content Linda read" from "instructions".

---

## 2. Where Morpheus stands (measured 2026-10-10)

**Size and velocity.** v0.87.0; 264,602 lines of Python in 2,600 files; 692
templates; 108 default apps (113 directories under `plugins/installed/`); 215
commits and **95 releases since 1 Sept 2026** (28 in October). The release
machinery works; the risk is what each release carries, not the cadence.

**Live home pages, mobile Lighthouse (performance excluded by the tool):**

| Store | A11y | Best practices | SEO | Agentic browsing | TTFB | Notes (LIVE) |
|---|---|---|---|---|---|---|
| dotbooks.store | 100 | 100 | 100 | 100 | 0.48 s | clean |
| supernatural-shop.com | 97 | 96 | 100 | **67** | 0.42 s | contrast 4.0:1 (`#7a7166` on `#efeae2`, `.lede` and `h2`); console 404s on `/img/av…` (the known 79 missing images); `<article>` with an inappropriate ARIA role breaks the agent tree; **HSTS `max-age=0` and SSL mode "full"** — both Cloudflare zone settings, not Django |
| montenegro-experience.me | **88** | 100 | 100 | **67** | 0.36 s | `<select name="region">`/`category` without a label (fails a11y *and* the agent tree); heading order (`h4`); contrast 2.33:1 on a pill |
| beta.irvingsurvival.com | 100 | 100 | 69 | 100 | 0.44 s | SEO 69 = `noindex` (pre-launch, intended) |

WebMCP audits are "not applicable" on all four (nothing registered). Storefront
CSP is report-only everywhere; the dashboard CSP enforces with
`'unsafe-inline' 'unsafe-eval'`; HSTS preload for a year on three stores; COOP
and Permissions-Policy set. All four Cloudflare zones are on the Free plan;
`is_robots_txt_managed` is on for supernatural (Cloudflare appends to our
robots.txt).

**Agent surfaces versus the current specs (CODE):**

| Surface | Morpheus today | Current spec | Gap |
|---|---|---|---|
| MCP server (`agent_mcp/views.py:171`) | `protocolVersion: '2024-11-05'`, hardcoded; Streamable HTTP with a minted `Mcp-Session-Id` | 2026-07-28 | four revisions behind; no negotiation; sessions removed upstream |
| UCP (`agent_mcp/well_known.py`) | `/.well-known/ucp.json`, `protocolVersion: '1.0'`, boolean capability flags, `mcp` endpoint map (shipped v0.30.0, before the Jan 2026 spec) | `/.well-known/ucp`, `ucp.version: 2026-08-25`, `services` / `payment_handlers` / `capabilities` (`dev.ucp.shopping.*`), `keys` | pre-spec shape; an agent reading the spec finds nothing here |
| ACP checkout (`agentic_checkout/`) | `API-Version 2026-04-17`, five endpoints, SPT redemption | 2026-04-17 | current ✔ |
| ACP feed (`agentic_checkout/feed.py`) | `id`, `link`, `image_link`, `price` as string + `currency`, `availability` string | 2026-04-17 `Variant`: `id`, `title`, `url`, `price {amount (minor units), currency}`, `availability {available, status}`, `media[]`, `seller {name, links}`, `variant_options[]`, `barcodes[]` | old field shape under a new version header |
| OpenAI merchant feed (ChatGPT discovery) | none | `item_id`, `url`, `image_url`, `seller_name`, `is_eligible_*`, `group_id`/`variant_dict`, returns fields; pushed over HTTPS | missing — the only door into ChatGPT shopping for a non-Shopify store |
| Trusted Agent / Web Bot Auth (`agent.json`) | advertises acceptance only when `TRUSTED_AGENT_PROXY_SECRET` is set (Cloudflare-injected headers) | RFC 9421 signatures, agent JWKS directories | no verification at the origin; dotbooks is not proxied by Cloudflare at all |
| WebMCP | none | Chrome 149 origin trial, Lighthouse category | missing |
| `llms.txt`, `agents.md`, `/ai/products.json`, `/md/products/<slug>` | ✔ | low-value per the data | keep, don't extend |
| AI Act Art. 50 | `{% ai_disclosure %}` (chatbot disclosure, merchant text in `gdpr`) ✔ | + machine-readable marking of AI-generated content | marking missing |
| GPSR fields | none (only `consent`, `gdpr`) | manufacturer, EU responsible person, warnings per listing | missing |
| Passkeys (customers) | none | allauth `mfa` WebAuthn + passkey login | missing |
| Prior-price evidence | `compare_at_price` only, no history | 30-day lowest price (EU), "was" price evidence (UK) | missing |
| Free-shipping promises | **hardcoded** in `themes/library/dot_books/.../product_detail.html:409` and `cart.html:86` ("Free shipping over $40") and `montenegro/.../cart.html:115` ("€40") while `ShippingRate` count is 0 on every store | the promise must come from the shipping app | a claim without a source — the same class as the `og:image` / JSON-LD defaults landmine, and drip-pricing exposure on the UK store |

---

## 3. Verified findings (scan of 2026-10-10)

Severity is the *verified* one (eleven findings were re-checked by a second
agent, several downgraded).

### A. Production, now — needs the owner

1. **DeepSeek balance is $0** on dotbooks, supernatural and montenegro
   (`GET /user/balance`: `is_available=false`, three different keys; 402 at the
   06:00 pulse). Every AI feature on those stores fails. dotbooks has keys for
   five other providers but `fallback_providers=[]`. **LIVE, high, S.**
2. **Nobody can pay by card anywhere**: `enabled_gateways()` returns `['cod']`
   on all four; `ShippingRate` count is 0 on all four (checkout silently ships
   free); supernatural has 18 active products at $0 (unbuyable, listing noise).
   Known since Release 3 of the stability plan; waits on Stripe/PayPal
   credentials and rates. **LIVE, medium (dotbooks/supernatural), launch-blocking (Irving).**
3. **No agent spend or run caps** set on any store; `BackgroundAgent` rows: 0.
   Set before Automations or autonomy get used. **LIVE, S.**
4. **Backups live on the same RAID as the databases** (dotbooks 1.39 GB/night
   × 7); no `rclone`/`restic`/`aws` on the host; nothing ships off-host. **LIVE, M.**
5. **tetra disk 86 %**, 52.7 GB of other projects' volumes reclaimable, each push
   adds ~4 × 770 MB images; alert fires at 93 %. **LIVE, S.**
6. **Root `sutekh-watchdog` cron** (`pkill -9 -f /tmp/sutekh; rm -f /tmp/sutekh*`
   every minute, since 2026-08-21) is still installed; origin unknown. Must be
   understood before live payment keys land on this host. **LIVE, M.**
7. **Every Coolify env var is a build variable**: `SECRET_KEY`,
   `SERVICE_PASSWORD_POSTGRES`, `SERVICE_PASSWORD_REDIS` (all stores) and
   `DJANGO_SUPERUSER_PASSWORD` (supernatural) are in `docker history` of the live
   images. Flip "Build Variable" off, then rotate `SECRET_KEY` after a prune. **LIVE, S.**
8. **Production is not gated by CI**: `main` has no protection or rulesets and
   Coolify deploys every push — `ea0c12fc` deployed to all four stores with a red
   test job. **LIVE, M.**
9. **Cloudflare, supernatural-shop.com zone**: HSTS `max_age: 0` and SSL mode
   "full" (montenegro: 1 year, "strict"). Two settings, five minutes. **LIVE, S.**
10. **Irving has no SMTP** (the other three relay through tetra Postfix; recipe
    in memory/runbook); its health alerts and digest go to the log. **LIVE, S.**

### B. Supply chain and build

11. The image runs `pip install -r requirements.txt` (45 lines, **zero `==`
    pins**) while CI tests `requirements.lock.txt` with hashes: **48 of 107**
    packages differ between the live dotbooks container and the lock. **LIVE, high, M.**
12. Dependabot alerts and security updates are **disabled** on a public repo;
    the one open Dependabot PR (#96) cannot resolve against the stale lock. **LIVE, S.**
13. Janus builds from `JANUS_REF=main` into every image and the runtime updater
    installs any newer `main` SHA; `pip-audit` of the live Janus venv: pillow
    12.2.0 (25 advisories), PyJWT 2.12.1 (18), starlette 1.0.1 (8), mcp 1.26.0
    (6). `JANUS_KNOWN_GOOD=eafb7aba` is the head of `main` and carries no tag.
    **LIVE, medium, S.** The Janus layer (216 MB) is rebuilt on every push
    because it runs after `COPY . /app`.
14. CI flake: "database table is locked" in 4 of the last 8 failed test runs
    (background threads during test-DB creation). **LIVE, S.**
15. `deploy_smoke.sh`, `lighthouse.yml` and `accessibility.yml` audit **only
    dotbooks.store**. **CODE, S.**

### C. Correctness (code fixes)

16. `orders.expire_pending_orders` cancels **cash-on-delivery and manual orders
    after 60 min** — COD is Irving's only method. **CODE, high, S.**
17. GraphQL mutations for inventory, orders and book_product refuse every core
    API key — fix is in the working tree (v0.87.1, W0). **CODE.** Bare `is_staff`
    gates in `crm/graphql` (leads, customer timeline with PII, tasks),
    `agent_core/graphql` (runs and steps with full tool arguments) and payments
    let **any MCP token through regardless of its GraphQL scopes**; the
    session-staff short-circuit in `mutation_scope_error` returns before the
    RBAC-aware `check()`, so a role that lost `catalog.write` keeps GraphQL writes
    once `rbac` enforces; an explicitly empty GraphQL scope list is projected as
    `['*']` (latent). **CODE, medium/low, S.**
18. Affiliates: three settings keys nobody reads (the panel says programs
    inherit them — false); the **minimum payout is not enforced on the server**
    (`request_affiliate_payout` checks only `pending > 0`); the referral cookie is
    hardcoded to 30 days while programs advertise 1–365; the settings-key guard
    passes only because `marketplace` uses the same key names. **CODE, low, S.**
19. Linda automations have **no overlap guard**: a 60-second job with 240-second
    turns on a 4-slot worker fills every slot and shares one Janus session.
    **CODE (inferred), medium, S.**
20. Three default models are unpriced (`openrouter anthropic/claude-3.5-sonnet` —
    dots vs dashes in `_match`; `hermes`; `moonshot kimi-latest`) and the Janus
    custom model is free text, so the spend cap is blind to them and the picker
    silently omits them. **CODE, S.**
21. `error-capture.js` reports the browser's `ViewTransition` abort
    (`InvalidStateError`) as an error — the top "error" on three stores. **LIVE, S.**
22. Irving theme: pre-launch (noindex) product pages rendered **Add to cart**
    and the sticky bar (`{% if product.noindex %}` on a GraphQL dict that never
    carries `noindex`). Fixed on `main` at 00:45 today (`ceec1bfc`, `52c82511`
    — merged without a version bump; v0.87.1 carries them); product cards
    built from GraphQL dicts still keep their button. Checkout defaults the
    country to `US`, no `UK → GB` normalisation, US labels. Bookstore copy
    leaks into `/membership/` (`subscriptions/.../membership.html:7`) and the
    `gdpr` seed pages. **LIVE, low, S.**
23. `agent_mcp.views._audit_call` stores `output` as a **string**, and Activity
    flags a failure only for a dict with `error` — so failed Linda/MCP calls show
    green (dotbooks: 11 shown failed, 23 real). **LIVE, low, S.**
24. `AgentAuthMiddleware` leaves `request.user` anonymous for API keys, so
    `invokeAgent` and the REST invoke endpoint refuse even `admin` keys — may be
    deliberate; the docstring only discusses MCP tokens. **CODE, owner call.**

### D. Observability and compliance completeness

25. **Janus turns create no `AgentRun`**, and everything that reports reads
    `AgentRun`: Observability is empty on Irving (0 runs vs 42 Linda replies and
    5.96 M prompt tokens in 7 days); Activity shows Linda's tool calls but not her
    turns, failures or the **83 refused writes**; the AI-Act export omits the
    consent trail (`assistant.tool_write`, `mcp.tool_denied`); and **no decision
    row anywhere carries a model or provider** (0 of 4,938 on dotbooks — Worker
    rows included). Linda's tokens do reach the spend cap and Settings → AI.
    **LIVE, medium, M.**
26. Linda cannot create, pause or run Automations from chat (no `automations.*`
    tools); schedules are interval or daily-time only (no 5-field cron). **CODE, M.**

### E. Debt and ratchets

27. Plugin boundary: 116 pairs on `main` (113 in the working tree); 29 are
    repayable with one-line `requires` declarations (mind `_topo_sort` and
    first-registrant-wins URL mounting); shell → optional-app imports remain
    (admin_dashboard → cloudflare 7 sites, cms 8, marketing 5, product_videos 4,
    metafields 3; storefront → book_product 10, cms 7, metafields 6);
    `demo_data` is an unregistered app holding 6 pairs. **CODE.**
28. Tailwind Play CDN in `admin_dashboard/base.html:27`, `media/picker.html:6`
    and `storefront/base.html:19`; `test_csp_richtext.py:22` pins
    `'unsafe-eval'`; the deploy has no Node, so compiled CSS must be committed. **CODE, M.**
29. `JANUS_KNOWN_GOOD` has no tag; a history rewrite of Janus-Agent would leave
    the build fallback on an unreachable commit (build fails, stores keep running). **LIVE, low, S.**

### F. Plugin layer (112 app directories, 108 in the default list) — CODE

Measured with one script over `plugins/installed/` (non-test Python lines,
tests, migrations, contributions, manifest descriptions).

- **Scale.** 150,751 non-test Python lines in the apps; 3,035 `def test_` in
  458 test files (plus 952 in `core/`). The weight sits in seo (15.5 k lines,
  353 tests), booking_marketplace (15.1 k, opt-in), admin_dashboard (10 k),
  catalog and storefront (5.7 k each), ai_assistant and agent_core (4.5 k),
  affiliates and orders (4.3 k).
- **Zero tests (7):** consent, linda_generated, localization, marketing,
  product_videos, **rbac**, store_bootstrap — rbac answers every capability
  check, consent gates every tracker. **Nineteen more** have only module-level
  pytest functions in `tests/__init__.py` (25 tests in all) that only CI's
  separate pytest step runs: journal, post_checkout_upsell, brand_kit,
  referrals, drops, motion, checkout_experience, returns_portal, one_click,
  media_3d, ai_stylist, ugc_reviews, save_for_later, lookbook, immersive_pdp,
  rich_post_purchase, discovery_quiz, smart_shipping, rails.
- **Twenty default apps are under 150 lines** and most describe a large
  feature: smart_shipping (110: "EasyPost/Shippo live rates" — the live-rate
  code lives in `shipping/services.py`; this app contributes one block and a
  "lowest carbon badge" setting), rich_post_purchase (67: "email + SMS +
  WhatsApp + PWA push" — a channel enum and a model, no SMS or WhatsApp
  adapter), checkout_experience (99: "one-page + express-pay checkout" — two
  storefront blocks and a settings panel; the wallets come from Stripe's
  Payment Element in `payments`), one_click (95), immersive_pdp (97), media_3d
  (142), ugc_reviews (115: "creator program"), drops (103), referrals (136),
  save_for_later (104), rails (114), lookbook (141), journal (139), ai_stylist
  (127), lumina (117), motion (85), product_gallery (76), post_checkout_upsell
  (141), discovery_quiz (152), linda_generated (86, a landing zone by design).
  The Apps catalogue is merchant-facing; a manifest that promises more than the
  code delivers is the settings-with-no-reader landmine at app scale.
- **Overlapping concepts** (merge, or describe honestly): reviews /
  ugc_reviews / trust_signals (and catalog's manifest still says "and
  reviews"); marketing (291 lines, 0 tests: "coupons, discount engine, email
  campaigns, abandoned-cart recovery" — holds a `Coupon` and a `Redirect` model)
  vs promotions (rule engine, types `catalog` / `order`) vs cart_abandonment vs
  newsletter; post_purchase / rich_post_purchase / post_checkout_upsell;
  shipping / smart_shipping; checkout_experience / one_click / the storefront
  checkout; personalisation / dynamics / rails / discovery_quiz (four
  recommendation surfaces); product_gallery / immersive_pdp / product_stories /
  product_videos / media_3d / lookbook (six PDP add-ons); referrals / affiliates /
  loyalty_points (three reward ledgers); seven AI apps (ai_assistant,
  ai_content, ai_stylist, agent_core, morpheus_brain, janus, linda_generated);
  tracking / analytics / feature_adoption / experiments; observability /
  feedback / notifications_center; journal / cms / richtext; localization /
  `core.i18n`; and the book vertical in the default list (book_product,
  audiobooks, bookvault, bookstore_3d, lumina, flipbook, eco_impact) on every
  store that does not set `MORPHEUS_DISABLED_APPS`.
- **Dead or unplaced:** demo_data (1.8 k lines, not registered, 6 boundary
  pairs); environments ("dev/staging/production with snapshots and promotion",
  408 lines, 3 tests, used by nothing in the deploy story).
- **Otherwise sound:** every app with models has migrations and a
  `migrations/__init__.py`; TODO/FIXME is near zero; only storefront declares
  settings keys without a panel or page (8, read by its views).
- **Oversized files:** `booking_marketplace/management/commands/_experiences_data.py`
  (5,289 lines of seed data) and `seed_places.py` (1,902), `seo/views.py`
  (1,886), `storefront/views/catalog.py` (1,721),
  `admin_dashboard/views_split/settings.py` (1,368), `seo/templatetags/seo.py`
  (1,217). Nothing in `core/` exceeds 1,200.
- `scripts/plugin_standard_baseline.json` records 43 contract violations
  (tests.missing 26, structure.apps 8, models.has_models_flag 7,
  settings.not_registered 2) and `check_plugin_standard.py` **runs nowhere** —
  its docstring says CI.

### G. Commerce engine depth — CODE

| Area | Implemented | Partial / thin | Missing |
|---|---|---|---|
| Catalog | products, variants, attributes, categories, collections, metafields, digital products, audiobooks, the book vertical, lookbook bundles, importers (Shopify, WooCommerce, Magento, BigCommerce, … — 2 tests), WebP/AVIF variants | product types are flags, not a type system; `localized_prices` JSON on Product | bundles as a product type; price history; GPSR data |
| Pricing & promotions | promotions engine (predicates, `catalog`/`order` types, usage limits, scheduling), coupons in `marketing`, B2B price lists + quotes + net terms (893 lines, **2 tests**), gift cards, loyalty, store credit, membership discount, one price seam (`core/pricing.py`) | two coupon systems (`marketing.Coupon` vs promotions); BOGO/tiered/automatic only as predicates | 30-day prior-price evidence |
| Markets & currency | `markets` (per-country price, currency, locale), `ExchangeRate` rows, a convert tag | no rate source feeds `ExchangeRate`; no Market/StoreChannel rows on any live store | automatic FX, tax-inclusive display per market |
| Tax | TaxCategory / TaxRegion / TaxRate, provider `local` or `stripe`, `prices_include_tax`, EU OSS categories | no store has a region or rate configured | US sales-tax provider, VIES VAT-ID check, reverse charge |
| Shipping | zones + rates: flat, weight tier, order-total tier, free-over, **live Shippo and EasyPost quotes** (`shipping/services.py:_carrier_quote`), Bookvault POD; free-shipping progress tag | `smart_shipping` is a badge; three themes hardcode free-shipping copy | labels, pickup, delivery-date promise, Merchant Center handling/transit days |
| Checkout | Stripe Payment Element with `automatic_payment_methods` (cards, Apple Pay, Google Pay, Link, Klarna when enabled at Stripe), Apple Pay domain file, PayPal, COD, bank/manual, sandbox; guest checkout; SetupIntent for saved cards | 3DS cannot be driven by an agent (noted in code); `checkout_experience` only adds blocks; no address autocomplete; element count never measured | customer passkeys; express buttons above the form; order editing |
| Payments ops | one refund service with locks + idempotency keys; webhook idempotency; fraud rules over Radar | **the base `capture()` returns `{'success': True}` without capturing** (`payments/gateway.py:59-61`) — a delayed-capture gateway would mark unpaid money captured | multi-capture, BNPL beyond Stripe's |
| Inventory | warehouses, stock levels, movements, atomic reservations, low-stock alerts, back-in-stock subscriptions, reorder points, predictive stockout | | backorder/pre-order policy, transfers, serial/lot |
| Orders & fulfilment | FSM (pending → processing → partially_fulfilled → fulfilled/shipped → delivered, cancelled, refunded), partial fulfilment, HTML invoice page, returns (canonical flow + `returns_portal`), draft orders/quotes, tracking → post-purchase chain | invoices are HTML; exchanges = return + new order | order editing, packing slips, PDF documents |
| Customers | allauth accounts, addresses, `CustomerSegment`, wishlist, save-for-later, consent, GDPR export/erase | customer MFA none; OIDC/SAML staff-only | passkeys |
| Subscriptions | plans, Stripe Billing adapter, dunning + pre-renewal mail, pause/resume, memberships with evidence-based entitlement | | |
| Marketplace | vendors, vendor orders, payouts; affiliates (links, attribution, tiers, payouts); booking marketplace (opt-in) | affiliate payout threshold not enforced | |
| Notifications | 7 transactional emails (placed, paid, fulfilled, cancelled, refund, download, welcome) + subscription and cart-recovery mail; PWA push (VAPID) | SMS / WhatsApp exist only as enum values | SMS provider; per-customer notification preferences |
| Search | DB search with an optional Typesense backend; embeddings + semantic search in `ai_assistant` | no `/search/suggest` (planned in competitive-edge, never built) | typo-tolerant suggest, merchandising rules |
| Content | CMS pages/blocks/menus/forms, journal block editor, Lexical rich text, media library, web stories, flipbook, 3D bookstore | three themes inline 1,072–1,347 lines of CSS in `base.html` | a Horizon-class theme editor |
| APIs | REST (11 routes in `api/urls.py` + per-app), GraphQL (50 mutations, ~176 typed fields), 4 MCP servers, ACP, UCP, agent tools, webhooks UI | no OpenAPI schema or client SDK | |
| Platform | staff TOTP + SSO, RBAC (log mode), rate limiting, enforced dashboard CSP, request ids, OTel traces (off by default), Sentry (off), error capture + digest + health checks, PWA, GA4 + Measurement Protocol, Meta CAPI, feeds for Google/Meta/TikTok/Pinterest/Snapchat/Microsoft | `/healthz/deep` is unauthenticated and echoes exception text; `api/llm_tasks.py:76,128` and `agent_core/views.py:82,134` are `@csrf_exempt` yet accept a staff session; `CORS_ALLOW_CREDENTIALS=True`; `SESSION_COOKIE_SAMESITE` unset; the agent code sandbox is a thread with a denylist, not isolation (its docstring says so); `smtp_password` in plaintext | metrics export |

What a real store hits first: (1) the capture no-op, (2) no price-history or
shipping-promise truth, (3) checkout length and express-button placement, (4)
PDF invoices and packing slips, (5) `/search/suggest`, (6) passkeys, (7) an FX
rate source, (8) a US tax provider, (9) order editing, (10) an SMS provider.

### H. Quality infrastructure — CODE

- **CI** (`ci.yml`): lint (ruff 0.15.8 check + format, bandit `-ll`, both
  boundary checks, **`mypy core || true`** — the only soft-fail), audit
  (pip-audit on `requirements.txt`), migrations on Postgres 16, test (SQLite +
  Redis, serial: `release --check`, `check --deploy`, `makemigrations --check`,
  the disable-guard suite, pytest smoke, coverage `--fail-under=40`),
  api-stability (254 SDK symbols). `cd.yml` builds the GHCR image *after* CI,
  but Coolify deploys on the push. Live audits cover dotbooks only. pre-commit
  pins ruff 0.7.4 against CI's 0.15.8.
- **Tests**: 585 files / 4,096 `def test_`. Three "postgres-only" tests
  (`demo_data/test_seed.py:55`, `orders/tests/test_checkout.py:212`,
  `dynamics/test_dynamic_products.py:120`) **never run anywhere** — CI tests on
  SQLite only. The tracked root `_test_settings_tmp.py` still excludes "11
  sibling plugins" as broken.
- **Dependencies**: `requirements.txt` is all `>=` floors and the lock resolves
  to those floors — Django **6.1.1**, DRF 3.18.1, strawberry 0.327.7 /
  strawberry-django 0.89.2, celery 5.6.3, redis 8.1 / django-redis 7.0, stripe
  15.6.1, allauth 65.19.4, psycopg2-binary 2.9.13 (no psycopg 3), pillow
  12.3.0, django-money 3.6.1, django-fsm ≥ 3.0.1 (upstream archived; check its
  Django 6 story), openai 3.17 / anthropic 1.7, sentry-sdk 2.70, OpenTelemetry
  1.44. Dockerfile: `python:3.12-slim`, installs the floors, then
  **`pip install gunicorn==23.0.0`** against a `gunicorn>=26.2.0` requirement.
- **Frontend**: dashboard = Tailwind Play CDN + Remix Icon (jsDelivr, behind a
  `lucide` shim) + Inter (jsDelivr) + htmx 2.0.10 (unpkg) + a self-hosted
  Lexical bundle (the only `package.json`); the storefront fallback base also
  loads the Play CDN; montenegro ships precompiled Tailwind; `static/<theme>/style.css`
  in irving_survival and supernatural_shop is unreferenced. External origins:
  fonts.googleapis/gstatic, js.stripe.com, maps.googleapis.com,
  cdn.ampproject.org, unpkg.com (htmx, Leaflet), cdn.jsdelivr.net (Remix,
  Inter, page-flip), cdnjs (pdf.js), cdn.tailwindcss.com — **no SRI on any CDN
  tag**. The storefront CSP has been "report-only for ~2 weeks" since it was
  written; `security_headers.py`'s docstring ("no CDNs, no unsafe-eval") is
  stale.
- **self_improvement**: seven collectors (error_log, csp, cart_abandon,
  zero_search, seo_gap, upstream_drift — always zero in containers,
  code_quality), nightly recommend → adversarial verify → policy, four healers,
  weekly digest, 102 tests. Its beat entries are registered through
  `app.conf.beat_schedule` inside `try/except: pass` (`morph/celery.py:94-96`)
  — the mechanism that silently dropped core's jobs until v0.75.27 — and
  `test_beat_schedule.py` does not assert them. **Verify on a live worker
  before trusting any SI output.**
- **Observability**: request ids, JSON logs, OTel traces (off unless an
  endpoint is set), Sentry (off), ErrorEvent capture + nightly health + digest,
  `/healthz`, `/readyz`, `/healthz/deep`. No metrics exporter.
- **Docs drift**: README says 111 apps / 3,696 tests / 184 tools; CLAUDE.md
  says 122 pairs and 30 apps; the root `ARCHITECTURE.md` (2026-05-21, "61
  plugins") duplicates `docs/ARCHITECTURE.md`; `UPDATING.md` claims verification
  at v0.42/v0.44; `API_STABILITY.md`'s breaking-changes table stops at v0.80.0
  while `MIGRATING.md` has v0.81.0; `CHANGELOG.md` stops at v0.2.x; about 15
  plan files carry status lines the code contradicts (acp "draft",
  multi-storefront "not started", linda-selfdev dashboards removed in v0.65 …).
  ADRs: 38 in `.torsor/architecture/decisions/`, newest 0038 (BSL 1.1).
- **Security scan**: 57 `mark_safe` sites (seo templatetags 27), 59 `|safe`,
  no `autoescape off`, no raw-SQL f-strings, no `verify=False`, `DEBUG`
  defaults off, `ALLOWED_HOSTS` fails closed; 22 `@csrf_exempt` sites (two
  accept a staff session, see G); tracked clutter (`_test_settings_tmp.py`,
  `openai_tools_output.json`, five `dash-*.png`).
- **Still open from earlier plans, re-confirmed**: the GraphQL response-cache
  key is blind to market/currency/language/channel and invalidation covers
  only product/category writes (`mcp-graphql-hardening`); the approval-audit
  row in `core/assistant/tools/ecommerce_writes.py:113` is never written
  (`agent-authorization`); P8 edition gating is absent and the open-core plan's
  "Apache-2.0 community edition" contradicts ADR 0038.

---

## 4. The plan — ranked workstreams

Each item is one release (`PATCH` for fixes, `MINOR` for features). "Verify"
is what must be true on production before the next item starts.

### W0 — Ship the working tree (today) — SHIPPED v0.87.1 (779264da)

- v0.87.1: one `mutation_scope_error` for catalog, inventory, orders,
  book_product (`api/graphql_permissions.py`, `api/tests_mutation_scope.py`,
  baseline 116 → 113, CLAUDE.md). Live-verified on Irving with probe API keys
  (right scope reaches the mutation, wrong scope is refused); all four stores
  on v0.87.1; CI green.
- Verify: `api.tests_mutation_scope` + `catalog.tests.test_graphql_mutation_auth`
  + `orders.tests.test_graphql_cart_ownership` in one process; `ruff`;
  `release --check`; `/readyz` reports v0.87.1 on all four.

### W1 — Stop the bleeding (1–2 days, all S)

**Status 2026-10-10:** items 1–6, 8, 9, 11, 12 and 14 shipped as v0.87.2
(plus the Linda automation run lock, the 15-minute floor and the unpriced-model
refusal in the Janus form). Open: 7 (the remaining theme bits), 10, 13, and
every infra and owner item below.

Code, one release each or batched as one PATCH:

1. `orders/tasks.py`: exclude offline gateways (`cod`, `manual`) from
   `expire_pending_orders`, or give them their own window; test in
   `test_expire_pending.py`. (Finding 16)
2. `core/static/core/error-capture.js` + `/api/errors/client/`: drop
   `InvalidStateError` / "Transition was aborted" rejections; test that a real
   error still lands. (21)
3. `agent_mcp/views._audit_call`: store `{'error': …}` as a dict; Activity treats
   it as failed; test with an MCP-shaped row. (23)
4. `agent_core/scheduler.fire`: `cache.add` lock per automation for the task's
   time limit, a 15-minute minimum for the Linda engine, own Celery queue. (19)
5. `core/agents/pricing`: price the three default models, normalise `.`→`-` and
   strip `org/` in `_match`; refuse (or warn loudly on) an unpriced custom model
   in Settings → AI → Janus. (20)
6. GraphQL gates: `crm`, `agent_core`, `payments` through `has_scope` with new
   `crm.read` / `crm.write` / `agents.read` in `AVAILABLE_SCOPES` and
   `_CAPABILITY_FOR_SCOPE`; session staff through `has_scope` (mode-aware);
   project an empty scope list as `[]`. (17)
7. Irving theme: the PDP and sticky-bar fix is merged (`ceec1bfc`); still to
   do: cards built from GraphQL dicts, default country from
   `StoreSettings.country`, map `UK → GB` (reuse tax `_norm_country`), UK
   labels; neutral membership and `gdpr` seed copy. Theme code bumps (ADR 0033). (22)
8. `scripts/deploy_smoke.sh` loops over all four hosts and requires the pushed
   `MORPHEUS_VERSION` from each `/readyz`. (15)
9. CI flake: under `settings._RUNNING_TESTS` run the side-effect threads inline
   (at least the IndexNow ping); confirm with several serial runs. (14)
10. Affiliates: enforce the minimum payout inside `request_affiliate_payout`;
    cookie `max_age` from `program.cookie_window_days`; delete the three dead
    keys (owner chose removal in v0.76.4) and fix the panel text; make the
    settings-key guard count readers in the declaring app only. (18)
11. `payments/gateway.py` base `capture()` returns `{'success': False,
    'error': 'capture not supported'}`; a test that no gateway without capture
    can mark an order captured. (G)
12. `/healthz/deep` behind staff or a token, exception text replaced by a
    check name. (G, H)
13. The two `@csrf_exempt` views that accept a staff session
    (`api/llm_tasks.py`, `agent_core/views.py`) require a Bearer token for
    that path or drop the exemption; set `SESSION_COOKIE_SAMESITE='Lax'`
    explicitly. (H)
14. Move the self_improvement beat entries into `settings.CELERY_BEAT_SCHEDULE`
    and assert them in `test_beat_schedule.py`; confirm with `celery inspect`
    on a live worker. (H)

Infra (my access, owner's OK per change): Cloudflare supernatural HSTS one year
+ SSL strict (9); Coolify "Build Variable" off for every secret, then rotate
`SECRET_KEY` after the next prune (7); `docker builder prune -af` and an image
prune, alert threshold 85 % (5); branch protection with required checks or
Coolify deploy from the CI-built image (8).

Owner: DeepSeek top-up or provider switch / `fallback_providers` (1); spend and
run caps (3); Irving SMTP via the relay (10); `sutekh` investigation before
payment keys (6); a bucket for off-host backups (4).

### W2 — Supply chain and build (2–3 days, M)

- Regenerate `requirements.lock.txt` (`uv pip compile --generate-hashes
  --universal`), get CI green, **build the image from the lock**
  (`--require-hashes`), close Dependabot #96, enable Dependabot alerts and
  security updates, add a weekly `pip-audit` job that also audits the Janus venv. (11, 12)
- Janus: tag `eafb7aba` (`morpheus-known-good`), pin `JANUS_REF` to a reviewed
  SHA in the Coolify build args, bump its pins (PyJWT ≥ 2.15, pillow ≥ 12.3,
  starlette ≥ 1.3.1, mcp ≥ 1.28.1) in `janus_runtime.PINS` and the Dockerfile,
  move the Janus install before `COPY . /app` (copy `janus_contract.py` first). (13, 29)
- Drop the Dockerfile's `pip install gunicorn==23.0.0` (the lock has ≥ 26.2);
  wire `check_plugin_standard.py` into CI with its 43-item baseline as a
  ratchet; run the three postgres-only tests in the `migrations` job.
- GraphQL response cache: put market, currency, language and channel into the
  cache key and invalidate on the writes that change them
  (`mcp-graphql-hardening` deferred item).
- Verify: `pip freeze` in a fresh container equals the lock; `docker history`
  shows no secrets; image size and build time drop.

### W3 — Make Linda's work visible (3–5 days, M)

One source of truth for a Janus turn. Recommendation: write a lightweight
`AgentRun` (`agent='linda'`, provider, model, tokens from `state.db`,
`tool_call_count`, error) at the end of every turn in `core/assistant/runtime.py`,
and put the resolved provider/model into the turn token so
`agent_mcp.views._audit_call` records them on each decision row. Everything that
already reads `AgentRun` (Observability, run caps, AI-Act export) then sees her
without a second code path.

- Observability: Linda rows (turns, tokens, cost via `estimate_cost`, failures,
  refusals from `mcp.tool_denied`). Activity: per-turn rows + refusals. AI-Act
  export: a `consents` section (`assistant.tool_write`, `mcp.tool_denied`), the
  consenting message id and timestamp recorded when `consent.consume` succeeds. (25)
- `automations.list/create/pause/resume/run_now/delete` agent tools in
  `agent_core/agent_tools.py` (`requires_approval=True`, inside an existing scope,
  refused inside `:auto:` conversations); 5-field cron via a small parser
  (check `croniter` is not already a dependency first); automation chats
  read-only on the chat page. (26)
- Update `docs/plans/linda-sessions-automations-models-2026-10.md` status.

### W4 — Agent-ready for 2026 (1–2 weeks, L) — the market bet

Ordered by cost-to-value; a–c are feeds and manifests, cheap and immediately
visible to agents.

- **4a UCP manifest to spec.** Serve `/.well-known/ucp` (keep `ucp.json` as an
  alias): `ucp.version: 2026-08-25`, `services` (`mcp` → the cart/checkout
  clusters; `rest` → the ACP-shaped checkout), `capabilities` for
  `dev.ucp.shopping.checkout` / `.cart` / `.order` computed from live tools,
  `payment_handlers` (Stripe when configured), `keys` (JWKS for signed
  webhooks). Fixture-test the manifest against the spec's JSON schema
  (download once into the test tree, Verified-Output rule).
- **4b ACP feed to the 2026-04-17 `Variant` schema** (`url`, `price {amount in
  minor units, currency}`, `availability {available, status}`, `media[]`,
  `seller {name, links}`, `variant_options[]`, `barcodes[]`, `list_price`), keep
  the old shape behind `?v=2025-09-29` for a release.
- **4c OpenAI merchant feed** as a channel app (`openai_shopping`, the
  `google_shopping` / `channels` pattern on `plugins/feed_mapping.py`): JSONL
  export with `item_id`, `url`, `image_url`, `seller_name`, `is_eligible_search`,
  `is_eligible_checkout` (+ `seller_privacy_policy`, `seller_tos`), `group_id` +
  `variant_dict`, `accepts_returns` / `return_deadline_in_days` /
  `return_policy`; a scheduled push when the owner has endpoint credentials;
  a Channels tab with coverage counts. Perplexity's merchant program takes the
  same data.
- **4d MCP server to 2026-07-28** with backward compatibility: honour `_meta`
  protocol version and client capabilities, implement `server/discover`,
  `resultType: "complete"` on every result, `ttlMs` + `cacheScope` on list
  results, deterministic tool order, `Mcp-Method` / `Mcp-Name` headers, drop the
  minted session for new clients, keep the `initialize` path for
  2024-11-05 … 2025-11-25 clients through the deprecation window; renumber error
  codes. Contract tests per version; update `docs/AGENT_PROTOCOLS.md` and
  `docs/MCP_SERVER.md`.
- **4e WebMCP.** A storefront contribution (`global_head` block + template tag)
  that annotates the search, add-to-cart, newsletter and checkout-address forms
  declaratively, and registers three imperative tools (`search_products`,
  `add_to_cart`, `get_cart`) backed by `/mcp/cart/v1/`; a seo/agent setting
  switches it; Lighthouse's agentic category is the test (today "not
  applicable"; target: all four audits pass on all four stores).
- **4f Web Bot Auth at the origin.** Middleware that verifies RFC 9421
  `Signature-Input` / `Signature` against the agent's published JWKS
  (`Signature-Agent` directory) and sets `request.verified_agent`; honoured on
  MCP / ACP / UCP endpoints; agent id persisted on the order as `agent.json`
  already promises; the Cloudflare header path stays. Needs an Ed25519 verify —
  `cryptography` is already a dependency; confirm before adding anything.
- **4g AP2 / Visa / Mastercard**: nothing to build until a PSP account exists
  (Release 3). **4h** Cloudflare: keep `ai_bots_protection` disabled on purpose and
  write it into `OPERATIONS_RUNBOOK.md`.

### W5 — Compliance pack (1–2 weeks, M per item)

- **5a GPSR**: a `product_safety` app contributing a product-form card
  (`PRODUCT_FORM_CARDS`), a PDP block and feed attributes for manufacturer
  (name, postal + electronic address), EU responsible person, product
  identifiers, warnings and safety documents; renders only when filled.
- **5b Honest prices**: remove the hardcoded free-shipping lines from the
  `dot_books` and `montenegro` themes and render the promise from the shipping
  app only when a threshold is configured; add a `PriceHistory` row on every
  price change so a reduction can show the 30-day prior price (EU) and a "was"
  price has evidence (UK); the PDP/cart show the full price including unavoidable
  fees the first time a price appears.
- **5c Art. 50 marking**: every `ai_content` output (descriptions, images, alt
  text) carries `ai_generated=True` metadata, a machine-readable marker in the
  page (`data-ai-generated` + JSON-LD `creditText`/`creator` of type
  `SoftwareApplication`), a merchant setting for a visible label, and a line in
  the AI-Act export. The chatbot disclosure stays as is.
- **5d EAA / WCAG**: fix the measured failures (supernatural contrast and
  `<article>` role; montenegro `<select>` labels, heading order, pill contrast);
  run `accessibility.yml` against all four stores after deploy-smoke; a theme
  guard that every `<select>` has a label.
- **5e PCI DSS 4.0.1** (before card payments go live): a written script
  inventory for `/checkout/`, SRI on every CDN script there, CSP enforced (with
  nonces) on the checkout route first, a report endpoint; Stripe's iframe keeps
  card data out of scope.
- **5f Consent**: honour `Sec-GPC` as "reject non-essential", remember a refusal
  for six months, keep one-click reject (the banner already has Accept all /
  Reject all / Save).
- **5g Email**: the nightly health check resolves SPF/DKIM/DMARC for the sending
  domain and warns in the dashboard.

### W6 — Platform modernisation (ongoing, M–L)

- Morpheus already runs Django 6.1.1 on Python 3.12. Use what that gives:
  fetch modes on the PDP/listing hot paths (the N+1 class the storefront_blocks
  fix was about), template partials for the dashboard fragments, Django's
  `ContentSecurityPolicyMiddleware` with nonces as the replacement for the
  hand-rolled policy; keep Celery. Housekeeping: psycopg 3 instead of
  psycopg2-binary, confirm django-fsm's Django 6 support or move to its
  maintained fork, follow the monthly security releases through the lock +
  Dependabot.
- Tailwind precompiled and committed (dashboard, media picker, storefront
  base), CDN scripts dropped, `'unsafe-eval'` removed, then nonces for dashboard
  inline scripts; storefront CSP enforced after a report review. (28)
- OpenAPI schema for the REST surface and a published client — the real
  prerequisite for anything called an SDK (reconciliation item 6).
- Lock-based builds from W2 become the only build path.

### W7 — Plugin-layer hygiene (S–M each, one release per step)

1. **Truth in the Apps catalogue.** Rewrite the manifests of the twenty thin
   apps to say what each does today — or fold each into its owner: smart_shipping
   → shipping; checkout_experience + one_click → the storefront checkout;
   rich_post_purchase + post_checkout_upsell → post_purchase; ugc_reviews +
   trust_signals → reviews; rails + discovery_quiz → personalisation/dynamics;
   immersive_pdp + product_stories → product_gallery; `marketing.Coupon` →
   promotions. One merge per PR: model/FK moves with migrations, settings keys
   preserved, the disable suite green, a `MIGRATING.md` section and an
   `API_STABILITY.md` row each.
2. Tests for the seven zero-test apps (rbac and consent first); turn the
   nineteen `tests/__init__.py`-only apps into real test modules so
   `manage.py test` runs them.
3. `check_plugin_standard.py` in CI (W2) and its baseline shrinking.
4. Repay the 29 `requires` one-liners; contribute cloudflare's and seo's settings
   panels; decide demo_data and environments (owner).
5. **Docs truth pass**: counts point at the source of truth; status lines on
   the ~15 contradicted plan files; the `API_STABILITY.md` v0.81.0 row; delete
   the root `ARCHITECTURE.md` duplicate and `CHANGELOG.md` or make them true;
   remove the tracked clutter; fix `security_headers.py`'s docstring.
6. Theme CSS out of `base.html` into `static/<theme>/` (the unreferenced
   `style.css` files are the place), SRI on every CDN tag, the Play CDN out of
   the storefront fallback base.

### W8 — Commerce depth (M–L each)

1. Stripe `capture()` for delayed capture, after W1 item 11 makes the base
   honest.
2. Checkout: count form elements per theme against the 12–14 benchmark and cut;
   express buttons above the form (Stripe's Express Checkout Element is already
   enabled by `automatic_payment_methods`); address autocomplete behind a
   setting (the Places key the booking app uses); **customer passkeys** via
   allauth `mfa` (`webauthn` in `MFA_SUPPORTED_TYPES`, `MFA_PASSKEY_LOGIN_ENABLED`)
   with a store toggle and the staff MFA gate untouched.
3. `PriceHistory` + shipping promise from W5b; GPSR from W5a.
4. Invoices and packing slips: print CSS first, PDF later (a native dependency
   means a deploy window).
5. `/search/suggest`: trigram prefix search, Typesense when configured,
   semantic fallback on zero results.
6. FX: a daily `ExchangeRate` refresh from the ECB when a market uses another
   currency.
7. Order editing before fulfilment (lines, re-price, re-authorise).
8. SMS adapter (Twilio) for the existing channel enum, or remove the enum.
9. Later, only when a store needs them: US sales-tax provider, VIES VAT-ID
   check, backorder policy, transfers.

### W9 — Irving launch (owner + code)

Owner: Stripe account and keys, GB shipping zone and rates, VAT decision, legal
entity on terms/privacy/imprint, catalogue (images, copy, which products leave
`noindex`), **GBP** + `country=GB` + `Europe/London`, SMTP, apex domain cutover
with a 301 map for the 116 old URLs, logo, Site domain, GA4; then flip
`seo.hide_until_launch` and `orders.prelaunch_noindex_not_for_sale` and fix the
FAQ. Code: W1 item 7, 5b (shipping promise), staff-picks/empty-shelf hiding.

### W10 — Distribution and open core (owner decision)

Host the signed update manifest, decide repo visibility and a CLA
(reconciliation items 3 and "what is missing"). Only worth starting if the
README's goal of bringing in contacts is still the goal.

### Sequence

W0 → W1 → W2 → W3 → W4a–c → W5b, 5d, 5a → W7.1–2 → W4d–f → W5c, 5e–g → W8 →
W6, with the remaining W7 items as fillers between the larger pieces. Every
merge bumps the version; no two large pieces in flight at once.

---

## 5. Decisions needed from the owner

1. AI provider money: top up DeepSeek on three stores, or switch providers and
   set `fallback_providers`.
2. Daily spend cap and run cap per store.
3. Stripe (and/or PayPal) credentials per selling store; shipping rates; the 18
   $0 products on supernatural.
4. Deploy gate: CI-built image via the Coolify API, or branch protection plus
   auto-deploy off.
5. Coolify build-variable flags off and a `SECRET_KEY` rotation window.
6. Off-host backup target (R2/B2 bucket) and budget.
7. The `sutekh-watchdog` cron: who installed it, keep or remove after
   investigation.
8. `demo_data`: opt-in app or move out of `plugins/installed/`.
9. API keys invoking merchant agents: document as unsupported, or accept keys
   whose scopes cover the agent's.
10. Irving: currency, VAT registration, legal entity, launch date, apex cutover.
11. Distribution/open-core: pursue or park.

## 6. Deliberately not in this plan

ACP Instant Checkout integration (retired); AP2/Visa/Mastercard mandates until a
PSP account exists; POS and multi-tenant; SCIM; extending `llms.txt`; Python 3.14
free-threading; migrating Celery to Django Tasks; the five-engineer enterprise
roadmaps in `docs/analysis/`.

## 7. Sources

Agentic commerce: [ACP explained](https://eco.com/support/en/articles/14845478-acp-agentic-commerce-protocol-explained) · [Instant Checkout retirement / ACP state](https://agenticplug.ai/current-state-of-agentic-commerce) · [OpenAI commerce key concepts](https://developers.openai.com/commerce/guides/key-concepts) · [OpenAI product feed spec](https://developers.openai.com/commerce/specs/feed) · [ACP 2026-04-17 feed OpenAPI](https://github.com/agentic-commerce-protocol/agentic-commerce-protocol/blob/main/spec/2026-04-17/openapi/openapi.feed.yaml) · [UCP spec overview](https://ucp.dev/latest/specification/overview/) · [UCP launch](https://askbosco.io/blog/shopify/google-launches-the-universal-commerce-protocol-ucp-in-the-us/) · [Shopify Spring '26 dev edition](https://www.shopify.com/news/spring-26-edition-dev) · [AP2 explained](https://eco.com/support/en/articles/15192002-ap2-protocol-explained-google-s-agentic-commerce-standard-2026) · [Agentic payments, June 2026](https://universalcommerceprotocol.blog/en/agentic-payments-june-2026/) · [Web Bot Auth](https://stellagent.ai/insights/web-bot-auth-cloudflare-ietf) · [cloudflare/web-bot-auth](https://github.com/cloudflare/web-bot-auth) · [MCP 2026-07-28 changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog) · [WebMCP (Chrome)](https://developer.chrome.com/docs/ai/webmcp) · [Chrome 149 origin trial](https://ppc.land/chrome-149-origin-trial-puts-webmcp-in-developers-hands-at-last/) · [Perplexity merchant program](https://alhena.ai/blog/perplexity-shopping-merchants-setup-guide/) · [AI traffic conversion](https://www.digitalcommerce360.com/2026/04/23/ecommerce-trends-ais-key-conversion-metric-is-improving/) · [Stripe Sessions 2026](https://stripe.com/blog/everything-we-announced-at-sessions-2026) · [Cloudflare default AI-crawler blocking](https://chudi.dev/blog/cloudflare-block-ai-crawlers-september-15).

Regulation: [AI Act Art. 50 live](https://www.bakerbotts.com/thought-leadership/publications/2026/september/eu-ai-act-article-50-transparency-obligations-go-live) · [AI Omnibus in force](https://natlawreview.com/article/eu-digital-omnibus-ai-enters-force) · [FPF AI Act timeline](https://fpf.org/wp-content/uploads/2026/07/FPF-EU-AI-Act-Timeline-2026-R2.pdf) · [Digital Omnibus status](https://acompli.ie/news/digital-omnibus-gdpr-cookies-status-september-2026/) · [EAA](https://kinsta.com/blog/european-accessibility-act/) · [GPSR Art. 19](https://www.vimm.be/en/blog/gpsr-article-19-product-information-webshop) · [DMCC drip pricing](https://www.hsfkramer.com/notes/crt/2026-07/cma-launches-three-further-drip-pricing-investigations-under-the-dmcc-act-consumer-protection-regime) · [DMCC first year](https://www.ashurstperkinscoie.com/en/insights/lessons-from-the-first-year-of-the-new-consumer-enforcement-regime/) · [PCI DSS 4.0.1 6.4.3/11.6.1](https://blog.report-uri.com/pci-dss-4-0-1-and-requirements-6-4-3-and-11-6-1-what-changed-for-payment-page-scripts/) · [Bulk sender requirements 2026](https://generate.folderly.com/blog/gmail-yahoo-outlook-sender-requirements-2026).

Stack and search: [Django 6.1 released](https://www.djangoproject.com/weblog/2026/aug/05/django-61-released/) · [Django 6.0 release notes](https://docs.djangoproject.com/en/6.0/releases/6.0/) · [Django security archive](https://docs.djangoproject.com/en/dev/releases/security/) · [State of Python 2026](https://devnewsletter.com/p/state-of-python-2026/) · [Django task queues 2026](https://levelup.gitconnected.com/which-background-task-queue-should-you-actually-use-with-django-in-2026-aa109f4aa9ab) · [Tailwind Play CDN](https://github.com/tailwindlabs/tailwindcss/discussions/15479) · [Medusa/Saleor/Vendure 2026](https://focusreactive.com/best-nextjs-headless-ecommerce-platforms/) · [Shopify Summer '26](https://www.adsx.com/blog/shopify-summer-26-edition-horizons) · [AI Overviews on shopping queries](https://almcorp.com/blog/google-ai-overviews-shopping-queries/) · [Merchant listing structured data 2026](https://dev.to/mr_manushukla/product-schema-in-2026-9-fixes-that-decide-if-your-merchant-listings-show-16cm) · [Google category codes, July 2026](https://ppc.land/google-adds-category-codes-to-merchant-listings-on-july-7/) · [llms.txt zero requests](https://ppc.land/llms-txt-adoption-rises-8-8x-but-97-of-files-get-zero-ai-requests/) · [Core Web Vitals 2026](https://seojuice.com/blog/core-web-vitals-2026-audit-changes/) · [Cart abandonment 2026](https://readycloud.com/info/cart-abandonment-rates-2026-numbers-reasons-what-ecommerce-brands-should-do-next) · [Passkeys by industry](https://mojoauth.com/blog/passkey-adoption-rates-by-industry) · [allauth WebAuthn](https://django-allauth.readthedocs.io/en/stable/mfa/webauthn.html) · [OWASP LLM Top 10 2025](https://www.invicti.com/blog/web-security/owasp-top-10-risks-llm-security-2025) · [OWASP agentic threats](https://www.aigl.blog/content/files/2025/04/Agentic-AI---Threats-and-Mitigations.pdf).
