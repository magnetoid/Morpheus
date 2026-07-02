---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-02T21:17:22'
updated: '2026-07-02T21:17:22'
rules:
- id: mcp-writes-need-approval-audit-ratelimit
  pattern: plugins/installed/agent_mcp/(views|auth|dashboard)\.py
  message: 'MCP tool dispatch must keep the governance gates after scope check: requires_approval
    tools refused unless the token''s approved_tools grants it, every call/denial
    audited via core.audit, per-token rate limit. Don''t bypass _enforce_rate_limit
    / the approval block / _audit_call. (ADR: agent-write governance.)'
---

# ADR 0027: Agent-write governance: requires_approval enforced at the MCP edge via per-token grants; every tool call audited; per-token rate limits

## Context
The MCP admin surface (/mcp/admin/v1/) authenticated a Bearer token and enforced SCOPES, but nothing else: the ~58 tools declaring requires_approval=True (refunds, pricing, RBAC role grants, i18n writes, ecommerce writes) were fully executable by any correctly-scoped token; no audit row recorded which agent called which tool; there was no per-token rate limit; and stamp_order_with_agent() (verified-agent -> order.metadata.agent_id, advertised by the UCP/Trusted-Agent manifest as 'persisted on checkout') was defined but never called. The in-process agent runtime already had an approval_check gate (core/agents/runtime.py) and a core audit trail (core/audit, record_ai_decision, EU AI Act framing) — the HTTP/Bearer edge simply didn't use them. This was the #1 enterprise-readiness gap for the AI-first claim (enterprise-ai-first-plan Phase 1).

## Decision
The MCP tool-dispatch edge (plugins/installed/agent_mcp/views.py _handle_tools_call) enforces governance after scope check, before invoke: (1) APPROVAL — a requires_approval tool is refused (JSON-RPC -32030) unless the presented token's entry lists it in `approved_tools`, a per-token human grant made in the dashboard (Settings → Developer → MCP tokens → 'Approved protected tools'). Deny-by-default: legacy raw-string tokens and unlisted tools get nothing; staff dashboard sessions (no token) pass, since the human wields the same power in the UI. (2) AUDIT — every executed call writes an `agents.decision` core AuditEvent (actor=token label, tool, args capped, output summary, duration); every denial writes `mcp.tool_denied`. Audit is fail-soft (never breaks the call). (3) RATE LIMIT — per-token fixed 60s window (default 120/min, per-token override via `rate_limit_per_minute`), keyed by token hash (or client IP for sessionless), fail-open on cache outage, denials audited (-32029). (4) ATTRIBUTION — the TrustedAgentMiddleware stashes the verified agent in a thread-local; agent_mcp subscribes to ORDER_PLACED and stamps order.metadata.agent_id/agent_provider (disable-safe via the hook bus, ADR 0024). Token entry shape gains `approved_tools: list[str]` and `rate_limit_per_minute: int`.

## Consequences
External agents can no longer execute a protected write over MCP without an explicit per-token grant, and every automated action (and refusal) is now in the exportable core audit trail. Backward-compat: existing scoped tokens keep read/propose access; a token that previously could fire a protected write now needs its owner to tick the tool in the dashboard (intended tightening — flag in release notes). GraphQL agent mutations still route approval through the runtime, not this edge; a follow-up should apply the same approved_tools gate to the agent GraphQL endpoint for parity. New MCP JSON-RPC error codes: -32029 (rate limited), -32030 (approval required). Guarded by plugins/installed/agent_mcp/tests/test_governance.py.
