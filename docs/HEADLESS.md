# Headless Morpheus

> *"I want to use Morpheus like Saleor — no Django templates, just the API."*

Yes, you can. The bundled `dot_books` theme is optional. Everything in it is replicable through the GraphQL + REST API.

## What you get on the headless path

- **GraphQL endpoint**: `https://your.shop/api/graphql/`
- **REST endpoints**: `/api/health/`, `/api/ready/`, `/api/payments/stripe/webhook/`, `/api/agents/*`
- **MCP endpoint** for AI clients: `/mcp/v1/`
- **Agent-readable surface**: `/llms.txt`, `/llms-full.txt`, `/md/products/<slug>`
- **Sitemap + SEO surfaces**: `/sitemap.xml`, `/sitemap-images.xml`, `/sitemap-news.xml`, `/robots.txt`, `/manifest.json`, `/opensearch.xml`
- **Webhooks** out of `/dashboard/apps/webhooks_ui/`

## Disabling the bundled theme

The theme is loaded by `ThemeLoader` in `themes/`. To run truly headless:

1. Set `MORPHEUS_THEME=none` in your `.env` (or unset `MORPHEUS_DEFAULT_THEME`).
2. Storefront URLs (`/products/<slug>/`, etc.) will return 404 — your frontend owns those paths.
3. The admin dashboard at `/dashboard/*` still works (it has its own templates, separate from the storefront theme).

## Minimal GraphQL operations

### Read the catalogue

```graphql
query Products($first: Int!, $category: String) {
  products(first: $first, category: $category) {
    edges {
      node {
        id
        slug
        name
        price { amount currency }
        compareAtPrice { amount currency }
        primaryImage { url altText }
        images { url altText sortOrder isPrimary }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
```

### Authoritative cart totals (NEVER compute these client-side)

```graphql
query CartTotals($input: CartTotalsInput!) {
  cartTotals(input: $input) {
    subtotal { amount currency }
    tax { amount currency }
    shipping { amount currency }
    discount { amount currency }
    total { amount currency }
    lines { rateName ratePercent amount { amount currency } }
  }
}
```

Compute on the client only for display speed; the value you charge must come from this query (or `Mutation.checkoutComplete` which calls it server-side).

### Complete checkout

```graphql
mutation Checkout($input: CheckoutCompleteInput!) {
  checkoutComplete(input: $input) {
    order {
      id
      orderNumber
      status
      paymentStatus
      total { amount currency }
    }
    paymentIntent {
      clientSecret
    }
    errors { field message code }
  }
}
```

Bind the `clientSecret` to Stripe Elements on the frontend, confirm card, done.

## Auth

- **Customers**: cookie-session by default, JWT optional. Set `Authorization: Bearer <token>` once authenticated.
- **Staff / agents**: bearer token from `/dashboard/staff/account/` → "API tokens".
- **MCP clients**: bearer token with the `agent` scope.

## Webhooks for state sync

Don't poll. Subscribe to:

- `order.placed`, `order.paid`, `order.cancelled`, `order.refunded`
- `product.created`, `product.updated`, `product.low_stock`
- `customer.registered`, `customer.login`

Verify the HMAC signature on each delivery (see [WEBHOOK_RECIPES.md](WEBHOOK_RECIPES.md)).

## SEO from a headless frontend

If your Next.js / SvelteKit / Astro app is serving the storefront:

- Fetch `https://api.your.shop/md/products/<slug>` at build time for LLM-friendly markdown.
- Mirror `https://api.your.shop/sitemap.xml` from your frontend's `/sitemap.xml`. The XML already uses your storefront's canonical URLs (set them in `/dashboard/apps/seo/settings/`).
- Embed the JSON-LD blocks that Morpheus's `seo` plugin generates — fetch them via the storefront query and inject into your `<head>` directly. Schema types: Product, ProductGroup, Offer with MerchantReturnPolicy + shippingDetails, BreadcrumbList, FAQPage, Organization, WebSite.

## What's NOT in the GraphQL surface (yet)

These still require REST or template scraping today; we're moving them to GraphQL on the public-API stability roadmap:

- Multi-warehouse stock allocation preview
- Gift-card redemption mid-cart (works at checkout via mutation, not as a separate operation)
- Bulk price edit (admin-only)
- CMS pages tree
- Affiliate-link attribution lookup

See [API_STABILITY.md](API_STABILITY.md) for what's frozen and what isn't.

## Reference implementations

- **`dot_books`** theme — the canonical Django-template consumer of the same GraphQL surface. Read its templates to see the queries we use in production.
- **`/dashboard/apps/agent_mcp/`** — the MCP server as a working JSON-RPC integration target.

If you build a headless storefront on Morpheus, open a PR adding it to this file with a "Built with Morpheus" link.
