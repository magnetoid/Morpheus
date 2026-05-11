# Compliance — EU AI Act + GDPR

This document maps Morpheus's audit + observability primitives to
the obligations that apply to operators of an agent-native commerce
platform from **February 2026** (EU AI Act enforcement) onward.

## What Morpheus does for you

| Obligation | Where it lives | How |
|---|---|---|
| AI decision provenance (AI Act art. 12 / 13) | `core/audit/services.py:record_ai_decision` | Each personalisation, dynamic-pricing, or agent tool call writes one `agents.decision` row with agent, run id, tool, args, output, duration, model, provider |
| Append-only audit log | `core/audit/models.py:AuditEvent` | UUID PK, no update path, indexed on `(event_type, created_at)` and `(target, created_at)` |
| Agent run trace | `plugins/installed/agent_core` — `AgentRun` + `AgentStep` | Every Linda / sub-agent invocation, with per-step LLM calls + tool calls |
| Customer data export (GDPR art. 15) | Query `AuditEvent` on `actor` + `target` like `customer/<id>` | One SQL/Django query returns the full decision history |
| Trace export without PII (GDPR art. 5) | `core/observability.py:_PIIScrubberProcessor` | Email / phone / IPv4 in OTel span attributes replaced with stable SHA-256 hashes before any external exporter sees them |
| Approval gates for high-risk actions | `plugins/installed/agent_core/models.py:AgentApprovalRequest` | Plugin disables, bulk deletes, and other hard-gated tools record a row per request |

## Exporting one customer's audit trail

```python
from core.audit.models import AuditEvent

customer_id = 4711
trail = AuditEvent.objects.filter(
    target__in=[
        f'customer/{customer_id}',
        f'order/{customer_id}',
    ],
).order_by('created_at')

for row in trail:
    print(row.created_at, row.event_type, row.metadata)
```

The same query, scoped to `event_type='agents.decision'`, returns
only the AI-driven decisions affecting that customer — the subset
covered by AI Act art. 13's transparency duty.

## Pulling the audit trail for a specific model

```python
AuditEvent.objects.filter(
    event_type='agents.decision',
    metadata__model='claude-opus-4-7',
    created_at__gte='2026-01-01',
)
```

Useful for: vendor-of-record reviews after a model swap, post-hoc
analysis when a provider issues a behavior advisory.

## PII redaction in traces

If `OTEL_EXPORTER_OTLP_ENDPOINT` is set, every span hits
`_PIIScrubberProcessor.on_end` before the batch exporter. The
processor scans every string attribute and replaces matches:

- Email: `alice@example.com` → `<redacted:a1b2c3d4e5f6>`
- Phone: `+1 415 555 0100` → `<redacted:9f8e7d6c5b4a>`
- IPv4: `192.0.2.1` → `<redacted:0123456789ab>`

Hashes are deterministic (truncated SHA-256), so analytics can
still group by the same redacted token across spans without
identifying the underlying customer.

## What Morpheus does *not* do for you

- Pseudonymise customer database rows. GDPR-mandated data
  minimisation in the operational DB is the merchant's
  responsibility.
- File the AI Act conformity assessment with national authorities.
- Manage the data-protection impact assessment (DPIA). The audit
  trail is one input to it, not a substitute.

## How to disable AI logging (development only)

Set `MORPH_DISABLE_AI_AUDIT=1`. The `record_ai_decision` helper
short-circuits to a no-op. **Never** ship to production with this
flag set — the audit trail is the only artefact a regulator will
ask for.
