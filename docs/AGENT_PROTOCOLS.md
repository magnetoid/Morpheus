# Agent protocols — integration guide

Morpheus speaks **five** agent protocols out of the box. This guide
walks through each one and shows how to point your client at a
Morpheus instance.

## 1. MCP (Model Context Protocol) — JSON-RPC 2.0

Endpoints — pick one based on what the calling agent should be
allowed to do:

| Endpoint | Audience | Auth | Tools |
|---|---|---|---|
| `/mcp/storefront/v1/` | Anonymous shoppers | None | Catalog reads |
| `/mcp/cart/v1/` | Anonymous shoppers | None | Catalog + cart |
| `/mcp/checkout/v1/` | Anonymous shoppers | None | Catalog + cart + checkout |
| `/mcp/admin/v1/` | Staff bots | Bearer | Full Linda tool catalog |
| `/mcp/v1/` | Legacy clients | None | Curated public reads |

Every endpoint is a **dual-era** server (spec revision `2026-07-28`): a
request that carries the per-request `_meta`
(`io.modelcontextprotocol/protocolVersion` + `clientCapabilities`) and the
mirrored `MCP-Protocol-Version` / `Mcp-Method` / `Mcp-Name` headers is served
statelessly — no handshake, no session, `resultType` + server identity on
every result, `ttlMs` + `cacheScope` on lists, `server/discover` for
versions and capabilities, `-32020` / `-32022` / `-32602` on a bad envelope.
A client that opens with `initialize` is served the 2024-11-05 way, exactly as
before. The full rules and a modern `curl` are in
[`MCP_SERVER.md`](MCP_SERVER.md#two-protocol-eras-on-every-mcp-endpoint).

### Initialize handshake (legacy era)

```bash
curl -sX POST https://your-morpheus/mcp/storefront/v1/ \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize"}'
```

Response:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "serverInfo": {"name": "morpheus-storefront", "version": "0.2.0"}
  }
}
```

### List + call tools

```bash
# tools/list
curl -sX POST .../mcp/storefront/v1/ -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

# tools/call
curl -sX POST .../mcp/storefront/v1/ -d '{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {"name": "products.search", "arguments": {"query": "novel"}}
}'
```

### Claude Desktop / Cursor

Add to the client's MCP config (locations vary by client):

```json
{
  "mcpServers": {
    "morpheus": {
      "transport": "http",
      "url": "https://your-morpheus/mcp/admin/v1/",
      "headers": {"Authorization": "Bearer YOUR_KEY"}
    }
  }
}
```

The admin endpoint requires a key generated under
`/dashboard/settings/agent_mcp/`.

## 2. UCP (Universal Commerce Protocol)

Google and Shopify's open protocol (backed by Stripe, Etsy, Walmart and others)
is discovered through a **business profile** at `/.well-known/ucp`, in the
shape the specification describes (`ucp.version` as a date, `services` keyed by
reverse-domain names with a transport and an endpoint, `capabilities`,
`payment_handlers`). Morpheus serves it:

```bash
curl https://your-morpheus/.well-known/ucp
```

```json
{
  "ucp": {
    "version": "2026-08-25",
    "services": {
      "dev.ucp.shopping": [
        {"version": "2026-08-25", "spec": "https://ucp.dev/2026-08-25/specification/overview/",
         "transport": "mcp", "endpoint": "https://your-morpheus/mcp/checkout/v1/"}
      ]
    },
    "capabilities": {},
    "payment_handlers": {}
  }
}
```

The profile claims only what the store serves: the shopping service over MCP
(the checkout cluster when `agentic_checkout` is on, else the cart cluster).
The UCP checkout *capability* — `create_checkout` / `update_checkout` /
`complete_checkout` over REST — is not implemented yet, so it is not listed;
an agent that needs it falls back to the MCP tools or to ACP (section 4).

The pre-spec manifest from v0.30.0 is still served at `/.well-known/ucp.json`
for the clients that learned it, and links the profile as `profile_url`:

```bash
curl https://your-morpheus/.well-known/ucp.json
```

That legacy manifest advertises:

- The MCP endpoint URLs your storefront exposes
- Supported currencies + locales (from the `markets` plugin)
- Catalog API endpoint
- Capabilities (cart, checkout, returns, …)

**The `cart` / `checkout` capabilities are computed, not hardcoded** — they
report `true` only when the tools that back them actually resolve (i.e. the
`agentic_checkout` plugin is enabled). Disable it and the manifest honestly
reports `cart: false, checkout: false`, so a UCP agent never calls a dead
capability. `auth.required_for` lists `cart`/`checkout` too: anonymous
discovery (`tools/list`) is open on every cluster, but *executing* a
cart/checkout tool (`tools/call`) needs a Bearer token — they are
money-adjacent.

UCP-aware agents discover Morpheus through Google's verifier, then use the MCP
cart/checkout clusters to build a priced cart, and complete on the merchant's
own checkout (the ACP `/acp/` money path — see §3). No code changes required
on your side.

### MCP cart/checkout tools

When `agentic_checkout` is enabled, the `cart` and `checkout` MCP clusters
expose (Bearer token required to call):

```text
cart.create            → start a session, returns its id
cart.add_item          → add a product (SKU or product_id/variant_id);
                         reserves stock, applies live pricing
