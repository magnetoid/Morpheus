# Product Specification & Architecture (Spec)

> Fill this in *before* writing code. Pillar 1 of [universal-principles.md](universal-principles.md).
> A two-line spec beats no spec — but never let the spec become longer than the implementation it describes.

## 1. Project Overview

- **Name:**
- **Goal:** What is the core purpose of this project / feature?
- **Target users:**
- **Why now:** What changed that made this worth building?

## 2. Tech Stack & Dependencies

- **Language:**
- **Framework:**
- **Styling:**
- **Database:**
- **Test runner:**
- **Package manager:**
- **Key libraries:** *(e.g., Zod, React Query, Stripe — pin versions if they matter)*

## 3. Data Models / Schemas

*(Define the core entities. Include field types, constraints, indexes. The data model decides 80% of the architecture.)*

- **Entity 1:**
  - `id`: UUID
  - `createdAt`: Timestamp
- **Entity 2:**

## 4. Key Features & Acceptance Criteria

- [ ] **Feature 1:** [description]
  - *Acceptance:* [what proves this works — a runnable test or a manual scenario]
- [ ] **Feature 2:**
  - *Acceptance:*

## 5. Architectural Constraints

*(e.g., must support 10k concurrent users, WCAG 2.2 AA, no third-party UI libraries, GDPR data residency)*

## 6. Non-Functional Requirements

- **Performance:** [latency targets, throughput, SLOs]
- **Reliability:** [availability target, retry/backoff policy, idempotency]
- **Accessibility:** [WCAG level, keyboard-only, screen reader]
- **Internationalization:** [locales, RTL, currency / date formatting]

## 7. Security & Privacy

- **Threat model:** [who would attack this, how]
- **Data classification:** [PII, financial, health, secrets — and where each lives]
- **Auth model:** [who can do what — roles, scopes, session policy]
- **Input boundaries:** [what's user-controlled, what's external-API-controlled]
- **Secret handling:** [where secrets live, rotation cadence, who has access]
- **Compliance:** [GDPR, HIPAA, SOC 2, PCI — what applies]

## 8. Observability

- **Logs:** [what gets logged, structured format, retention]
- **Metrics:** [the 3–5 metrics that prove this feature is working in prod]
- **Traces:** [where distributed-trace boundaries live]
- **Alerts:** [the conditions that should page someone]

## 9. Out of Scope

*(Just as important as scope. Listing what we are deliberately NOT building prevents scope creep mid-session.)*

- ...

## 10. Open Questions

*(Questions whose answers would significantly change the design. Resolve before starting.)*

- ...

---

## AI Agent Instructions

Read this file fully before suggesting any code implementations. Ensure all generated code aligns with the tech stack, data models, security requirements, and non-functional requirements above. Surface any conflict between this spec and the existing codebase *before* writing code.

If a section above is empty, ask the user to fill it in or explicitly mark it as not applicable. Do not assume.
