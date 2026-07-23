# Compliance — EU AI Act + GDPR

This document maps Morpheus's audit + observability primitives to
the obligations that apply to operators of an agent-native commerce
platform. Key dates: GPAI duties since **Aug 2025**; **Art. 50
transparency (chatbot disclosure + AI-content marking) is effective
Aug 2, 2026**; high-risk (Annex III) duties land **Aug 2026 → likely
Dec 2027** (the Digital Omnibus delay, not yet formally adopted, so
treat Aug 2026 as binding).

## What Morpheus does for you

| Obligation | Where it lives | How |
|---|---|---|
| AI decision provenance (AI Act art. 12 / 13) | `core/audit/services.py:record_ai_decision` | Each personalisation, dynamic-pricing, or agent tool call writes one `agents.decision` row with agent, run id, tool, args, output, duration, model, provider |
| Append-only audit log | `core/audit/models.py:AuditEvent` | UUID PK, no update path, indexed on `(event_type, created_at)` and `(target, created_at)` |
| Agent run trace | `plugins/installed/agent_core` — `AgentRun` + `AgentStep` | Every Linda / sub-agent invocation, with per-step LLM calls + tool calls |
| Customer data export (GDPR art. 15) | Query `AuditEvent` on `actor` + `target` like `customer/<id>` | One SQL/Django query returns the full decision history |
| Trace export without PII (GDPR art. 5) | `core/observability.py:_PIIScrubberProcessor` | Email / phone / IPv4 in OTel span attributes replaced with stable SHA-256 hashes before any external exporter sees them |
| Approval gates for high-risk actions | `plugins/installed/agent_core/models.py:AgentApprovalRequest` | Plugin disables, bulk deletes, and other hard-gated tools record a row per request |
| AI-disclosure on chat surfaces (AI Act art. 50(1)) | `core/templatetags/morph.py:ai_disclosure` + `AI_SURFACE_DISCLOSURE` filter | `{% ai_disclosure %}` renders a mandatory "you're talking to an AI" label inside every conversational AI surface; the default is a core legal floor, gdpr customises the wording |

## Art. 50 — transparency ("you're talking to an AI")

**50(1) — chatbot disclosure.** Any surface that lets a shopper
*converse with an AI* must say so. Morpheus ships the disclosure as a
**core** tag, `{% ai_disclosure surface="…" %}`
(`core/templatetags/morph.py`), rendered *inside* each conversational
surface's own template. The wording is a legal-floor default in core —
it can't be removed by disabling a plugin — and the `gdpr` plugin may
replace it with merchant copy through the `AI_SURFACE_DISCLOSURE`
filter (disable gdpr → the core default still shows). Disabling the
*surface* plugin removes chat and label together, which is correct.

*Current state (2026-07):* the only shipped conversational surface is
`ai_stylist`, which is **dormant** (its `contribute_storefront_blocks`
returns `[]` pending a finished, rate-limited backend). The disclosure
is already wired into its widget header, so the surface is
compliant-by-construction the moment it is mounted. The live `crm`
"Chat with us" widget routes to **human staff**, not AI, so 50(1) does
not apply to it today.

**50(2)/(4) — AI-generated content marking.** Morpheus auto-writes
product descriptions via an agent workflow
(`ai_assistant.tasks.generate_product_description`). Every such write
already produces an `agents.decision` provenance row
(`record_ai_decision`, art. 12/13). We do **not** yet stamp a
per-object, render-time "AI-generated" marker on the product: the write
is agent-mediated (no single write-point) and commercial product copy
is not "text published to inform the public on matters of public
interest" under 50(4), so it is outside the hard bright line. A
visible "AI-assisted" affordance is tracked as a good-practice
follow-up (see `docs/plans/ai-commerce-strategy-2026-2031.md`,
Horizon 2 — C2PA content provenance).

## The AI Act evidence export (one click)

The raw `AuditEvent` queries below are the primitive; the merchant-facing
export is built on them. **Dashboard → Linda → AI Act evidence**
(`/dashboard/apps/agent_core/compliance/`, staff-only) shows the trail of
automated AI decisions (art. 12/13) and human approvals for a date window and
downloads it as CSV. The same report is scriptable:

```bash
python manage.py export_ai_act_report --days 90 --format csv > evidence.csv
python manage.py export_ai_act_report --format json
```

Both the page and the command share one builder
(`agent_core/compliance.py:build_ai_act_report`) — decisions, approvals, a
per-tool/per-model summary, and the active guardrail config — so they never
drift. It lives in `agent_core` (a PROTECTED plugin, so the compliance surface
can't be disabled); the data it reads is all core/agent-owned.

## Agent guardrails (the enforced knobs)

The report's `guardrails` section is not decorative — it reflects live limits a
merchant sets under **Settings → Agent guardrails** (agent_core's settings
panel) and Morpheus enforces:

| Knob | Enforced where | On breach |
|---|---|---|
| **Pause all agents** (kill switch) | `core/agents/runtime.py` (delegated runs, re-checked each step) + `core/assistant/runtime.py` (Linda) | a delegated run fails `agents_paused`; Linda declines gracefully (never a stack trace) |
| **Max agent runs / day** | `core/agents/runtime.py`, once at run start | the run fails `run_cap_exceeded` before any model call |
| **Max estimated spend / day (USD)** | same | the run fails `spend_cap_exceeded` — *best-effort*, see the caveat below |
| **Max price change / action (%)** | `catalog/agent_tools.py:products.update_price` | the tool raises; the price is unchanged |
| **Max refund / action** | `orders/agent_tools.py:orders.refund` | the tool raises after the hard gate but before any charge |

Every knob is **off by default** (kill switch off, every cap `0` = unlimited),
so an unconfigured store behaves exactly as before. All reads funnel through
`core/agents/guardrails.py`, which reads the agent_core config **cross-process
fresh** (a celery worker must see a switch a merchant just flipped from the web
dashboard).

**Caveat — the USD spend cap is best-effort.** It sums *estimated* model cost
(`core/agents/pricing.py`), which is `$0` for any model without a known price
(self-hosted / unpriced — the production model today is one). For a hard,
model-independent ceiling use **Max agent runs / day**; the USD cap only bites
merchants on a priced provider.

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
