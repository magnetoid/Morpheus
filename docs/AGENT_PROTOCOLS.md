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

### Initialize handshake

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

Google, Shopify, Stripe, Etsy, and Walmart converged on a single
MCP-compatible discovery manifest at
`/.well-known/ucp.json`. Morpheus ships it:

```bash
curl https://your-morpheus/.well-known/ucp.json
```

The manifest advertises:

- The MCP endpoint URLs your storefront exposes
- Supported currencies + locales (from the `markets` plugin)
- Catalog API endpoint
- Capabilities (cart, checkout, returns, …)

UCP-aware agents discover Morpheus through Google's verifier, then
fall back to the MCP cluster for actual transactions. No code
changes required on your side.

## 3. ACP (OpenAI/Stripe Agentic Commerce Protocol)

The `agentic_checkout` plugin (OFF by default — enable it from
**Dashboard → Apps** once enrolled) serves Phase 1 of the Agentic
Commerce Protocol, spec version `2026-04-17`:

- `/.well-known/acp.json` — discovery manifest (protocol version,
  checkout base URL, feed URL, payment handlers, Bearer auth).
- `/acp/feed.json` — product feed (reuses the `google_shopping` mapping).
- `/acp/checkout_sessions` — `create` / `get` / `update` / `cancel` /
  `complete`, backed by the existing `Cart`.

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

## 4. Visa TAP / Mastercard VI (Trusted Agents)

Both ride on **Cloudflare Web Bot Auth**. Cloudflare verifies
signed agent traffic at the edge, then forwards the request with
trust headers attached:

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
