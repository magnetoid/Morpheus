# Morpheus Enterprise Benchmark Gap Report

> **Goal:** Identify all critical missing features required to build an enterprise-grade self-hosted e-commerce platform that surpasses Shopify Plus, WooCommerce Enterprise, BigCommerce Enterprise, and Adobe Commerce (Magento).
>
> **Date:** 2026-07-09
> **Scope:** Full codebase audit of `/Users/magnetoid/coding/morph/` — 104 plugins, 35 kernel subsystems, ~52 hook events.
> **Methodology:** Direct source inspection + parallel subagent audits (multi-tenancy, RBAC, security/compliance, ops/scalability, inventory/B2B/warehouse, reporting/BI/monitoring) + competitor benchmarking via web research.

---

## Executive Summary

Morpheus has a **world-class AI/agent layer** (Linda assistant, autonomous worker kernel, MCP server, self-improvement engine) and a **solid e-commerce core** (catalog, checkout, payments, inventory, subscriptions, analytics). It leads every competitor in agentic commerce infrastructure — no other platform ships an autonomous agent runtime with a self-improvement loop.

However, **5 critical blockers prevent any enterprise from adopting it today**, and **~25 high-priority gaps** mean it would lose an RFP against any of the Big Four on standard enterprise checklists:

| Category | Blocker | High | Medium | Low |
|---|---|---|---|---|
| Multi-Tenancy & Organization Model | 1 | 3 | 1 | 0 |
| RBAC & Access Control | 1 | 0 | 0 | 0 |
| Security & Compliance | 2 | 1 | 3 | 1 |
| White-Labeling & Branding | 1 | 0 | 0 | 0 |
| B2B & Wholesale | 0 | 7 | 3 | 2 |
| Inventory & Fulfillment | 0 | 3 | 2 | 2 |
| Reporting & BI | 0 | 3 | 4 | 1 |
| Operations & Monitoring | 0 | 2 | 4 | 0 |
| API & Developer Experience | 0 | 1 | 1 | 2 |
| **Total** | **5** | **20** | **18** | **8** |

The blocker list is short and surgically defined — each is a hard gate that an enterprise buyer's security/compliance/procurement checklist catches in the first 30 minutes. The high-priority list represents features that every competitor ships in their enterprise tier. The medium/low list represents competitive differentiators and "nice-to-haves" that can be sequenced.

**Unique self-hosted advantage:** No competitor can match Morpheus's combination of (1) full code access, (2) no vendor lock-in, (3) no transaction fees, (4) autonomous AI operator (Linda), and (5) agent-native commerce surfaces (MCP server, ACP). The report validates that every gap identified below is either a hard enterprise requirement not fully met by any single competitor, or a space where Morpheus can leapfrog by solving it better (cheaper than Adobe, more open than Shopify, more AI-native than all of them).

---

## Part 1: Codebase Audit — What Exists

### 1.1 Platform Scale

| Dimension | Value |
|---|---|
| Plugins in `MORPHEUS_DEFAULT_PLUGINS` | 104 |
| Plugins with persistent models | ~60 |
| Core kernel subsystems | 35 |
| Hook events | ~67 |
| Dashboard pages contributed | ~35 plugins |
| Agent tools (Linda-callable) | ~15 plugins |
| Advertising channel integrations | 8 (Google, Meta, TikTok, Pinterest, Snapchat, Microsoft, Amazon, Reddit) |
| Celery beat tasks | ~12 plugins |

### 1.2 Enterprise-Relevant Capabilities That Already Ship

These are capabilities that are often missing from open-source platforms and represent Morpheus's existing enterprise strengths:

| Capability | Status | File / Plugin |
|---|---|---|
| **Multi-channel storefronts** (StoreChannel) | Shipped | `core/models.py:95` |
| **Multi-currency / markets** | Shipped | `plugins/installed/markets/` |
| **Multi-warehouse inventory** | Shipped | `plugins/installed/inventory/models.py:14` |
| **Atomic inventory reserve/commit/release** | Shipped | `plugins/installed/inventory/services.py` |
| **Predictive stockout forecasting** | Shipped | `plugins/installed/inventory/demand_forecast.py` |
| **Stripe subscription billing** (MRR, dunning, webhooks) | Shipped | `plugins/installed/subscriptions/` |
| **GDPR consent audit trail** (Art. 7(1)) | Shipped | `plugins/installed/consent/` |
| **GDPR data export** (Art. 15) | Shipped | `plugins/installed/customers/services.py:68` |
| **GDPR anonymisation** (Art. 17) | Shipped | `plugins/installed/customers/services.py:285` |
| **SSO — OIDC + SAML 2.0** | Shipped | `plugins/installed/staff_sso/` |
| **MFA — TOTP second factor** | Shipped | `plugins/installed/staff_mfa/` |
| **Webhook reliability** (HMAC-SHA256, exponential backoff, DLQ) | Shipped | `plugins/installed/webhooks_ui/` |
| **Transactional outbox** (FOR UPDATE SKIP LOCKED) | Shipped | `core/models.py:252` |
| **API key management** (SHA-256 hashing) | Shipped | `core/models.py:178` |
| **Rate limiting** (storefront + API) | Shipped | `core/ratelimit.py` + `api/rate_limit.py` |
| **Security headers** (CSP enforcing on /dashboard/) | Shipped | `core/security_headers.py` |
| **Audit event log** | Shipped | `core/audit/models.py` |
| **OpenTelemetry tracing** | Shipped | `core/observability.py` |
| **Prometheus + Grafana dev stack** | Shipped | `docker-compose.dev.yml` |
| **RBAC models** (Role, RoleBinding, capabilities) | Shipped (models only) | `plugins/installed/rbac/models.py` |
| **B2B price lists** (PriceList + PriceListItem) | Shipped | `plugins/installed/b2b/models.py:19` |
| **B2B quotes** (Quote + QuoteLine) | Shipped (partial) | `plugins/installed/b2b/models.py:59` |
| **B2B net terms** (NetTermsAgreement) | Shipped | `plugins/installed/b2b/models.py:160` |
| **Analytics** (15 event kinds, cohorts, attribution, anomaly detection) | Shipped | `plugins/installed/analytics/` |
| **RFM segmentation** | Shipped | `plugins/installed/customers/rfm.py` |
| **Fraud rules engine** (6 rules) | Shipped | `plugins/installed/fraud_rules/` |
| **Multi-vendor marketplace** | Shipped | `plugins/installed/marketplace/` |

---

