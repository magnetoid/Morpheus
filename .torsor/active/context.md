---
type: active-context
status: active
tags:
- active
links: []
created: '2026-06-24T02:15:16'
updated: '2026-06-24T02:15:16'
---

# Active Context

## Current focus
Closing the confirmed enterprise-security / agentic-commerce gaps surfaced by the 2026 competitive-analysis fact-check (docs/analysis/platform_competitive_analysis_2026.md).

## Open questions
ACP: write a spec + present forks (like MFA) before building? Forks — (a) new `agentic_checkout` plugin vs extend agent_mcp; (b) wrap the existing complete_order GraphQL mutation vs call OrderService directly; (c) where the Stripe shared_payment_token handshake lives (new payments/services/delegated_payment.py vs a stripe_gateway method). ACP was rated 'speculative until justified' in the fact-check — confirm it's the priority vs SSO or the smaller wins (cart-abandonment email drip sender, search cross-encoder reranker). Three branches await the user's own push to main: feat/staff-mfa, fix/loyalty-and-webhook-oncommit, chore/supply-chain-scanning.
