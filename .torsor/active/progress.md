---
type: progress
status: active
tags:
- active
links: []
created: '2026-06-24T02:15:16'
updated: '2026-06-24T02:15:16'
---

# Progress

Fact-checked the competitive doc against the codebase: ~8 shipping subsystems were mislabeled missing/partial/planned (funnel analytics, AI cost tracking, server-side attribution, zero-party capture, payment tokenization, hybrid search, UCP/A2A manifests, ai_stylist v1.0.0); confirmed-real gaps are MFA, SSO, ACP, native wallets, broader gateways. SHIPPED staff MFA v0.2.7 (ADR just recorded; plugin staff_mfa + one core AUTH_SECOND_FACTOR hook; 16 tests pass; commit b656e0b on feat/staff-mfa, NOT pushed). Scoped ACP next: Explore survey says thin ~150-200 LOC plugin, ~80% reuse — acp.json alongside agent_mcp's existing /.well-known/ucp.json+agent.json, reuse OrderService.create_from_cart / complete_order mutation, reuse agent_mcp Bearer+scopes, reuse inventory StockLevel; only NEW piece is a Stripe shared_payment_token (delegated payment) method on the payments gateway. Zero prior ACP code in repo.
