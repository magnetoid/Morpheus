# Zendrop dropshipping — the `zendrop` app

*Spec written 2026-10-07 (v0.79.0). Status: shipping; the automated order push
and tracking pull over Zendrop's MCP tools are a follow-up gated on seeing the
tool catalogue for the owner's account.*

## 1. Overview

- **Goal:** let a Morpheus store fulfil orders through Zendrop (US-warehouse
  dropshipping): map variants to Zendrop products, work paid orders through
  Zendrop quickly, and ship them with Zendrop's tracking numbers so the shopper
  gets the normal "on its way" email and the order reaches *shipped*.
- **Target users:** supernatural-shop first; any store that opts in with
  `MORPHEUS_EXTRA_APPS=…,plugins.installed.zendrop`.
- **Why now:** the owner wants Zendrop alongside DSers as a supplier.

## 2. How Zendrop can be connected (researched 2026-10-07)

- **Native connectors:** Shopify, Wix, TikTok Shop US, ClickFunnels. The
  WooCommerce integration was discontinued in April 2023. No CSV order import.
- **Manual orders:** Zendrop's "Sample Order" form works only with one of
  those stores connected to the account, and Zendrop itself calls it
  unsuitable for volume. "Add New Store → Other → Direct API Access" files a
  request, nothing more.
- **MCP server:** `https://app.zendrop.com/mcp/v1` — a standards-compliant
  MCP server (JSON-RPC 2.0 over HTTP POST; `Authorization: Bearer`; OAuth
  resource metadata at `/.well-known/oauth-protected-resource/mcp/v1`; PKCE
  with dynamic client registration; rate limits 120 read / 30 write / 10
  fulfilment per minute). Scopes include `catalog:read`, `my_products:read|write`,
  `orders:read`, `orders:write`, `order_issues:read|write`, `stores:read|write`,
  `billing:read`, `users:read`, `reporting:read`. Zendrop's marketing describes
  listing/filtering orders, fulfilment status, tracking numbers, shipping
  estimates per product and country, *triggering fulfilment* and updating
  addresses — on orders already in Zendrop. **The tool names are visible only to
  an authenticated client**, and nothing documented creates an order from an
  external store.

**Decision:** connect over MCP for *discovery* (show the merchant exactly which
tools their token reaches), make the manual loop fast and auditable today, and
add automated fulfilment/tracking in a follow-up once the tool catalogue for
this account is known. Shared supplier machinery (eligibility, address
normalisation, tracking-file parsing, ship-with-tracking) moves to
`plugins/dropshipping/` and is used by both `dsers` and `zendrop`.

## 3. Data models (`plugins/installed/zendrop/models.py`)

- **`ZendropLink`** — per product/variant: `zendrop_product_id`,
  `zendrop_variant_id`, `product_url`, `notes`. Unique on (`product`, `variant`).
  Edited on the product form (`PRODUCT_FORM_CARDS` / `PRODUCT_FORM_SAVED`).
- **`ZendropOrder`** — OneToOne → `orders.Order` (`related_name='zendrop_order'`):
  `status` (*placed, shipped, cancelled*), `zendrop_order_number`, `placed_at`,
  `tracking_number`, `carrier`, `shipped_at`, `note`. The shipping state itself
  is written where the platform owns it (`Order.ship()` + `orders.Fulfillment`).

## 4. Features and acceptance

- [ ] **Connection.** Settings → Apps → Zendrop: `access_token` (write-only).
  Page button "Test connection" runs MCP `initialize` + `tools/list`, caches
  the snapshot for an hour and shows server, tool count, tools grouped by what
  they allow (orders read/write, shipping estimates, catalog) and the raw list.
  *Acceptance:* mocked server over JSON and SSE; 401 → clear token-free error;
  no token → "No access token saved"; network failure → reported, not raised.
- [ ] **Order sheet.** For each paid, shippable, not-yet-placed order: the
  supplier-ready address (full country name, cleaned lines, phone digits) and
  each line's Zendrop product/variant id (flagged when unmapped). "Placed in
  Zendrop" (+ Zendrop order number) records it and moves a *confirmed* order to
  *processing* when the setting says so.
- [ ] **Shipping.** Per placed order: tracking number + carrier → `Order.ship()`,
  `Fulfillment(in_transit, carrier, tracking URL)`, `ZendropOrder(shipped)`;
  or a tracking CSV (header-tolerant; Zendrop's orders export) for many at once.
  *Acceptance:* `ORDER_FULFILLED` fires once; already-shipped / cancelled / no
  tracking are reasons, not errors.
- [ ] **Needs attention.** An order cancelled after placing is flagged.
- [ ] **Settings:** `access_token`, `tracking_url_template`,
  `mark_processing_when_placed` — each read by code.

## 5. Constraints

- Plugin owns everything under `plugins/installed/zendrop/`; `requires = ['orders',
  'catalog']`. Shared code only through `plugins.dropshipping` (plugin
  infrastructure at the package root, like `plugins/feed_mapping.py`).
- No new dependencies: `requests` for HTTP. The token never appears in logs or
  error text. Only `initialize` / `tools/list` are called — nothing writes to
  Zendrop in this version.
- Dashboard views: `@staff_member_required` + existing capabilities
  (`orders.read` / `orders.write`).

## 6. Out of scope (deliberately)

- Automatic order creation or fulfilment through MCP tools; tracking pull.
  Follow-up: with the owner's token, read the tool catalogue and schemas, then
  implement `services/fulfilment.py` behind `ZendropOrder`.
- Product import from Zendrop's catalogue (titles, images, prices).
- OAuth PKCE sign-in flow (a pasted access token is enough for one store).

## 7. Open questions for the owner

- Generate a Zendrop access token for the MCP server with the orders and
  catalog scopes and paste it into Settings → Apps → Zendrop; press "Test
  connection". The tool list it shows decides what the follow-up can automate.
- Whether a Shopify/Wix/TikTok store is connected to the Zendrop account (the
  manual order form needs one).