## Part 2: Enterprise Feature Assessment — Gap-by-Gap Analysis

### 2.1 Multi-Tenancy & Multi-Store Architecture

**Current state:** [StoreChannel](file:///Users/magnetoid/coding/morph/core/models.py#L95-L137) is a domain-routing + currency primitive. It is **not** a tenant boundary. There is no Organization/Tenant model. All data lives in one database with no row-level isolation.

**Competitor baseline:**
- Shopify Plus: 10 expansion stores, separate admin per store
- BigCommerce: Native multi-storefront
- Adobe Commerce: Multi-website/multi-store from one admin
- WooCommerce: WordPress Multisite (separate DB tables per site)

| Gap | Criticality | Detail |
|---|---|---|
| **No Organization/Tenant model** | **BLOCKER** | The database has zero tenant isolation. Every model (Product, Order, Customer) belongs to no tenant. An enterprise managing 3 brands in one Morpheus instance would see all 3 brands' products, orders, and customers in the same admin. |
| No data isolation (row-level security) | **BLOCKER** | No `tenant_id` column pattern, no Postgres RLS policies, no schema-per-tenant. Sharing a database across tenants is a hard "no" for any enterprise security review. |
| No per-channel admin isolation | **HIGH** | Staff members have full visibility across all StoreChannels. An admin managing Brand A can see and modify Brand B's products. |
| No per-tenant SSO configuration | **MEDIUM** | The staff_sso plugin supports exactly one IdP. An enterprise with multiple brands under separate Azure AD / Okta tenants cannot map Brand A → IdP A, Brand B → IdP B. |
| No per-tenant data residency | **MEDIUM** | No mechanism to enforce that Tenant A's PII stays in EU servers while Tenant B's stays in US servers. |

**Implementation approach:**
1. Add `Organization` model (`id`, `slug`, `name`, `settings JSON`, `is_active`).
2. Add `organization_id` FK to every tenant-owned model (Product, Order, Customer, StoreChannel, etc.) — or use Postgres RLS with `current_setting('app.organization_id')`.
3. Add middleware that resolves `organization_id` from request domain and sets it for the request lifecycle.
4. Per-organization RBAC scoping: a RoleBinding gets `organization_id`, and `has_capability()` enforces it.

**Competitor comparison:** This is the #1 blocker. Every enterprise competitor ships multi-store. Morpheus has StoreChannel (a routing primitive) but no tenant isolation. The multi-storefront plan exists at [docs/plans/multi-storefront.md](file:///Users/magnetoid/coding/morph/docs/plans/multi-storefront.md) but is still in planning, not shipped.

---

### 2.2 Role-Based Access Control (RBAC)

**Current state:** RBAC models exist ([Role](file:///Users/magnetoid/coding/morph/plugins/installed/rbac/models.py#L92-L125), [RoleBinding](file:///Users/magnetoid/coding/morph/plugins/installed/rbac/models.py#L128-L158)) with 6 built-in role templates and capability strings like `catalog:create_product`. The service layer has `has_capability()`, `grant()`, and `revoke()`.

**Critical finding:** `has_capability()` is **never called from any view, middleware, or GraphQL resolver.** All dashboard views use `@staff_member_required` as a binary gate. GraphQL treats any staff member as fully privileged ([graphql_permissions.py](file:///Users/magnetoid/coding/morph/api/graphql_permissions.py#L66-L69)). The RBAC system exists as a definition — it is **not an enforcement gate**.

| Gap | Criticality | Detail |
|---|---|---|
| **RBAC never enforced in views** | **BLOCKER** | `has_capability()` exists in `rbac/services.py:10` but is called nowhere. Every admin view uses `@staff_member_required`. Shipping RBAC as "we have role definitions" while every staff member can still do everything is a compliance failure. |

**Competitor baseline:**
- Shopify Plus: Granular staff permissions (orders, products, customers, settings, etc.) with per-store scoping
- BigCommerce: Role-based access with customizable permissions
- Adobe Commerce: ACL with resource-level permissions (view/edit/delete/create per module)
- WooCommerce: WordPress roles + capabilities system (shop_manager, etc.)

**Implementation approach:**
1. Create a `@require_capability("catalog:create_product")` decorator or middleware.
2. Add `CapabilityRequiredMixin` for class-based views.
3. Patch GraphQL `StaffOrReadOnly` to call `has_capability()` instead of assuming all staff are fully privileged.
4. Add channel-scoping to `has_capability()` — a staff member with `manage_products` on Channel A should not manage Channel B's products unless granted.

---

### 2.3 Enterprise Security & Compliance

#### 2.3.1 PII Encryption at Rest

**Current state:** PII (customer names, emails, addresses, phone numbers) is stored in **plaintext** in the database. The only field-level encryption in the codebase is in the `one_click` plugin for payment method tokens — not for PII.

| Gap | Criticality | Detail |
|---|---|---|
| **PII stored in plaintext** | **BLOCKER** | Customer names, emails, phone numbers, and addresses have no encryption at rest. This fails GDPR Art. 32 (appropriate technical measures), SOC 2 CC6.1 (logical and physical access controls), and any enterprise security review. A database backup leak exposes all customer PII in cleartext. |

**Competitor baseline:**
- Shopify Plus: Encrypted at rest (AES-256), SOC 2 Type II, PCI Level 1
- BigCommerce: Encrypted at rest, SOC 2
- Adobe Commerce: Encrypted at rest on Adobe Commerce Cloud
- WooCommerce: Dependent on hosting — self-managed encryption

**Implementation approach:**
1. Add a `FernetEncryptedField` (Django model field using `cryptography.fernet`) for PII columns.
2. Encrypt: `first_name`, `last_name`, `email` (search-by-hash), `phone`, `address_line1`, `address_line2`, `postal_code`.
3. Key management: store the Fernet key in an env var / secrets manager, not in the DB.
4. Migration: one-time encrypt-all-PII management command.

#### 2.3.2 Audit Log Immutability (SOC 2)

**Current state:** [core/audit/models.py](file:///Users/magnetoid/coding/morph/core/audit/models.py#L11-L63) has `AuditEvent` with `record()` in [core/audit/services.py](file:///Users/magnetoid/coding/morph/core/audit/services.py#L19-L55). But the table is a regular Django model — rows are mutable via the ORM, the admin, or direct SQL. There is no append-only enforcement, no tamper-evident hashing (Merkle tree / hash chain), no retention policy, and no export.

| Gap | Criticality | Detail |
|---|---|---|
| **Audit rows are mutable** | **BLOCKER** | SOC 2 requires immutable audit trails. Current `AuditEvent` rows can be UPDATE/DELETE'd by any staff member with DB access (or via `python manage.py shell`). An enterprise security auditor will reject this. |
| No tamper-evident hashing | **HIGH** | No hash chain (each row's hash includes previous row's hash) or Merkle tree. Without this, you cannot prove an audit log hasn't been tampered with. |
| No audit log export | **MEDIUM** | The observability plugin has a filterable viewer ([views.py](file:///Users/magnetoid/coding/morph/plugins/installed/observability/views.py)) but no CSV/JSON export, no SIEM forwarding, no compliance report generation. |
| No retention policy | **MEDIUM** | No automatic archival or deletion of old audit events. GDPR-compliant data lifecycle requires configurable retention. |

**Competitor baseline:**
- Shopify Plus: Immutable audit logs, SOC 2 Type II certified
- BigCommerce: Audit logs with export
- Adobe Commerce: Admin Actions Logging (immutable)
- WooCommerce: WP Activity Log plugin (third-party)

**Implementation approach:**
1. Add a database-level REVOKE UPDATE, DELETE on the `audit_auditevent` table via a migration.
2. Add a `previous_hash` field to `AuditEvent` — SHA-256 of the previous row's `(id, timestamp, actor_id, action, target_type, target_id, changes, previous_hash)`.
3. Add `audit_log_export` management command (CSV with date range filter).
4. Add a `cleanup_old_audit_events` Celery beat task (configurable retention days).

#### 2.3.3 GraphQL Security

**Current state (verified 2026-07-10):** Better than first assessed. [api/graphql_view.py](file:///Users/magnetoid/coding/morph/api/graphql_view.py#L259) ships a pre-parse `_validate_complexity()` gate: **query depth limit** (`GRAPHQL_MAX_QUERY_DEPTH`, default 10), **alias cap** (`GRAPHQL_MAX_ALIASES`, default 15), and **introspection blocking in production** (Bearer-authenticated agent clients exempted). The remaining gaps are cost analysis and pagination caps — real, but not blockers.

| Gap | Criticality | Detail |
|---|---|---|
| ~~No query depth limit~~ | ~~BLOCKER~~ **SHIPPED** | Depth (10) + alias (15) limits and prod introspection blocking run pre-parse in `graphql_view.py:_validate_complexity`. *(Original claim was wrong — corrected after code verification.)* |
| No query complexity/cost limit | **MEDIUM** | A wide query (many fields at the same level, within depth 10) can still be expensive. No per-field cost-analysis middleware exists. |
| No node-count cap | **MEDIUM** | A `products(first: 10000)` query with no pagination enforcement can still be heavy. Enforce `first`/`last` ≤ 250. |

**Implementation approach:**
1. Add query complexity analysis to the existing `_validate_complexity` pre-pass (assign cost to each field, enforce max total cost per query).
2. Enforce pagination caps: `first`/`last` cannot exceed 250 without explicit override.

#### 2.3.4 PCI DSS

**Current state:** Payment processing is fully delegated to Stripe — no card data touches Morpheus servers. This is the correct architecture. PCI DSS SAQ A (or A-EP if using Stripe.js/Elements) is achievable in the current state.

**Gap:** No SAQ documentation, no PCI DSS compliance guide, no quarterly ASV scanning setup. These are documentation/deployment gaps, not code gaps.

#### 2.3.5 Other Security Gaps

| Gap | Criticality | Detail |
|---|---|---|
| No vulnerability scanning (Trivy/Clair) | **MEDIUM** | `pip-audit` is run but results are report-only (`docs/plans/enterprise-readiness-2026-07.md`). No container image scanning in CI/CD. |
| No secrets rotation | **MEDIUM** | API keys are hashed (SHA-256) but the secret itself, once created, lives forever. No rotation policy, no expiry. |
| No security.txt | **LOW** | No `/.well-known/security.txt` for vulnerability disclosure. |

---

### 2.4 White-Labeling & Brand Customization

**Current state:** The admin dashboard hardcodes "Morpheus" in multiple places:

- Page title tag: `<title>Morpheus admin</title>` ([plugins/installed/admin_dashboard/templates/admin_dashboard/base.html](file:///Users/magnetoid/coding/morph/plugins/installed/admin_dashboard/templates/admin_dashboard/base.html#L7)). Note: `StoreSettings.store_name` already exists (`core/models.py:14`) — the fix is wiring it into the admin shell, not adding a new model.
- Sidebar header: hardcoded "Morpheus" text
- No `StoreSettings`-driven branding override

| Gap | Criticality | Detail |
|---|---|---|
| **Hardcoded "Morpheus" branding** | **BLOCKER** | An enterprise white-labeling the platform cannot change the admin dashboard branding. Every screen says "Morpheus." This fails the white-label requirement in every enterprise RFP. |

**Competitor baseline:**
- Shopify Plus: White-label checkout, custom domain, branded admin (Shopify organization branding)
- BigCommerce: White-label storefront, custom domain, branded checkout
- Adobe Commerce: Full white-label — admin, storefront, emails
- WooCommerce: Full white-label (open source, you own it)

**Implementation approach:**
1. Add `site_name`, `site_logo`, `favicon` fields to `StoreSettings`.
2. Template reads `{{ store_settings.site_name }}` instead of hardcoded "Morpheus."
3. Email templates read from a `BrandKit` contribution or `StoreSettings`.
4. Login page branding driven by StoreSettings.

---

### 2.5 B2B & Wholesale

**Current state:** The [b2b plugin](file:///Users/magnetoid/coding/morph/plugins/installed/b2b/) ships `PriceList`, `PriceListItem`, `Quote`, `QuoteLine`, `NetTermsAgreement`, and a bulk CSV order upload ([services_bulk_order.py](file:///Users/magnetoid/coding/morph/plugins/installed/b2b/services_bulk_order.py)). This is a solid start but has critical gaps.

| Gap | Criticality | Detail |
|---|---|---|
| **No purchase orders** | **HIGH** | No `PurchaseOrder` model anywhere. Enterprise B2B buyers expect to pay by PO number and receive invoices. This is a standard procurement workflow. |
| **No quote-to-order conversion** | **HIGH** | `Quote.converted_order` FK exists but the `convert_quote_to_order` service is not implemented. A customer accepts a quote but it never becomes an order. |
| **No tiered/volume pricing** | **HIGH** | `PriceListItem` is a flat per-product override. No quantity breaks ("buy 10+ = $X, buy 100+ = $Y"). This is a basic wholesale requirement. |
| **No customer-group pricing** | **HIGH** | Pricing is either per-Account (via PriceList) or product default. No "Wholesale" vs "VIP" vs "Retail" customer groups with group-level price lists. |
| **No minimum order quantities** | **HIGH** | No product-level or account-level MOQ. Wholesale buyers need "minimum order: 50 units" enforcement at the checkout level. |
| **No B2B checkout** (PO as payment, invoice-me) | **HIGH** | Checkout assumes immediate payment (Stripe). There is no "pay by invoice" or "pay by PO number" payment method for net-terms B2B buyers. |
| **No request-for-quote (RFQ)** | **HIGH** | Quotes are staff-created only. A B2B buyer cannot initiate a quote request from the storefront. |
| **B2B price resolution not in checkout flow** | **MEDIUM** | `resolve_price_for_account()` works for bulk CSV upload but is not wired into the regular checkout pricing hooks. A B2B customer browsing the storefront sees retail prices until they upload a CSV. |
| **No requisition lists** | **MEDIUM** | A B2B buyer cannot save a list of frequently-ordered products for quick reorder. |
| **No shared catalogs** | **MEDIUM** | An Account cannot have a curated subset of the full catalog ("these are the products your company can order"). |
| **No EDI / Punchout** | **LOW** | Electronic Data Interchange for automated procurement. Roadmapped for Q3 2027 earliest. |
| **No contract pricing** | **LOW** | No contract model for negotiated volume commitments. |

**Competitor baseline:**
- Adobe Commerce: Enterprise-grade B2B (company accounts, shared catalogs, negotiable quotes, requisition lists, quick order, punchout). Best-in-class.
- BigCommerce Enterprise: Strong native B2B (quote management, punchout, customer groups, price lists).
- Shopify Plus: Basic B2B (company accounts, price lists, negotiated terms) — described as "partially baked" by enterprise buyers.
- WooCommerce: Via third-party plugins (Wholesale Suite, B2BKing).

**Market opportunity:** Affordable, open-source, AI-native B2B. Adobe charges $150K-$400K for B2B. Shopify's B2B is "partially baked." There is no self-hosted platform with native B2B that an agency can sell to mid-market manufacturers at $5K-$20K/year.

---

### 2.6 Inventory & Fulfillment

**Current state:** Morpheus has one of the strongest inventory subsystems in open-source commerce — multi-warehouse, atomic reserve/commit/release, 3 allocation strategies, predictive stockout forecasting, and beat-driven low-stock alerts. This is a genuine strength.

| Gap | Criticality | Detail |
|---|---|---|
| **No warehouse transfers UI** | **HIGH** | `StockMovement` has a `transfer` movement type, but no view or service to create a transfer from Warehouse A to Warehouse B. The movement type exists but is unused. |
| **No geo-aware fulfillment routing** | **HIGH** | The allocator has 3 strategies (`single_warehouse`, `default_first`, `descending_stock`) but none are geography-aware. An order from a California customer should route to the California warehouse, not the New York one. |
| **No backorder fulfillment workflow** | **HIGH** | `ProductVariant.inventory_policy='continue'` allows backorders, but there is no automation to release backordered stock when new inventory arrives. The inventory arrives, the backorder sits unfulfilled. |
| **No dropshipping support** | **MEDIUM** | `catalog.Vendor` exists but has no supplier-specific fields (lead times, dropship capability, shipping origins). No dropship order routing, no PO generation for dropship vendors, no split fulfillment across vendors. |
| **No supplier inventory sync** | **MEDIUM** | No mechanism for external suppliers to report their available stock. Dropshipping requires knowing the supplier's current inventory. |
| **No bin/picking logic** | **LOW** | No warehouse bin model, no wave picking, no pick-list generation. |
| **No IoT/smart inventory** | **LOW** | Roadmapped as "18+ months" in the roadmap. |

**Competitor baseline:**
- Adobe Commerce: Multi-Source Inventory (MSI), multi-warehouse with source prioritization
- Shopify Plus: Multi-location inventory, fulfillment prioritization
- BigCommerce: Inventory management with backorder support
- WooCommerce: Through extensions

---

### 2.7 Enterprise Reporting & Business Intelligence

**Current state:** The [analytics plugin](file:///Users/magnetoid/coding/morph/plugins/installed/analytics/) is comprehensive for operational analytics (15 event kinds, 14+ KPIs, funnels, cohorts, multi-touch attribution, anomaly detection, predictive trends, RFM segmentation). Subscription analytics (MRR, churn, trial funnel) are also shipped. This is a strength.

**The gap is on the enterprise side:** no custom report builder, no PDF generation, no scheduled/automated reports, no BI tool connectors, no data warehouse/ETL.

| Gap | Criticality | Detail |
|---|---|---|
| **No PDF generation anywhere** | **HIGH** | Zero PDF generation in the entire codebase — no invoices, no packing slips, no shipping labels, no analytics report PDFs. The `AnalyticsExport` model has a `format=PDF` choice but no rendering code. |
| **No custom report builder** | **HIGH** | No drag-and-drop report builder, no query builder, no saved custom reports. All dashboards are pre-built. Enterprises need to create reports for their specific KPIs. |
| **No scheduled report delivery** | **HIGH** | `AnalyticsExport` has a `schedule_cron` field but no Celery task to execute scheduled exports and email them. The model exists, the runner doesn't. |
| No BI tool connectors | **MEDIUM** | No integration with Metabase, Tableau, PowerBI, or Looker. No dedicated analytics API or data export pipeline for external BI. |
| No data warehouse / ETL | **MEDIUM** | No data pipeline to export to Snowflake/BigQuery/Redshift. |
| No enterprise KPI framework | **MEDIUM** | No executive dashboard aggregating across all modules (revenue + subscriptions + marketplace + loyalty in one view). |
| No PDF invoice generation | **MEDIUM** | `SubscriptionInvoice` model exists but has no PDF rendering. Order confirmation emails are plain text. |
| No compliance report generation | **LOW** | No automated GDPR/CCPA compliance reports. |

**Competitor baseline:**
- Shopify Plus: ShopifyQL (query language), custom reports, scheduled reports
- Adobe Commerce: Magento Business Intelligence (100+ out-of-box reports), custom dashboards
- BigCommerce: Built-in analytics and reporting
- WooCommerce: Basic reports built in; advanced via plugins

---

### 2.8 Operations, Monitoring & Observability

**Current state:** OpenTelemetry tracing is shipped ([core/observability.py](file:///Users/magnetoid/coding/morph/core/observability.py)), Sentry is integrated ([core/sentry.py](file:///Users/magnetoid/coding/morph/core/sentry.py)), Prometheus + Grafana + Loki are in the dev Docker stack ([docker-compose.dev.yml](file:///Users/magnetoid/coding/morph/docker-compose.dev.yml#L44-L69)), and the ops-agent can read Prometheus and author GitOps PRs ([services/ops_agent/](file:///Users/magnetoid/coding/morph/services/ops_agent/)).

| Gap | Criticality | Detail |
|---|---|---|
| **No Django /metrics endpoint** | **HIGH** | `prometheus-client` is not in `requirements.txt`. `core/observability.py` initializes only the TracerProvider, not the MeterProvider. Django emits no Prometheus metrics (request latency, error rate, queue depth, DB connection pool stats). This is documented as a HIGH-priority gap. |
| **No system health dashboard** | **HIGH** | No built-in dashboard showing: Celery queue depth, failed task count, DB connection pool utilisation, Redis memory, cache hit rate, disk usage. An enterprise ops team needs this to run the platform. |
| No Grafana custom dashboards | **MEDIUM** | Grafana + Prometheus datasource are provisioned but no custom Morpheus dashboards are pre-built. |
| No queue/broker monitoring UI | **MEDIUM** | No visibility into Celery broker queue depth, worker count, or task success/failure rate from the admin dashboard. |
| No SLI/SLO tracking | **MEDIUM** | No error budget tracking, no service-level indicator dashboard, no SLO definition framework. |
| No alerting rules | **MEDIUM** | No pre-configured threshold alerts for infrastructure metrics (CPU > 80%, disk > 85%, error rate > 5%). |

---

### 2.9 API Reliability & Developer Experience

**Current state:** Rate limiting is solid ([core/ratelimit.py](file:///Users/magnetoid/coding/morph/core/ratelimit.py) + [api/rate_limit.py](file:///Users/magnetoid/coding/morph/api/rate_limit.py)), webhook reliability is strong (HMAC-SHA256, exponential backoff, DLQ), and the transactional outbox pattern is implemented. GraphQL API surface is extensive.

| Gap | Criticality | Detail |
|---|---|---|
| No API versioning | **MEDIUM** | No version prefix on API routes (`/api/v1/`), no deprecation headers, no versioning strategy. |
| No enterprise API SDK | **HIGH** | No generated client library (Python, JS, PHP). Enterprises integrating Morpheus into their ERP/WMS need a typed SDK. |
| No API usage analytics | **LOW** | No per-client API usage dashboard (who's calling what, how often, what's failing). |
| No GraphQL persisted queries | **LOW** | No support for persisted queries (trusted document store) for performance and security. |

---

### 2.10 Additional Gaps

| Gap | Criticality | Detail |
|---|---|---|
| No DSAR workflow state machine | **MEDIUM** | GDPR data export and anonymisation functions exist but there is no staff-facing workflow to track DSAR (Data Subject Access Request) lifecycle: received → verified → processing → completed → archived. |
| No product-level sustainability data model | **MEDIUM** | `smart_shipping` shows per-rate carbon estimates, but there is no product-level carbon footprint, no Digital Product Passport readiness, no sustainability dashboard. EU regulation is coming. |
| No live commerce | **MEDIUM** | No livestream shopping capability. Projected to reach 10-20% of all e-commerce by 2027. |
| No retail media network | **MEDIUM** | Cannot serve as an ad platform for marketplace sellers. |
| No POS integration | **LOW** | No in-store POS, no BOPIS (buy online, pick up in store), no unified inventory across physical locations. |
| No SCIM provisioning | **MEDIUM** | No automated user provisioning/deprovisioning for enterprise identity management (Okta, Azure AD). |
| No search observability | **MEDIUM** | No search analytics dashboard (zero-results queries, top searches, click-through rate on search results, conversion rate from search). The `analytics` plugin captures `search` events but there's no dedicated search-analytics surface. |

---

## Part 3: Comparative Analysis — Where Morpheus Leads, Matches, and Lags

### 3.1 Where Morpheus Leads (Competitive Advantages)

| Capability | Morpheus | Shopify Plus | Adobe Commerce | BigCommerce | WooCommerce |
|---|---|---|---|---|---|
| **Autonomous AI Agent Runtime** | Linda + Worker kernel | Sidekick (assistant only) | None | None | None |
| **MCP Server (Native)** | Shipped | Storefront-MCP only (March 2026) | None | None | None |
| **Self-Improvement Engine** | Shipped | None | None | None | None |
| **Agentic Checkout Protocol** | ACP + UCP support | UCP only | None | None | None |
| **AI Personalisation** | Multi-armed bandit + embedding similarity | Basic | Sensei product recs | None | None |
| **Full Code Access** | Yes (self-hosted) | No | No (proprietary) | No (SaaS) | Yes (GPL) |
| **No Transaction Fees** | Yes | No | No | Yes | Yes |
| **No Vendor Lock-in** | Yes | No | No | Partial | Yes |
| **GDPR Consent Audit Trail** | Art. 7(1) native | Basic | Via config | Basic | Via plugins |
| **Subscription Billing (Native)** | Stripe adapter + dunning | Via apps | Via extensions | Via extensions | Via plugins |
| **Predictive Stockout Alerts** | Shipped | Limited | MSI only | Limited | Via plugins |
| **Observability (OTel + Sentry)** | Native | Limited | Adobe-only | Limited | Via plugins |

### 3.2 Where Morpheus Matches

| Capability | Morpheus | Competitors |
|---|---|---|
| Multi-currency / markets | Shipped | All ship this |
| Multi-channel advertising | Shipped (8 platforms) | Shopify/Adobe ship; BigCommerce via Feedonomics |
| Webhook reliability | Shipped (HMAC + backoff + DLQ) | All ship webhooks |
| Rate limiting | Shipped (dual middleware) | All ship rate limiting |
| MFA (TOTP) | Shipped | All ship MFA |
| SSO (OIDC + SAML) | Shipped (single IdP) | All ship SSO (usually multi-IdP) |
| API key management | Shipped (SHA-256 hashed) | All ship API keys |
| Analytics (funnels, cohorts) | Shipped | All ship analytics |
| Product/variant management | Shipped | All ship |
| Checkout + cart | Shipped | All ship |

### 3.3 Where Morpheus Lags (Gaps vs All Competitors)

| Capability | Morpheus | All 4 Competitors |
|---|---|---|
| **Multi-tenancy / tenant isolation** | **Missing** | All ship multi-store/tenant |
| **RBAC enforcement in views** | **Definition only, never enforced** | All enforce granular permissions |
| **PII encryption at rest** | **Plaintext** | Shopify/BigCommerce/Adobe encrypt; WooCommerce depends on host |
| **Immutable audit logs** | **Mutable rows** | Shopify/Adobe ship immutable; BigCommerce has export; WooCommerce via plugins |
| **White-label admin** | **Hardcoded "Morpheus"** | All support white-label |
| **GraphQL query limits** | Depth + alias limits shipped; no cost analysis / pagination cap | All have full limits |
| **PDF generation** | **Zero** | All generate invoices/packing slips/labels |
| **Custom report builder** | **None** | Shopify (ShopifyQL), Adobe (MBI), BigCommerce (built-in) |
| **Scheduled reports** | **Model exists, no runner** | All ship scheduled reports |
| **Purchase orders** | **No model** | All ship or have plugins for POs |
| **Tiered/volume pricing** | **Flat price overrides only** | Adobe/BigCommerce ship natively; Shopify/ WooCommerce via plugins |
| **Customer-group pricing** | **None** | Adobe/BigCommerce/SaaS ship; WooCommerce via plugins |
| **B2B checkout (PO/invoice-me)** | **None** | Adobe ships; others via plugins |
| **Prometheus metrics endpoint** | **None** | All can export metrics |
| **System health dashboard** | **None** | All have admin health/status pages |
| **SCIM provisioning** | **None** | Shopify/Adobe ship; others via plugins |
| **SDK / client library** | **None** | Shopify ships SDKs; others have REST/GraphQL clients |

---

## Part 4: Gap Prioritization Matrix

### BLOCKERS (5 — cannot serve an enterprise customer without these)

These are hard gates. An enterprise security/compliance team kills the evaluation here.

| # | Gap | Rationale |
|---|---|---|
| **B1** | No Organization model / tenant isolation | Multi-tenant data isolation is the #1 enterprise requirement. Without it, every brand's data is visible to every other brand. No security team signs off. |
| **B2** | RBAC never enforced in views | "We have roles but everyone can do everything" is a compliance failure. Every competitor enforces granular permissions. |
| **B3** | PII stored in plaintext | GDPR Art. 32, SOC 2 CC6.1, and every enterprise security review require encryption at rest for PII. A DB backup leak exposes all customer data. |
| **B4** | No white-label admin | Enterprise buyers cannot ship a platform branded "Morpheus" to their staff. The admin must reflect their brand. |
| **B5** | Audit rows are mutable | SOC 2 requires immutable audit trails. *(The original B5 also cited "no GraphQL query limits" — verified wrong: depth/alias limits + prod introspection blocking already ship in `api/graphql_view.py`; the residual cost-analysis/pagination gaps are MEDIUM.)* |

### HIGH-PRIORITY (20 — would lose an RFP without these)

These are features every enterprise competitor ships. An RFP checklist catches every one.

| # | Gap | Domain | Competitor Ship? |
|---|---|---|---|
| **H1** | No purchase order system | B2B | Adobe, BigCommerce natively; Shopify/Woo via plugins |
| **H2** | No quote-to-order conversion | B2B | Adobe/BigCommerce natively |
| **H3** | No tiered/volume pricing | B2B | Adobe/BigCommerce natively |
| **H4** | No customer-group pricing | B2B | Adobe/BigCommerce natively |
| **H5** | No minimum order quantities | B2B | All via config/plugins |
| **H6** | No B2B checkout (PO as payment, invoice-me) | B2B | Adobe natively |
| **H7** | No request-for-quote (RFQ) from storefront | B2B | Adobe/BigCommerce |
| **H8** | No warehouse transfers UI | Inventory | Adobe MSI |
| **H9** | No geo-aware fulfillment routing | Inventory | Shopify multi-location, Adobe MSI |
| **H10** | No backorder fulfillment workflow | Inventory | BigCommerce, Adobe |
| **H11** | No PDF generation (invoices, labels) | Reporting | All |
| **H12** | No custom report builder | Reporting | Shopify (ShopifyQL), Adobe (MBI) |
| **H13** | No scheduled report delivery | Reporting | All |
| **H14** | No Django /metrics endpoint (Prometheus) | Ops | All can export |
| **H15** | No system health dashboard | Ops | All |
| **H16** | No enterprise API SDK | DX | Shopify ships SDKs |
| **H17** | Per-channel admin isolation | Multi-tenancy | All via multi-store |
| **H18** | Audit log tamper-evident hashing | Security | SOC 2 requirement |
| **H19** | B2B price resolution in checkout flow | B2B | Embedded bug — `resolve_price_for_account()` works for CSV but not checkout |
| **H20** | No requisition lists | B2B | Adobe natively |

### MEDIUM-PRIORITY (18 — competitive gaps, not RFP-killers)

| # | Gap | Domain |
|---|---|---|
| **M1** | No BI tool connectors (Metabase, Tableau, PowerBI) | Reporting |
| **M2** | No data warehouse / ETL pipeline | Reporting |
| **M3** | No audit log export (CSV/JSON) | Security |
| **M4** | No compliance report generation | Security |
| **M5** | No DSAR workflow state machine | Compliance |
| **M6** | No SCIM provisioning | Identity |
| **M7** | No per-tenant SSO (multi-IdP) | Multi-tenancy |
| **M8** | No per-tenant data residency | Multi-tenancy |
| **M9** | No Grafana custom dashboards | Ops |
| **M10** | No queue/broker monitoring UI | Ops |
| **M11** | No SLI/SLO tracking | Ops |
| **M12** | No alerting rules for infrastructure metrics | Ops |
| **M13** | No dropshipping support | Inventory |
| **M14** | No supplier inventory sync | Inventory |
| **M15** | No product sustainability data model | Catalog |
| **M16** | No live commerce | Channels |
| **M17** | No retail media network | Monetisation |
| **M18** | No search analytics dashboard | Analytics |

### LOW-PRIORITY (8 — roadmap items, not urgent)

| # | Gap | Domain |
|---|---|---|
| **L1** | No API versioning strategy | DX |
| **L2** | No API usage analytics | DX |
| **L3** | No GraphQL persisted queries | DX |
| **L4** | No EDI / Punchout | B2B |
| **L5** | No contract pricing model | B2B |
| **L6** | No bin/picking logic | Inventory |
| **L7** | No IoT/smart inventory | Inventory |
| **L8** | No POS/in-store integration | Channels |

---

## Part 5: Implementation Roadmap

### Phase 1: Unblock Enterprise Adoption (BLOCKERS) — Q3 2026

**Goal:** Pass an enterprise security/compliance review in 30 minutes.

| # | Blocker | Implementation | Est. Effort |
|---|---|---|---|
| B1 | Organization model + tenant isolation | Add `Organization` model, `organization_id` FK to core models, request-lifecycle middleware, Postgres RLS policies | 2-3 weeks |
| B2 | RBAC enforcement | `@require_capability()` decorator, `CapabilityRequiredMixin`, patch GraphQL `StaffOrReadOnly` to call `has_capability()` | 1-2 weeks |
| B3 | PII encryption at rest | `FernetEncryptedField` for PII columns, encrypt-all management command, key management | 1 week |
| B4 | White-label admin | `StoreSettings.site_name`/`site_logo`, template updates to read from settings | 3 days |
| B5a | Immutable audit log | DB-level REVOKE UPDATE/DELETE, `previous_hash` chain, retention policy | 1 week |
| B5b | GraphQL cost limits (depth/alias already shipped) | Complexity/cost middleware + pagination caps on top of existing `_validate_complexity` | 2 days |

**Total Phase 1:** ~6-8 weeks. After this phase, Morpheus passes an enterprise security checklist.

### Phase 2: Win the RFP (HIGH-PRIORITY) — Q4 2026 - Q1 2027

**Goal:** Match or exceed the feature set of every competitor's enterprise tier.

**Batch A — B2B Suite** (6-8 weeks):
- H1: Purchase order model + workflow
- H2: Quote-to-order conversion service
- H3-H5: Tiered pricing, customer-group pricing, MOQ
- H6-H7: B2B checkout (PO/invoice-me), RFQ from storefront
- H19: Wire `resolve_price_for_account()` into checkout pricing hooks
- H20: Requisition lists

**Batch B — Inventory/Logistics** (4-5 weeks):
- H8: Warehouse transfers UI
- H9: Geo-aware fulfillment routing
- H10: Backorder fulfillment workflow

**Batch C — Enterprise Reporting** (4-5 weeks):
- H11: PDF generation pipeline (WeasyPrint or ReportLab)
- H12: Custom report builder (basic: save filter + date range as named report)
- H13: Scheduled report runner (Celery beat task)

**Batch D — Operations & DX** (3-4 weeks):
- H14: Django Prometheus metrics endpoint (`django-prometheus`)
- H15: System health dashboard (Celery queues, DB pool, Redis, disk)
- H16: OpenAPI schema generation + SDK generation pipeline
- H17: Per-channel admin isolation (scoped querysets based on RoleBinding.channel)
- H18: Audit log hash chain

**Total Phase 2:** ~17-22 weeks. After this phase, Morpheus wins RFPs against Shopify Plus and BigCommerce Enterprise. Adobe Commerce still wins on B2B depth.

### Phase 3: Leapfrog (MEDIUM-PRIORITY) — Q2-Q3 2027

**Goal:** Add features that no single competitor offers, making Morpheus the clear choice for self-hosted enterprise.

- M1-M2: BI tool connectors + data warehouse export
- M3-M5: Audit export, compliance reports, DSAR workflow
- M6-M7: SCIM provisioning, multi-IdP SSO
- M13-M14: Dropshipping support
- M16: Live commerce plugin
- M17: Retail media network for marketplace sellers
- M18: Search analytics dashboard

### Phase 4: Moat Deepening (LOW-PRIORITY) — Q4 2027+

- L1: API versioning (v1 → v2)
- L4: EDI/Punchout for large B2B procurement
- L8: POS integration (likely partnership)

---

## Part 6: Validation — Unique Self-Hosted Enterprise Advantages

### 6.1 What No Competitor Can Match

Every gap identified above exists in comparison to at least one competitor. But Morpheus has structural advantages that **no competitor can replicate** without fundamentally changing their architecture:

1. **Autonomous AI agent runtime** — Linda can prepare changes for merchant approval, run multi-step operations, and self-improve. Shopify Sidekick is an assistant, not autonomous. No other competitor has anything comparable.

2. **MCP server + agentic commerce protocol** — Morpheus ships an MCP server exposing tools to AI agents. Shopify retrofitted storefront-MCP in March 2026. The others have nothing. This is the protocol layer for the agentic commerce transition (McKinsey projects $3-5 trillion redirected through agentic commerce by 2030).

3. **Self-improvement loop** — The platform can audit its own code quality, track upstream drift in vendored dependencies, and auto-fix lint/type issues. No competitor ships a self-improving platform.

4. **Zero vendor risk** — Self-hosted means no account holds (Shopify's 1.5/5 Trustpilot score is driven by this), no price changes, no deprecation without consent, no rug-pull relicensing.

5. **Cost at scale** — No transaction fees. No app subscription compounding. Fixed infrastructure cost regardless of GMV. At $1M+/month GMV, the cost advantage over Shopify Plus is 6-7 figures annually.

6. **Full observability** — You own the OpenTelemetry data, the Sentry instance, the Prometheus metrics. No black-box "trust us it's up" from a SaaS vendor.

### 6.2 The Gap That Only Morpheus Can Fill

The competitive research identifies one gap that **no platform fills today**: an **affordable, open-source, AI-native, enterprise-grade e-commerce platform with both a Shopify-grade merchant admin and a real AI operator**.

- Medusa/Saleor/Vendure: Developer-first OSS, no batteries-included merchant admin
- WooCommerce: Batteries-included incumbent, but shrinking (-11% YoY), no AI-native architecture
- Shopify Plus: Great admin + AI assistant, but proprietary, expensive, and vulnerable to account holds
- Adobe Commerce: Enterprise-grade B2B, but $150K-$400K TCO and complex to run
- BigCommerce: Strong headless + B2B, but proprietary SaaS

Morpheus, post-Phase-2, fills the middle: Shopify-grade admin, autonomous AI operator, native B2B, self-hosted, open-source, no transaction fees, no lock-in. That platform does not exist in the market today.

---

## Part 7: What Morpheus Already Does Better Than All Competitors

This section exists to prevent the report from reading as purely negative. Morpheus ships capabilities that no competitor matches:

| Capability | Status | Competitor Gap |
|---|---|---|
| **Agent Runtime** (Linda + Worker kernel) | Shipped — `core/agents/`, `plugins/installed/agent_core/` | Shopify: Sidekick (assistant only). Adobe: None. BigCommerce: None. WooCommerce: None. |
| **MCP Server** | Shipped — `plugins/installed/agent_mcp/` | Shopify: Storefront-MCP only (March 2026 retro-fit). Others: None. |
| **Self-Improvement Engine** | Shipped — `plugins/installed/self_improvement/` | None have this. |
| **AI Personalisation** (bandit + embeddings) | Shipped — `plugins/installed/personalisation/`, `plugins/installed/dynamics/` | Shopify: Basic. Adobe: Sensei product recs. BigCommerce: None. WooCommerce: None. |
| **GDPR Art. 7(1) Consent Trail** | Shipped — `plugins/installed/consent/` | Most: Basic consent. Morpheus: timestamped, per-category, IP-hashed, audit-ready. |
| **Predictive Stockout Alerts** | Shipped — `plugins/installed/inventory/demand_forecast.py` | Shopify: Limited. Adobe: MSI only (no prediction). Others: Via plugins. |
| **Atomic Multi-Warehouse Inventory** | Shipped — `plugins/installed/inventory/services.py` (`select_for_update` + `transaction.atomic`) | Most have inventory, but with varying atomicity guarantees. |
| **Multi-Touch Attribution (5 models)** | Shipped — `plugins/installed/analytics/services_attribution.py` | Shopify: Via analytics. Others: Limited or via plugins. |
| **Anomaly Detection** (z-score, notifications) | Shipped — `plugins/installed/analytics/services_anomaly.py` | Most: Via plugins or external tools. |
| **Webhook DLQ + Exponential Backoff** | Shipped — `plugins/installed/webhooks_ui/` | All ship webhooks, but DLQ depth varies. |
| **Transactional Outbox** (`FOR UPDATE SKIP LOCKED`) | Shipped — `core/models.py:252`, `core/tasks.py` | Not all ship this pattern. |

---

## Appendix A: File Reference Index

| File | What It Contains |
|---|---|
| `core/models.py` | StoreChannel, ProductChannelListing, APIKey, OutboxEvent, WebhookEndpoint, StoreSettings |
| `core/audit/models.py` | AuditEvent model (mutable — needs hardening) |
| `core/audit/services.py` | `record()` service, `record_ai_decision()` |
| `core/security_headers.py` | CSP (enforcing on /dashboard/, report-only on storefront), Permissions-Policy |
| `core/ratelimit.py` | Storefront rate limiting with path-prefix rules |
| `api/rate_limit.py` | GraphQL/API rate limiting (100/600 req/min) |
| `api/graphql_permissions.py` | StaffOrReadOnly (treats all staff as fully privileged — needs RBAC enforcement) |
| `core/observability.py` | OpenTelemetry tracing (TracerProvider only, no MeterProvider) |
| `core/tasks.py` | Webhook dispatch, OutboxEvent processing |
| `plugins/installed/rbac/models.py` | Role, RoleBinding, 6 built-in role templates |
| `plugins/installed/rbac/services.py` | `has_capability()` — defined but never called from views |
| `plugins/installed/inventory/models.py` | Warehouse, StockLevel, StockMovement, BackInStockSubscription, StockoutAlert |
| `plugins/installed/inventory/services.py` | Atomic reserve/commit/release, multi-warehouse allocator |
| `plugins/installed/inventory/demand_forecast.py` | Predictive stockout forecasting, overstock detection |
| `plugins/installed/inventory/allocator.py` | 3 allocation strategies (single_warehouse, default_first, descending_stock) |
| `plugins/installed/b2b/models.py` | PriceList, PriceListItem, Quote, QuoteLine, NetTermsAgreement |
| `plugins/installed/b2b/services.py` | `resolve_price_for_account()`, `create_quote()`, `send_quote()` |
| `plugins/installed/b2b/services_bulk_order.py` | CSV bulk order upload with price resolution |
| `plugins/installed/subscriptions/models.py` | Plan, Subscription, SubscriptionInvoice |
| `plugins/installed/subscriptions/billing/stripe_adapter.py` | Stripe billing adapter (sync, start, cancel, pause, resume) |
| `plugins/installed/subscriptions/analytics.py` | MRR, churn, trial funnel, plan breakdown |
| `plugins/installed/analytics/models.py` | AnalyticsSession, AnalyticsEvent, DailyMetric, FunnelDefinition, AdSpendSnapshot |
| `plugins/installed/analytics/services.py` | 14+ computed KPIs, predictive trends |
| `plugins/installed/analytics/services_cohorts.py` | Weekly cohort retention (3 metrics, 12 periods) |
| `plugins/installed/analytics/services_attribution.py` | 5 attribution models (last_touch, first_touch, linear, time_decay, position_based) |
| `plugins/installed/analytics/services_anomaly.py` | Z-score anomaly detection on revenue/orders/sessions/conversion |
| `plugins/installed/customers/rfm.py` | RFM segmentation (champions, loyal, potential, at_risk, lost, new) |
| `plugins/installed/customers/services.py` | GDPR Art. 15 data export, Art. 17 anonymisation |
| `plugins/installed/consent/models.py` | GDPR Art. 7(1) consent audit trail with IP hashing |
| `plugins/installed/staff_sso/services.py` | OIDC + SAML 2.0 SSO with MFA gate |
| `plugins/installed/staff_mfa/services.py` | TOTP second factor, `second_factor_response()` |
| `plugins/installed/webhooks_ui/models.py` | WebhookDelivery with DLQ, 7-attempt backoff |
| `plugins/installed/webhooks_ui/services.py` | Webhook dispatch with HMAC-SHA256 signing |
| `plugins/installed/admin_dashboard/templates/admin_dashboard/base.html` | Hardcoded "Morpheus" branding (lines 7, 905, 906) |
| `docs/plans/multi-storefront.md` | Multi-storefront plan (not yet shipped) |
| `docs/plans/enterprise-readiness-2026-07.md` | Enterprise readiness gap doc (PII plaintext, pip-audit, container scanning) |
| `docs/analysis/platform_competitive_analysis_2026.md` | Competitive analysis vs Shopify/Adobe/BigCommerce/WooCommerce |
| `docs/analysis/platform_analysis_and_feature_proposals_2026.md` | 7 feature proposals with prioritization |

---

*Report compiled from direct codebase inspection of 104 plugins, 35 kernel subsystems, ~67 hook events; parallel subagent audits of security/compliance, multi-tenancy/RBAC, ops/scalability, inventory/B2B/warehouse, and reporting/BI/monitoring; competitor benchmarking via existing platform research docs and web research.*