cart.get               → read the session + running totals
checkout.get_session   → read line items, buyer/fulfillment, totals
checkout.set_buyer     → apply email + shipping address → shipping + tax quote
```

These reuse the exact `agentic_checkout` cart-session flow the `/acp/` REST
endpoints use (same stock reservation, pricing, quoted-total stamp). **Payment
completion is NOT an MCP tool** — the charge stays on
`POST /acp/checkout_sessions/{id}/complete`, behind `payments_enabled` and the
full money-path gate set. Build + quote over MCP, complete on the merchant.

## 3. ACP (OpenAI/Stripe Agentic Commerce Protocol)

The `agentic_checkout` plugin (OFF by default — enable it from
**Dashboard → Apps** once enrolled) serves Phase 1 of the Agentic
Commerce Protocol, spec version `2026-04-17`:

- `/.well-known/acp.json` — discovery manifest (protocol version,
  checkout base URL, feed URL, payment handlers, Bearer auth).
- `/acp/feed.json` — product feed in the ACP product-feed shape: one
  entry per product with its `variants[]` (prices in minor units, the
  option name/value that distinguishes each variant, availability from
  the inventory app) and a `seller` block linking the store's policy
  pages. Rows come from the shared channel resolver (`plugins/feed_mapping.py`).
- `/acp/checkout_sessions` — `create` / `get` / `update` / `cancel` /
  `complete`, backed by the existing `Cart`.

**Getting listed in ChatGPT without a checkout** is a separate, smaller
door: OpenAI retired Instant Checkout in March 2026 and merchants on a
custom stack apply at chatgpt.com/merchants with a product feed in OpenAI's
feed specification. The `openai_shopping` app serves that feed as JSONL at
`/feeds/openai-products.jsonl` (one row per product or variant, with the
`seller_*`, country, eligibility, variant-group and return fields the
specification requires — Perplexity's merchant program takes the same
file) and, once OpenAI allow-lists an endpoint, pushes it there every six
hours with the bearer token stored under **Settings → Channels → ChatGPT
Shopping feed**. Coverage is on **Channels → ChatGPT Shopping**.

```bash
curl https://your-morpheus/.well-known/acp.json
```

Auth is Bearer-scoped with a dedicated `acp.checkout` scope. Unlike the
MCP cluster, this payment-adjacent surface does **not** inherit the
wildcard: a token reaches `/acp/` only when granted `acp.checkout`
explicitly. Tokens are minted under `/dashboard/apps/agent_mcp/tokens/`.

`completeCheckoutSession` returns a conformant `MessageError` with code
`unsupported` — the money path (Stripe Shared Payment Token redemption)
is Phase 2 and deferred. ChatGPT-Operator shoppers can also still
transact through the MCP cluster's `/mcp/checkout/v1/`.

## 4. Web Bot Auth, Visa TAP / Mastercard VI (Trusted Agents)

**At the origin (v0.90.0).** An agent that signs its requests per
[Web Bot Auth](https://datatracker.ietf.org/doc/draft-meunier-web-bot-auth-architecture/)
(RFC 9421 HTTP Message Signatures) is recognised by Morpheus itself,
with or without Cloudflare in front:

```http
Signature-Agent: "https://agent.example"
Signature-Input: sig1=("@authority" "signature-agent");created=1760000000;expires=1760000300;keyid="<RFC 7638 thumbprint>";alg="ed25519";tag="web-bot-auth"
Signature: sig1=:<base64 Ed25519 signature>:
```

The origin fetches the agent's JWKS from
`<Signature-Agent origin>/.well-known/http-message-signatures-directory`
(https only, fixed path, 64 KB cap, cached an hour, a failure remembered
for five minutes, at most 30 directory fetches a minute process-wide),
picks the key whose `kid` or thumbprint equals `keyid`, checks the
`created`/`expires` window (≤ 24 h) and the `web-bot-auth` tag, and
verifies the signature over `@authority` (+ `signature-agent`). A verified
request carries `request.trusted_agent` with `provider="web-bot-auth"` and
the agent origin as its id, so the order stamp below works unchanged. A
request that does not verify is simply anonymous — never refused — and
verification is a *name on the order*, not a permission: scopes and
consent still gate every write. `/.well-known/agent.json` lists the
exact contract under `web_bot_auth`.

**Behind Cloudflare.** Visa TAP and Mastercard VI ride on **Cloudflare
Web Bot Auth**. Cloudflare verifies signed agent traffic at the edge, then
forwards the request with trust headers attached:

```http
X-Verified-Agent-Id: visa-tap:agent-12345
X-Verified-Agent-Provider: visa-tap
X-Verified-Agent-Signature: <opaque>
```

Morpheus's `TrustedAgentMiddleware` reads those headers and
attaches `request.trusted_agent`. At checkout, the order's
`metadata.agent_id` is stamped with the verified ID, so merchants
get an auditable trail of which agent placed which order.

Discovery: `/.well-known/agent.json` advertises Morpheus's
acceptance of both protocols + lists the verification header names
Cloudflare should set.

Enable the chain:

1. Put your Morpheus instance behind Cloudflare.
2. Turn on **Web Bot Auth** in the Cloudflare dashboard.
3. Cloudflare's edge handles the cryptographic verification; your
   origin sees only verified, header-stamped traffic.

## 5. Legacy webhooks (HMAC-SHA256)

For agents that don't speak any of the above:

```text
POST /webhooks/<topic>/      — outbound delivery target
GET  /dashboard/webhooks/    — subscribe + replay UI
```

## 6. Discovery files (how an agent finds all of the above)

Point a fresh agent at the site root — everything is self-describing:

```text
GET /agents.md          — agent-onboarding manifest (Markdown): what the store
                          is, how to discover it, and how to transact. The
                          "Agent commerce endpoints" section is contributed by
                          agent_mcp (MCP servers + UCP/TAP manifests + auth), so
                          it only lists surfaces that are actually enabled.
GET /llms.txt           — llmstxt.org catalog (compact); /llms-full.txt (verbose)
GET /ai/products.json   — structured product feed
GET /.well-known/ucp.json, /.well-known/agent.json, /.well-known/acp.json
GET /sitemap.xml, /robots.txt
```

`/agents.md` is assembled by the `seo` plugin (which seeds the discovery links
from its own surfaces) via the `AGENT_READINESS_SECTIONS` hook filter: any plugin
that owns an agent-facing surface appends its own section, and a disabled owner's
section (and endpoints) vanish together — so the manifest never advertises a dead
endpoint. Gated by the same *expose-to-AI* toggle as `/llms.txt`.

See [`docs/MCP_SERVER.md`](MCP_SERVER.md) for the full tool catalog,
[`docs/COMPLIANCE.md`](COMPLIANCE.md) for the AI Act audit-trail
export.
