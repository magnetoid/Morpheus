# Morpheus MCP server + GraphQL Bearer auth

Every Morpheus install ships a [Model Context Protocol](https://modelcontextprotocol.io)
cluster — four Shopify-shaped servers mounted at `/mcp/*/v1/` — plus a
GraphQL endpoint at `/graphql/`. External AI clients (Claude Desktop,
Cursor, Continue, custom scripts) and SaaS automations can list,
read, and write through either surface using the **same** Bearer
token issued from the dashboard.

## Endpoints

```
# MCP cluster (JSON-RPC 2.0 per /mcp/v1/ legacy + per-audience servers)
POST /mcp/v1/                    Legacy curated reads. initialize/tools/list are
#                                open; tools/call requires a Bearer token.
POST /mcp/storefront/v1/         Public catalog reads
POST /mcp/cart/v1/               Storefront reads + cart.create/add_item/get
POST /mcp/checkout/v1/           + checkout.get_session/set_buyer (quote)
#   ^ cart/checkout tools need agentic_checkout enabled; tools/call needs a
#     Bearer token. Completion stays on the /acp/ REST money path.
POST /mcp/admin/v1/              Linda's full catalog — writes too (Bearer auth
#                                required at the transport). requires_approval
#                                writes need the token's approved_tools grant —
#                                except Linda turn tokens (see below), which need
#                                the merchant's own "yes" in the conversation.

GET  /mcp/v1/health/             Liveness probe (mounted on /mcp/v1/, not /admin/)
GET  /mcp/v1/manifest.json       ChatGPT-style plugin manifest

# GraphQL
POST /graphql/                   Typed schema, Bearer or session auth
POST /graphql/agent/             Agent-only path (Cloudflare TAP / MVI)
```

## Authentication

A Bearer token issued at **/dashboard/apps/agent_mcp/tokens/** works
on *both* surfaces:

```
Authorization: Bearer mph_<32 random urlsafe bytes>
```

Tokens carry a label, creation timestamp, and last-used timestamp.
Revoking removes the row from `PluginConfig['agent_mcp']['public_keys']`
and takes effect immediately on the next call. There is no expiration;
rotate by creating + revoking.

### Issuing a token

1. **Dashboard** (recommended): Settings → Developer tools →
   **API tokens** → Create token. Full value is shown ONCE. The
   table only shows first4…last4 thereafter.
2. **Shell** (for automation / scripted bootstrap):

```bash
docker compose exec web python manage.py shell -c "
from plugins.installed.agent_mcp.dashboard import _new_token, _load_entries, _save_entries
import uuid, datetime as dt
entries = _load_entries()
new = {
  'id': str(uuid.uuid4()),
  'label': 'bootstrap token',
  'token': _new_token(),
  'created_at': dt.datetime.utcnow().isoformat(timespec='seconds') + 'Z',
  'last_used_at': '',
}
entries.append(new)
_save_entries(entries)
print(new['token'])
"
```

> A token created without an `mcp_scopes`/`graphql_scopes` key inherits the
> **wildcard** (full access) for back-compat. Scope it down in the dashboard
> (Settings → Developer tools → API tokens → permissions) or add explicit
> `mcp_scopes`/`graphql_scopes` lists to the entry above. A present-but-empty
> list (`[]`) grants nothing.

### How Bearer auth flows server-side

When the request hits either `/mcp/admin/v1/` or `/graphql/`:

1. Header parsed; presented token compared against
   `_api_keys()` (reads `PluginConfig['agent_mcp']['public_keys']`).
2. On match, `request.user` is replaced with a synthetic staff
   Customer named `mcp-service` (lazily created, `is_staff=True`,
   `is_active=True`, no usable password). Every mutation attributed
   to this user in the audit log.
3. `last_used_at` on the token entry is updated (best-effort).

If the token is missing / wrong, the request falls through to
Django's session middleware — useful for browser-based admins.

### Linda turn tokens (Janus engine)

Linda's engine calls `/mcp/admin/v1/` with a short-lived signed **turn token**
(`Authorization: Bearer lt1.…`), minted per chat turn by
`core/assistant/turn_identity.py`. It is not an API key: it never appears in
`public_keys`, cannot be issued from the dashboard, and is rejected everywhere
else, including `/graphql/`. It names one staff user, one conversation and the
conversation's mode, and expires shortly after the turn's timeout.

A call under a turn token runs as the real staff user, not `mcp-service`, and
passes the same gates as Linda's in-process loop (`core/assistant/gates.py`):

- **Scope** — Linda's scope profile, not the token's scopes.
- **Mode** — `tools/list` and `tools/call` see only the mode's tools; the user's
  entitlement to that mode is re-checked on every call.
- **Consent** — a `requires_approval` tool is refused with an `isError` result
  starting `approval_required:` until the merchant's own next message in that
  conversation is an affirmative reply. The grant is single-use and bound to the
  exact arguments. `approved_tools` plays no part.
- **Audit** — every write attempt, refused or executed, records
  `assistant.tool_write` with the merchant as actor, alongside the usual
  `agents.decision` row. Tool calls are also stored in the conversation history.

## Write surface (catalog, inventory, orders)

The MCP **admin** server (`/mcp/admin/v1/`) and GraphQL endpoint
(`/graphql/`) both expose the full Linda write catalog. The server is
**not** read-only — agents can drive operations end-to-end.

### Catalog

| Tool / Mutation | Purpose | Approval? |
|---|---|---|
| `catalog.publish_digital_product` / `publishDigitalProduct` | Publish a PDF book — downloads PDF + cover, creates product | no |
| `catalog.create_product` / `createProduct` | Create any product type | no |
| `catalog.update_product` / `updateProduct` | Update any field (~30 fields) | no |
| `catalog.update_digital_pdf` / `updateDigitalPdf` | Replace the PDF on an existing digital product | no |
| `catalog.add_product_image` / `addProductImage` | Download + attach an image | no |
| `catalog.remove_product_image` / `removeProductImage` | Delete one image | no |
| `catalog.set_primary_image` / `setPrimaryImage` | Promote image to primary | no |
| `catalog.archive_product` / `archiveProduct` | Status → archived | no |
| `catalog.restore_product` / `restoreProduct` | Restore archived | no |
| `catalog.delete_product` / `deleteProduct` | Hard delete | **yes** |
| `catalog.create_category` / `createCategory` | New category | no |
| `catalog.update_category` / `updateCategory` | Update category | no |
| `catalog.archive_category` / `archiveCategory` | Delete category | **yes** |
| `catalog.create_variant` / `createVariant` | Add a new variant to a product | no |
| `catalog.update_variant` / `updateVariant` | Update any variant field (matched by SKU) | no |

#### Variant fields

`create_variant` and `update_variant` accept (every field optional except
`name` + `sku` on create):

| Field | Type | Purpose |
|---|---|---|
| `name` | str | Display name ("Hardcover", "Audiobook narrated by author") |
| `sku` | str | Stock Keeping Unit (unique across all variants) |
| `size` | str(50) | Free-text size label ("XL", "300 ml"). Independent of the AttributeValue M2M. |
| `short_description` | str | One-line per-variant pitch. Storefront falls back to `Product.short_description` when blank. |
| `description` | str | Full per-variant description (HTML/Markdown). Storefront falls back to `Product.description` when blank. |
| `price_amount` | decimal | Variant price. Pass with `price_currency` (defaults to USD). |
| `price_currency` | str(3) | ISO currency code (USD, EUR, …). |
| `compare_at_amount` | decimal | Strike-through price for sale display. |
| `variant_type` | enum | `physical` (default, ships), `digital` (downloadable), `virtual` (no fulfillment). |
| `requires_shipping` | bool | Auto-derived from `variant_type` when omitted. |
| `is_taxable` | bool | Per-variant override of Product.is_taxable. |
| `inventory_policy` | enum | `deny` (default, refuse oversell) or `continue` (allow backorder). |
| `barcode` | str(50) | UPC / EAN / ISBN. |
| `is_active` | bool | When false, the variant is hidden from the storefront. |
| `sort_order` | int | Display order (lower = first). |

Both calls return the full variant dict via `_serialize_variant` — useful
for chained agent flows ("create variant, then upload the digital file
using the returned `id`").

### Inventory

| Tool / Mutation | Purpose |
|---|---|
| `inventory.set_stock` / `setStock` | Absolute quantity per variant (approval-gated) |
| `inventory.adjust_stock` / `adjustStock` | Delta by `variant_sku`/`warehouse_code`, refuses negative result (approval-gated) |

### Orders

| Tool / Mutation | Purpose | Approval? |
|---|---|---|
| `orders.mark_fulfilled` / `markOrderFulfilled` | FSM fulfill() | no |
| `orders.mark_shipped` / `markOrderShipped` | FSM ship() + tracking number | no |
| `orders.cancel` / `cancelOrder` | FSM cancel() | **yes** |
| `orders.mark_refunded` / `markOrderRefunded` | Bypass FSM for external refunds | **yes** |

All write operations enforce `info.context.request.user.is_staff` —
the Bearer-resolved `mcp-service` user satisfies this; sessionless
unauthenticated calls do not.

### Translations (i18n)

For external translators + translation tools. Any object is addressed by
`content_type` (`app_label.model`, e.g. `catalog.product`) + `object_id`.
Scopes: `i18n.read` / `i18n.write`.

| Tool / Mutation | Purpose | Approval? |
|---|---|---|
| `i18n.languages` | List enabled languages (translation targets) | no |
| `i18n.get_translations` / `translations(...)` | Read stored translations for an object | no |
| `i18n.set_translation` / `setTranslation(...)` | Set a field's translation in a language | **yes** (MCP) |

GraphQL also exposes `enabledLanguages`. The same Bearer token works from MCP or
GraphQL; the merchant grants `i18n.read`/`i18n.write` when minting the token.

## Read surface

Read tools available on the curated `/mcp/v1/` (discovery is open; `tools/call`
requires a Bearer token):

| Tool | Purpose |
|---|---|
| `products.search` / `find_products` | Search catalog |
| `products.get` / `get_product` | Single product by slug/sku |
| `cms.pages` | Published CMS pages |
| `analytics.top_products` | Best-selling products |
| `memory.recall` | Linda's stored merchant preferences |

Read tools on `/mcp/admin/v1/` additionally include:
`orders.list_recent`, `orders.summary`, `analytics.revenue_summary`,
`catalog.stats`, `catalog.list_categories`, `catalog.find_products`,
`catalog.get_product`, plus all writes above, plus diagnostics
(`fs.*`, `logs.*`, `plugins.*`).

## Examples

### Publish a PDF book (MCP)

```bash
curl -X POST https://YOUR-MORPHEUS-DOMAIN/mcp/admin/v1/ \
  -H "Authorization: Bearer mph_..." \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
    "params": {
      "name": "catalog.publish_digital_product",
      "arguments": {
        "title": "Crime and Punishment",
        "pdf_url": "https://your-cdn.com/crime.pdf",
        "cover_image_url": "https://your-cdn.com/crime.jpg",
        "price_amount": "9.99",
        "status": "active"
      }
    }
  }'
```

### Same call via GraphQL

```bash
curl -X POST https://YOUR-MORPHEUS-DOMAIN/graphql/ \
  -H "Authorization: Bearer mph_..." \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation($i: PublishDigitalProductInput!){ publishDigitalProduct(input: $i){ id slug url error } }",
    "variables": { "i": {
      "title": "Crime and Punishment",
      "pdfUrl": "https://your-cdn.com/crime.pdf",
      "coverImageUrl": "https://your-cdn.com/crime.jpg",
      "priceAmount": "9.99",
      "status": "active"
    } }
  }'
```

### Full lifecycle from an external agent

```graphql
# 1. Create a draft
mutation { createProduct(input: { name: "T-Shirt", priceAmount: "29.99" }) { slug } }

# 2. Add a cover image
mutation { addProductImage(input: { slug: "t-shirt", imageUrl: "https://…/front.jpg", isPrimary: true }) { id } }

# 3. Set initial stock
mutation { setStock(input: { productSlug: "t-shirt", quantity: 100 }) { available } }

# 4. Flip to active
mutation { updateProduct(input: { slug: "t-shirt", status: "active" }) { slug status } }

# 5. Replace the PDF later (digital products)
mutation { updateDigitalPdf(input: { slug: "my-book", pdfUrl: "https://…/book-v2.pdf" }) { slug error } }
```

### Connecting from Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```jsonc
{
  "mcpServers": {
    "morpheus-admin": {
      "transport": {
        "type": "http",
        "url": "https://YOUR-MORPHEUS-DOMAIN/mcp/admin/v1/",
        "headers": {
          "Authorization": "Bearer mph_..."
        }
      }
    }
  }
}
```

Restart Claude. The server appears under Tools as `morpheus-admin`
with the full write catalog.

## Resources

Three discoverable resource URIs (`resources/list`):

- `morpheus://catalog/featured` — featured products
- `morpheus://catalog/recent` — newest 20 products
- `morpheus://analytics/today` — today's revenue + order count
