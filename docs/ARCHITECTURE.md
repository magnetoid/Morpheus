# Architecture — orientation

Read this *before* [CLAUDE.md](../CLAUDE.md). CLAUDE.md is the
disciplinary house rules; this file is the map.

## The two halves

```
morpheus/
├── core/                          # The kernel — small, fixed.
│   ├── hooks.py                   # Event bus. Every cross-plugin call.
│   ├── agents/                    # LLM tool-use loop, provider abstraction.
│   ├── assistant/                 # Linda — the always-on operator.
│   ├── audit/                     # Append-only audit log (AI decisions).
│   ├── observability.py           # OpenTelemetry init + PII scrubber.
│   ├── i18n/                      # Translation kernel.
│   └── …
└── plugins/installed/             # 47 plugins, each isolated.
    ├── catalog/                   # Products, variants, categories.
    ├── orders/                    # Orders + cart.
    ├── checkout/                  # Stripe + payment gateways.
    ├── agent_mcp/                 # MCP/UCP/Trusted Agent gateway.
    ├── ai_assistant/              # Pulse insights + brand voice + embeddings.
    ├── inventory/                 # Stock + Redis fast-path.
    ├── webhooks_ui/               # Subscription + outbox + DLQ + replay.
    └── …
```

**Architectural compass:** *features ship as plugins, not core.* Core
holds only the foundations (auth, hooks bus, i18n kernel, audit,
request lifecycle, agent runtime). Everything else — reviews,
loyalty, markets, notifications, workflows, metafields, media, CMS,
the agent gateway — lives in `plugins/installed/<name>/`.

When in doubt, it's a plugin.

## The hook bus

`core/hooks.py` is how plugins communicate. **Never import one
plugin from another's models or views directly.**

```python
# In core (publisher):
hooks.fire('order.paid', order=order)

# In any plugin (subscriber, wired in apps.py:ready()):
self.register_hook('order.paid', self.on_order_paid, priority=5)
```

Hooks are synchronous within a single request — handlers run in the
process that fired them. For async fanout, the
[`webhooks_ui`](../plugins/installed/webhooks_ui/) plugin writes an
Outbox row in the same DB transaction and ships it via Celery with
HMAC-SHA256 signing + exponential backoff + DLQ.

## The agent layer

```
core/agents/                          ← runtime (LLM loop, providers)
core/assistant/                       ← Linda (hard-coded merchant operator)
plugins/installed/agent_core/         ← AgentRun, AgentStep, custom agents
plugins/installed/agent_mcp/          ← MCP/UCP/Trusted-Agent gateway
plugins/installed/ai_assistant/       ← Pulse insights, embeddings, search
```

- **Linda** ([core/assistant/](../core/assistant/)) is hard-coded; her
  ~30 tools live in `core/assistant/tools/`. She delegates to
  sub-agents registered via `agent_core` for diagnostics + ops.
- **The kernel** ([core/agents/](../core/agents/)) is a peer of
  `core/hooks` and `plugins/` — provider abstraction (OpenAI,
  Anthropic, Gemini, OpenRouter, Ollama, Mock), versioned prompts,
  trace.
- **Every LLM tool call** that affects a customer should record one
  `agents.decision` row via
  [`core.audit.services.record_ai_decision`](../core/audit/services.py) —
  EU AI Act art. 12 + 13 expect the trail. See
  [`docs/COMPLIANCE.md`](COMPLIANCE.md).
- **External AI clients** reach Morpheus through the MCP cluster:
  `/mcp/{storefront,cart,checkout,admin}/v1/`. See
  [`docs/AGENT_PROTOCOLS.md`](AGENT_PROTOCOLS.md).

## Plugin contract

Every plugin in `plugins/installed/<name>/` has:

```
<name>/
├── apps.py            # AppConfig (+ ready() for signal/hook wiring)
├── plugin.py          # Plugin manifest (name, label, version, requires)
├── models.py          # Optional. Database models.
├── migrations/        # Required if models.py exists.
└── tests/             # Mandatory permission boundary tests
```

Registered in `morph/settings.py:MORPHEUS_DEFAULT_PLUGINS`. The
[`plugin-skeleton`](../.claude/skills/plugin-skeleton/SKILL.md) skill
scaffolds the whole thing.

**Plugin crashes are isolated** — a broken `ready()` is logged and
that plugin is excluded; siblings keep loading.

## Request lifecycle

```
Cloudflare (Web Bot Auth)
   ↓ X-Verified-Agent-* headers
Plesk vhost → Coolify Traefik → web container
   ↓
Django middleware stack:
   - request_id (uuid attached to every log line)
   - sentry / observability spans
   - market resolution (per-country pricing/currency)
   - TrustedAgentMiddleware (attaches request.trusted_agent)
   - auth / session
   ↓
Routing:
   - /                   → storefront
   - /dashboard/         → admin
   - /graphql/           → GraphQL API
   - /mcp/<cluster>/v1/  → MCP JSON-RPC
   - /.well-known/*      → discovery manifests
   - /webhooks/<topic>/  → inbound webhooks
```

## Key reference files when working in this repo

| File | Why you'd open it |
|---|---|
| [`core/hooks.py`](../core/hooks.py) | Event bus internals |
| [`core/agents/__init__.py`](../core/agents/__init__.py) | Agent runtime entry |
| [`core/assistant/runtime.py`](../core/assistant/runtime.py) | Linda's main loop |
| [`core/audit/services.py`](../core/audit/services.py) | `record()` + `record_ai_decision()` |
| [`morph/settings.py`](../morph/settings.py) | Plugin registry, middleware order |
| [`plugins/installed/agent_mcp/views.py`](../plugins/installed/agent_mcp/views.py) | MCP JSON-RPC dispatcher |
| [`plugins/installed/inventory/services.py`](../plugins/installed/inventory/services.py) | Stock reservation contract |

## See also

- [PLUGIN_DEVELOPMENT.md](PLUGIN_DEVELOPMENT.md) — the full plugin
  development guide. Read this when writing a real plugin.
- [SKILLS.md](SKILLS.md) — catalog of automation skills.
- [COMPLIANCE.md](COMPLIANCE.md) — EU AI Act + GDPR mapping.
- [AGENT_PROTOCOLS.md](AGENT_PROTOCOLS.md) — MCP / UCP / Trusted
  Agent integration guide.
- [`CLAUDE.md`](../CLAUDE.md) — house rules.
