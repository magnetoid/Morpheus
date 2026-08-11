# Architecture — orientation

Read this *before* [CLAUDE.md](../CLAUDE.md). CLAUDE.md is the
disciplinary house rules; this file is the map.

## The two halves

```
morpheus/
├── core/                          # The kernel — small, fixed.
│   ├── hooks.py                   # Event bus. Every cross-plugin call.
│   ├── safety.py                  # Safety boundary — what AI may touch.
│   ├── self_improvement/          # The "immune system" (autonomic engine).
│   ├── agents/                    # LLM tool-use loop, provider abstraction.
│   ├── assistant/                 # Linda — the always-on operator.
│   ├── audit/                     # Append-only audit log (AI decisions).
│   ├── workflows.py               # Saga / compensation primitive.
│   ├── observability.py           # OpenTelemetry init + PII scrubber.
│   ├── i18n/                      # Translation kernel.
│   └── …
└── plugins/installed/             # 60+ plugins (live list: settings).
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
holds only the foundations: auth, the hooks bus, the i18n kernel,
audit, request lifecycle, the agent runtime, the **safety boundary**
(`core/safety.py` — the single source of truth for what AI may touch,
read by self-improvement / CI / pre-commit) and the **self-improvement
loop** (`core/self_improvement/` — the autonomic "immune system" of a
vibecoded platform; cannot be a togglable plugin). Everything else —
reviews, loyalty, markets, notifications, metafields, media, CMS, the
agent gateway, the merchant-facing `workflows` automation plugin —
lives in `plugins/installed/<name>/`.

When in doubt, it's a plugin.

> **Two things named "workflows."** `core/workflows.py` is a
> saga/compensation primitive for multi-step side-effecting flows
> (checkout, returns) — core. The `workflows` *plugin* is merchant-facing
> automation rules. Same word, different layers.

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

### Core extension point: the second-factor auth gate

Sign-in stays passwordless email-OTP in core — that is **factor one**,
always. The one place auth opens for extension is the
`AUTH_SECOND_FACTOR` **filter**
([core/hooks.py](../core/hooks.py)), fired by
[`core/auth/views.py:otp_verify`](../core/auth/views.py) *after* the
email-OTP first factor succeeds but *before* `login()` establishes the
session. A subscriber returns an `HttpResponse` (a redirect to its own
challenge view) to interpose a second factor; with no subscriber the
value stays `None` and login proceeds exactly as before.

This single core change is what lets the **`staff_mfa`** plugin add a
TOTP second factor for staff sign-in, and **`staff_sso`** (OIDC / SAML
via allauth, off by default) reuses the *same* gate from its login
adapter — allauth's `login()` doesn't fire `AUTH_SECOND_FACTOR`, so the
adapter calls `staff_mfa`'s `second_factor_response` directly, so SSO
logins honour MFA too. MFA and SSO are plugins; disabling them reverts
sign-in to single-factor email-OTP.

## The agent layer

```
core/agents/                          ← runtime (LLM loop, providers) + run-state
                                        models (AgentRun/AgentStep/ApprovalRequest,
                                        ADR 0034 — the runtime owns its state)
core/assistant/                       ← Linda (hard-coded merchant operator)
plugins/installed/agent_core/         ← runs dashboard/GraphQL, conversations,
                                        background-agent scheduler, custom agents
plugins/installed/agent_mcp/          ← MCP/UCP/Trusted-Agent gateway
plugins/installed/ai_assistant/       ← Pulse insights, embeddings, search
```

- **Linda** ([core/assistant/](../core/assistant/)) is hard-coded; her
  ~30 tools live in `core/assistant/tools/`. For parallel work she
  spawns copies of the generic **Worker** through the agents kernel
  (`delegate.spawn_workers`) — not named specialist sub-agents.
- **The kernel** ([core/agents/](../core/agents/)) ships exactly **one**
  agent: `Worker`
  ([core/agents/builtin/worker.py](../core/agents/builtin/worker.py)).
  There are no specialist agent classes — specialization is a *Skill
  bundle + caller scopes*, never a new `MorpheusAgent` subclass (a
  pre-commit hook enforces this). Provider abstraction lives in
  [core/agents/llm.py](../core/agents/llm.py): OpenAI / Anthropic /
  Ollama / Mock concretes (OpenAI-compatible base-URLs cover
  Gemini / OpenRouter).
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
├── app.py          # Plugin manifest (name, label, version, requires)
├── models.py          # Optional. Database models.
├── migrations/        # Required if models.py exists.
└── tests/             # Mandatory permission boundary tests
```

Registered in `morph/settings.py:MORPHEUS_DEFAULT_APPS`. The
[`plugin-skeleton`](../.claude/skills/plugin-skeleton/SKILL.md) skill
scaffolds the whole thing.

**Plugin crashes are isolated** — a broken `ready()` is logged and
that plugin is excluded; siblings keep loading.

**Plugin topology (non-obvious):**

- Three hubs almost everything depends on: **`catalog`**, **`orders`**,
  **`customers`**. Editing their models ripples across dozens of plugins.
- Four plugins are **protected** and cannot be disabled (disabling them
  soft-bricks the dashboard): `admin_dashboard`, `agent_core`, `rbac`,
  `customers` — enforced by `PROTECTED_PLUGINS` in
  [`core/safety.py`](../core/safety.py).
- Dependencies are declared per plugin in `app.py` (`requires`); the
  loader resolves order. No plugin declares `blocks` today.

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
