---
name: morpheus-api
description: How external systems publish + edit Morpheus catalog, inventory, and orders over MCP or GraphQL using a Bearer token from the dashboard. Use when the user asks about API tokens, "how do I publish from outside", "how does my agent edit products", PDF replacement, image upload via API, or scope/permission control for the MCP cluster.
---

# Morpheus external-write API

Morpheus exposes the same write surface through two protocols, both
gated by the same Bearer token issued from the dashboard at
`/dashboard/apps/agent_mcp/tokens/` (Settings → Developer tools →
**API tokens**).

## Auth

```
Authorization: Bearer mph_<32 random urlsafe bytes>
```

Tokens are 32 random bytes (`secrets.token_urlsafe(32)`) with an
`mph_` prefix — easy to spot in logs. They live in
`PluginConfig['agent_mcp']['public_keys']` as
`{id, label, token, created_at, last_used_at}` dicts. Legacy raw-string
tokens still work; they appear in the UI tagged `(legacy)`.

Resolution happens in
`plugins/installed/agent_mcp/auth.py:apply_bearer_user`. Valid tokens
replace `request.user` with a synthetic staff `Customer` named
`mcp-service`. Invalid / missing → falls through to Django session
auth. Both `MorpheusGraphQLView.dispatch` (api/graphql_view.py) and
the MCP admin endpoint (`plugins/installed/agent_mcp/views.py`) call
this resolver.

## Two surfaces, same token

| Surface | URL | Best for |
|---|---|---|
| MCP | `POST /mcp/admin/v1/` | LLM agents (tool discovery via `tools/list`) |
| GraphQL | `POST /graphql/` | Scripts, n8n, traditional automations |

## Service layer (single source of truth)

Every write goes through one of:

- `plugins/installed/catalog/services.py`
  - `publish_digital_product(...)` — PDF book publish (downloads PDF + cover)
  - `create_product(...)` — generic product create
  - `update_product(slug, **fields)` — ~30 fields touch-only-what-you-pass
  - `update_digital_pdf(slug, pdf_url)` — replace just the PDF
  - `add_product_image(slug, image_url, ...)` — download + attach
  - `remove_product_image(image_id)`
  - `set_primary_image(image_id)`
  - `archive_product(slug)` / `restore_product(slug, status)` / `delete_product(slug)`
  - `create_category(...)` / `update_category(...)` / `archive_category(...)`
- Inventory: `setStock` / `adjustStock` write directly to `StockLevel`.
- Orders: FSM transitions on `plugins.installed.orders.models.Order`
  (`fulfill()`, `ship()`, `cancel()`) plus a manual `mark_refunded`
  that bypasses the FSM.

GraphQL mutations and MCP `@tool` wrappers both delegate to these
services so validation and side effects stay aligned.

## Safety guarantees baked in

- HTTPS-only URL inputs (`pdf_url`, `image_url`, `cover_image_url`).
- 50 MB PDF cap, 8 MB image cap, 30-second download timeout.
- Image content-type allowlist: `image/jpeg`, `image/png`, `image/webp`, `image/gif`.
- Slug + SKU collision-safe (numeric suffix, up to 200 retries).
- Atomic transactions — failed download means no half-built row.
- Status defaults to `draft` on `create_product` so half-built rows
  never accidentally go live.
- Destructive ops (`delete_product`, `archive_category`,
  `cancel_order`, `mark_order_refunded`) have `requires_approval=True`
  in MCP — they queue for staff approval before executing.

## Common lifecycle (GraphQL example)

```graphql
# 1. Create a draft
mutation { createProduct(input: { name: "T-Shirt", priceAmount: "29.99" }) { slug } }

# 2. Add a cover image
mutation { addProductImage(input: { slug: "t-shirt", imageUrl: "https://…/front.jpg", isPrimary: true }) { id } }

# 3. Initial stock
mutation { setStock(input: { productSlug: "t-shirt", quantity: 100 }) { available } }

# 4. Flip live
mutation { updateProduct(input: { slug: "t-shirt", status: "active" }) { slug status } }

# 5. Replace the PDF on a digital product later
mutation { updateDigitalPdf(input: { slug: "my-book", pdfUrl: "https://…/book-v2.pdf" }) { slug error } }

# 6. Re-price
mutation { updateProduct(input: { slug: "t-shirt", priceAmount: "24.99" }) { slug priceAmount } }

# 7. Retire
mutation { archiveProduct(slug: "t-shirt") { slug status } }
```

## Mapping to MCP

Every GraphQL mutation has a matching MCP tool with the
`<domain>.<action>` naming convention:

| GraphQL | MCP tool |
|---|---|
| `publishDigitalProduct` | `catalog.publish_digital_product` |
| `createProduct` | `catalog.create_product` |
| `updateProduct` | `catalog.update_product` |
| `updateDigitalPdf` | `catalog.update_digital_pdf` |
| `addProductImage` | `catalog.add_product_image` |
| `removeProductImage` | `catalog.remove_product_image` |
| `setPrimaryImage` | `catalog.set_primary_image` |
| `archiveProduct` | `catalog.archive_product` |
| `restoreProduct` | `catalog.restore_product` |
| `deleteProduct` | `catalog.delete_product` |
| `createCategory` | `catalog.create_category` |
| `updateCategory` | `catalog.update_category` |
| `archiveCategory` | `catalog.archive_category` |
| `setStock` | `inventory.set_stock` |
| `adjustStock` | `inventory.adjust_stock` |
| `markOrderFulfilled` | `orders.mark_fulfilled` |
| `markOrderShipped` | `orders.mark_shipped` |
| `cancelOrder` | `orders.cancel` |
| `markOrderRefunded` | `orders.mark_refunded` |

## Adding a new mutation

When extending the write surface:

1. Add the service function to the relevant `plugins/installed/<plugin>/services.py`
   (raise `PublishError` for caller-fixable problems).
2. Add the GraphQL mutation to `plugins/installed/<plugin>/graphql/mutations.py`
   inside the right `*MutationExtension` class. Use `_is_staff(info)`
   to gate it; return a typed `*MutationResult` with an `error: str` field.
3. Add the MCP tool wrapper in `plugins/installed/agent_core/tools/<domain>.py`
   with `@tool(name='<domain>.<action>', scopes=['<domain>.write'], ...)`.
4. Register the tool in `plugins/installed/agent_core/tools/__init__.py`.
5. Update `docs/MCP_SERVER.md` write-surface table and this skill.

## When NOT to use

- **Storefront-public reads** — the catalog GraphQL queries on the
  agent-only path (`/graphql/agent/`) are designed for this; no token needed.
- **Cart + checkout for shoppers** — `/mcp/cart/v1/` and `/mcp/checkout/v1/`
  are the right surfaces; they don't require a Bearer token.
- **Long-running batch imports** — prefer the CSV importer plugin
  (`/dashboard/apps/importers/csv/`) for thousands of rows.
