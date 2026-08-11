# Morpheus — Enterprise E-commerce + CMS Gap Analysis (Codebase Audit)

Date: 2026-05-05

This report audits Morpheus across: commerce, CMS, architecture, security, UX, scalability, analytics, internationalization, and DevOps. It highlights what exists today, what is missing, and a prioritized roadmap to reach best-in-class status.

## 1) Current Strengths (What’s Already Differentiated)

- **Plugin-first architecture** with a hook/event bus: [ARCHITECTURE.md](file:///Users/magnetoid/coding/morph/ARCHITECTURE.md), [hooks.py](file:///Users/magnetoid/coding/morph/core/hooks.py)
- **Event-driven foundation** (Transactional Outbox → NATS JetStream): [core/models.py](file:///Users/magnetoid/coding/morph/core/models.py), [core/tasks.py](file:///Users/magnetoid/coding/morph/core/tasks.py)
- **Operational primitives**: OpenTelemetry + logs correlation + Loki/Vector (dev stack): [core/observability.py](file:///Users/magnetoid/coding/morph/core/observability.py), [compose/](file:///Users/magnetoid/coding/morph/compose)
- **Modern e-commerce primitives exist** (Orders FSM, Inventory allocation, Stripe intents): [orders/models.py](file:///Users/magnetoid/coding/morph/plugins/installed/orders/models.py), [inventory/services.py](file:///Users/magnetoid/coding/morph/plugins/installed/inventory/services.py), [payments/services/stripe.py](file:///Users/magnetoid/coding/morph/plugins/installed/payments/services/stripe.py)
- **SEO plugin is unusually strong** (sitemap/robots/llms/redirects/404 logging): [seo/services.py](file:///Users/magnetoid/coding/morph/plugins/installed/seo/services.py), [seo/middleware.py](file:///Users/magnetoid/coding/morph/plugins/installed/seo/middleware.py)

## 2) E-commerce Capabilities — Audit + Gaps

### 2.1 Product Catalog Management

**Implemented**
- Products, variants, categories, collections, images, attributes: [catalog/models.py](file:///Users/magnetoid/coding/morph/plugins/installed/catalog/models.py)
- GraphQL schema surface: [catalog/graphql/types.py](file:///Users/magnetoid/coding/morph/plugins/installed/catalog/graphql/types.py)

**Gaps for best-in-class**
- Catalog read model & search: no dedicated search engine (Typesense/Elastic) or relevance tuning.
- Merchandising: “rules-based collections”, scheduled pricing, per-channel catalogs, product bundles.
- Catalog governance: approvals, audit trail/versioning, bulk operations UX.

### 2.2 Cart Functionality

**Implemented (backend)**
- `Cart` and `CartItem` models + service: [orders/models.py](file:///Users/magnetoid/coding/morph/plugins/installed/orders/models.py), [orders/services.py](file:///Users/magnetoid/coding/morph/plugins/installed/orders/services.py)
- GraphQL mutations exist: [orders/graphql/mutations.py](file:///Users/magnetoid/coding/morph/plugins/installed/orders/graphql/mutations.py)

**Gaps**
- Storefront UX wiring for add/update/remove/coupons appears absent; templates look display-only.
- Cart totals breakdown (subtotal/discount/shipping/tax/total) is not consistently exposed via GraphQL.

### 2.3 Checkout / Payment Processing

**Implemented (primitives)**
- Checkout mutation exists (creates order, Stripe PaymentIntent): [complete_order](file:///Users/magnetoid/coding/morph/plugins/installed/orders/graphql/mutations.py#L165-L207)
- Stripe webhooks exist: [payments/views.py](file:///Users/magnetoid/coding/morph/plugins/installed/payments/views.py)
- Idempotency middleware exists: [api/idempotency.py](file:///Users/magnetoid/coding/morph/api/idempotency.py)

**Critical functional gaps (must-fix)**
- **Totals pipeline mismatch breaks tax/shipping/promotions** during checkout:
  - Checkout computes totals with `shipping_address=` / `billing_address=` kwargs: [orders/services.py](file:///Users/magnetoid/coding/morph/plugins/installed/orders/services.py#L98-L121)
  - Tax/shipping/promotions plugins expect `address=` and (shipping) `shipping_rate_id=`:
    - [tax/app.py](file:///Users/magnetoid/coding/morph/plugins/installed/tax/app.py)
    - [shipping/app.py](file:///Users/magnetoid/coding/morph/plugins/installed/shipping/app.py)
    - [promotions/app.py](file:///Users/magnetoid/coding/morph/plugins/installed/promotions/app.py)
- Checkout page indicates JS-driven GraphQL wiring but no JS integration is present: [checkout.html](file:///Users/magnetoid/coding/morph/themes/library/dot_books/templates/storefront/checkout.html)

**Missing for enterprise**
- 3DS/SCA handling UX, retryable payment flows, partial captures, multi-tender, offline payment review.
- Tax-inclusive/exclusive pricing modes; invoice generation; fraud scoring.

### 2.4 Order Management

**Implemented**
- Order state machine, fulfillments, refunds: [orders/models.py](file:///Users/magnetoid/coding/morph/plugins/installed/orders/models.py), [orders/refunds.py](file:///Users/magnetoid/coding/morph/plugins/installed/orders/refunds.py)
- Admin order operations: [admin_dashboard/views.py](file:///Users/magnetoid/coding/morph/plugins/installed/admin_dashboard/views.py)

**Gaps**
- Warehouse workflows (bins, wave picking), SLAs, shipments tracking integrations, returns portal.

### 2.5 Inventory Tracking

**Implemented**
- Reservation/commit/release allocator: [inventory/allocator.py](file:///Users/magnetoid/coding/morph/plugins/installed/inventory/allocator.py)

**Gaps**
- Multi-warehouse, reorder points, purchase orders, backorders/preorders.

### 2.6 Shipping Integration

**Implemented**
- Flat/free/tiered quoting primitives: [shipping/services.py](file:///Users/magnetoid/coding/morph/plugins/installed/shipping/services.py)

**Gaps / bugs**
- Carrier integrations are stubs.
- Weight-tier quoting references `product.weight_kg` (field doesn’t exist): [shipping/services.py](file:///Users/magnetoid/coding/morph/plugins/installed/shipping/services.py#L75-L80)
- Checkout does not pass required hook params (see 2.3).

### 2.7 Tax Calculation

**Implemented**
- Local tax rules engine: [tax/services.py](file:///Users/magnetoid/coding/morph/plugins/installed/tax/services.py)

**Gaps / bugs**
- Tax categories reference missing `Product.tax_category_code`: [tax/models.py](file:///Users/magnetoid/coding/morph/plugins/installed/tax/models.py)
- Checkout does not pass required hook params (see 2.3).

### 2.8 Customer Account Management

**Implemented**
- Customer model + addresses, account pages: [customers/models.py](file:///Users/magnetoid/coding/morph/plugins/installed/customers/models.py), [storefront/views.py](file:///Users/magnetoid/coding/morph/plugins/installed/storefront/views.py)

**Gaps**
- Enterprise identity: SSO/SAML, B2B account hierarchies and approvals.

## 3) CMS Capabilities — Audit + Gaps

### 3.1 Content Creation Tools

**Implemented (basic)**
- Pages, blocks, menus, forms: [cms/models.py](file:///Users/magnetoid/coding/morph/plugins/installed/cms/models.py)
- Public page routing: [cms/urls.py](file:///Users/magnetoid/coding/morph/plugins/installed/cms/urls.py), [cms/views.py](file:///Users/magnetoid/coding/morph/plugins/installed/cms/views.py)

**Missing (major)**
- No rich editor (WYSIWYG) integration.
- No production-ready authoring UI (dashboard is list-only; Django admin disabled in production): [morph/urls.py](file:///Users/magnetoid/coding/morph/morph/urls.py#L45-L54), [cms/dashboard.py](file:///Users/magnetoid/coding/morph/plugins/installed/cms/dashboard.py)
- No versioning/drafts preview/diffing.
- No custom content model builder.

### 3.2 Media Management

**Implemented (scattered)**
- Product images / avatars / optional S3: [settings.py](file:///Users/magnetoid/coding/morph/morph/settings.py)

**Missing**
- Central media library (upload/browse/tag/resize/variants/foldering).

### 3.3 SEO Optimization

**Implemented**
- Meta overlay, redirects, 404 logging, sitemap/robots, llms feeds: [seo/services.py](file:///Users/magnetoid/coding/morph/plugins/installed/seo/services.py)

**CMS gap**
- CMS pages do not pass `seo_object`, so per-page overrides aren’t used: [cms/views.py](file:///Users/magnetoid/coding/morph/plugins/installed/cms/views.py)

### 3.4 Multi-language Support

**Implemented (kernel)**
- Translation overlay model + template filter: [core/i18n](file:///Users/magnetoid/coding/morph/core/i18n)

**Missing**
- Locale routing, translated slugs, translation UI, per-locale SEO.

### 3.5 Workflow Management

**Implemented (basic)**
- Page state/publish_at: [cms/models.py](file:///Users/magnetoid/coding/morph/plugins/installed/cms/models.py)

**Missing**
- Scheduled state not fully implemented in resolver.
- Editorial workflow (approvals, assignments), audit logs.

### 3.6 User Permissions

**Implemented (models exist)**
- RBAC models + helper: [rbac/models.py](file:///Users/magnetoid/coding/morph/plugins/installed/rbac/models.py)

**Missing (critical wiring)**
- Dashboard uses staff-only gates; RBAC not enforced.
- GraphQL scope checks treat staff as fully privileged: [api/graphql_permissions.py](file:///Users/magnetoid/coding/morph/api/graphql_permissions.py)

## 4) Technical Architecture Assessment

### 4.1 Scalability

**Implemented**
- Primary/replica router: [core/db_router.py](file:///Users/magnetoid/coding/morph/core/db_router.py)
- PgBouncer in compose: [docker-compose.yml](file:///Users/magnetoid/coding/morph/docker-compose.yml)

**Gaps**
- Kubernetes manifests are incomplete/inconsistent: [k8s/](file:///Users/magnetoid/coding/morph/k8s/)
- No dedicated search/read model for high-QPS catalog reads.

### 4.2 Security

**Implemented**
- Agent auth middleware, rate limiting, idempotency.

**Gaps**
- GraphQL depth/complexity limits; introspection controls.
- Secrets management (SOPS/ExternalSecrets).
- Restore workflows.

### 4.3 Performance

**Implemented**
- GraphQL query caching: [api/middleware.py](file:///Users/magnetoid/coding/morph/api/middleware.py)

**Gaps**
- CDN caching strategy; DB indexing and read model separation.

### 4.4 API Completeness

**Gaps**
- Some plugins register GraphQL but are stubs (analytics/marketing).
- No versioning strategy, developer portal, typed webhook schemas.

## 5) UX Evaluation (Storefront + Admin)

### Storefront
- Checkout/cart flows need full JS/GraphQL wiring.
- Accessibility and performance budgets are not enforced.

### Admin
- CMS authoring UI, media library, campaign builder missing.
- Some dashboards appear broken due to model mismatches (marketing, marketplace).

## 6) Mobile / PWA

Current: backend-first/headless, no official storefront SDK.

Needed: official Next.js storefront (PWA baseline), React Native starter, push notifications, offline-first cart.

## 7) Analytics & Reporting

**Implemented**
- Event capture + dashboards: [analytics/app.py](file:///Users/magnetoid/coding/morph/plugins/installed/analytics/app.py)

**Gaps**
- Analytics GraphQL is stubbed; scheduled reports and exports are missing.
- Cohort/LTV and attribution reporting needs consolidation.

## 8) Marketing Automation

**Implemented**
- Cart abandonment + transactional email hooks.

**Gaps**
- Campaign builder and ESP integrations.
- Loyalty system missing.

## 9) Marketplace

**Implemented**
- Marketplace accounting + payouts: [marketplace/models.py](file:///Users/magnetoid/coding/morph/plugins/installed/marketplace/models.py)

**Gaps**
- Vendor onboarding workflow UI.
- Dashboard mismatch likely breaks vendor list.

## 10) International Commerce

**Implemented (partial)**
- i18n overlay kernel.

**Gaps**
- Locale routing and translation workflows.
- Compliance tooling.

## 11) DevOps & Deployment

**Critical gaps**
- Backups likely fail in containers due to missing `pg_dump`: [morph_backup.py](file:///Users/magnetoid/coding/morph/core/management/commands/morph_backup.py), [Dockerfile](file:///Users/magnetoid/coding/morph/Dockerfile)
- Restore tooling/runbook missing.
- k8s manifests incomplete.

---

## Prioritized Implementation Roadmap (Feature + Engineering)

### P0 (0–2 weeks): Checkout correctness + revenue integrity
- Fix totals contract (shipping/tax/promotions) end-to-end.
- Shipping rate selection UI + propagate `shipping_rate_id`.
- Coupon usage tracking + promotion application persistence.
- Affiliate attribution: cookie → order → conversion.

Effort: 2 backend + 1 frontend for 2 weeks.
Success criteria: accurate totals + successful payments + reconciled paid orders + no broken promo/tax/shipping paths.

### P1 (2–6 weeks): Admin UX + CMS authoring
- CMS create/edit UI in dashboard + preview + publish.
- Media library MVP.
- Wire SEO meta overrides for CMS pages.
- Enforce RBAC capabilities in dashboard and GraphQL.

Effort: 2 backend + 1 full-stack + 1 designer part-time.
Success criteria: non-technical admins publish pages/media without server access.

### P2 (6–12 weeks): Read scaling + ops reliability
- Search/read model for catalog (Typesense/Elastic).
- Production-grade tracing/logging + alerts.
- Fix backups (pg_dump availability, volumes, restore tooling, encryption).
- Replace raw k8s YAML with Helm/Kustomize, include full dependencies.

Effort: 2 backend + 1 DevOps.
Success criteria: p95 read latency target met under load; RPO/RTO tested.

### P3 (3–6 months): Growth engine
- Campaign builder + segmentation + ESP integrations.
- Loyalty + referrals.
- Advanced analytics: cohorts/LTV/attribution.

Effort: 2 backend + 1 data/analytics engineer.
Success criteria: measurable uplift in repeat purchase rate and recovered revenue.

### P4 (6–12 months): Platform ecosystem
- Federation/microservices decomposition.
- Public developer portal + app marketplace.
- Enterprise: SSO/SAML, audit logs, approvals, multi-warehouse.

Effort: platform team (3–5 engineers).
