# Product Specification & Architecture (Spec)

## 1. Project Overview

- **Name:** Storefront hero slider
- **Goal:** Upgrade the homepage hero into a high-performance featured-product slider that rotates across personalized featured books with synchronized copy and cover transitions.
- **Target users:** Storefront visitors on mobile, tablet, and desktop.
- **Why now:** The current homepage hero only renders the first featured product and already references product fields the view does not fetch, leaving both merchandising range and motion polish underused.

## 2. Tech Stack & Dependencies

- **Language:** Python, Django templates, vanilla JavaScript, CSS
- **Framework:** Django storefront theme override (`dot_books`)
- **Styling:** Existing theme CSS variables and inline template styles
- **Database:** PostgreSQL in production, sqlite for isolated local tests
- **Test runner:** Django `TestCase`
- **Package manager:** pip
- **Key libraries:** Existing `seo` template tags and built-in storefront motion tokens

## 3. Data Models / Schemas

- **Entity:** Homepage hero product
  - Source: personalized `featuredProducts` GraphQL result
  - Required fields: `id`, `name`, `slug`, `shortDescription`, `category.name`, `price`, `priceStartsFrom`, `primaryImage.url`, `primaryImage.altText`
  - Constraint: first item remains the LCP-preloaded slide

## 4. Key Features & Acceptance Criteria

- [ ] **Rotating hero:** Homepage cycles through multiple featured products with coordinated media and text transitions.
  - *Acceptance:* Homepage renders layered hero slides, manual navigation works, and the hero still degrades cleanly when only one product exists.
- [ ] **Motion-safe animation:** Slider uses transform/opacity only and respects reduced-motion preferences.
  - *Acceptance:* Autoplay stops for reduced-motion users and manual navigation still updates slides instantly without layout-breaking effects.
- [ ] **Complete hero data:** View fetches the fields the hero needs for title, category, description, and price.
  - *Acceptance:* Rendered hero shows populated copy from the fetched product payload instead of blank category/description text.

## 5. Architectural Constraints

- Must stay inside the active storefront theme and storefront home view.
- Must not add a new dependency or parallel slider framework.
- Must preserve personalized featured-product ordering from `rank_for_visitor`.

## 6. Non-Functional Requirements

- **Performance:** Transitions use only `transform` and `opacity`; first hero image remains the preloaded LCP candidate.
- **Reliability:** Homepage still renders when there are zero or one featured products.
- **Accessibility:** Keyboard-accessible controls, live slide status, semantic buttons, reduced-motion support.
- **Internationalization:** Preserve existing `{% translate %}` usage and money formatting.

## 7. Security & Privacy

- **Threat model:** Public storefront visitors receive only already-public product data.
- **Data classification:** No secrets or customer data enter the hero payload.
- **Auth model:** Public anonymous access.
- **Input boundaries:** All hero content comes from internal GraphQL/catalog data and must be escaped by default template rendering.
- **Secret handling:** Not applicable.
- **Compliance:** No new privacy surface.

## 8. Observability

- **Logs:** Reuse existing storefront/browser diagnostics only; no new server logging required.
- **Metrics:** LCP candidate remains preloadable, hero control interactions remain accessible, no JS errors in slider bootstrap.
- **Traces:** Not applicable for this template-only enhancement.
- **Alerts:** Not applicable.

## 9. Out of Scope

- New CMS-managed homepage hero content model
- Video hero backgrounds
- Touch-drag gesture physics beyond button/dot navigation

## 10. Open Questions

- None for this implementation chunk.

---

## AI Agent Instructions

Read this file fully before suggesting any code implementations. Ensure all generated code aligns with the tech stack, data models, security requirements, and non-functional requirements above. Surface any conflict between this spec and the existing codebase before writing code.
