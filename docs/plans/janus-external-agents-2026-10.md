# External agents talk to Janus; the API page becomes a connection hub (2026-10-10)

Owner, 2026-10-10: "expose Janus over MCP and GraphQL, so that external agents like
Hermes or OpenClaw can talk with Janus. Janus needs to be the most powerful part of
the ecommerce." Also: "add 'copy connection code' on an API key, where I copy
everything the other party needs to know; the JSON sections below are not needed;
maybe add some other options." Rule: Torsor ADR 0039 (Janus is the brain; every door
runs one gate chain; only the merchant's own message is consent).

## What was found (code maps, 2026-10-10)

- A Janus turn is `Assistant().stream(message, conversation_key, context)`
  (`core/assistant/runtime.py`). It stores the message as `role='user'`, checks the
  guardrails, mints a signed turn token (`lt1.`, `core/assistant/turn_identity.py`) for
  a staff user and runs the Janus subprocess, which calls `/mcp/admin/v1/` with that
  token. The edge (`agent_mcp/linda_turn.py`) runs `gates.gate_reason` per tool call.
- **Consent hazard.** The consent kernel treats the newest stored `role='user'`
  message as the merchant. Only automation keys (`:auto:`) are refused consent. An
  external agent's message stored the same way would approve Janus's proposals.
- A turn can last up to 300 s. A blocking MCP or GraphQL call would hold a gunicorn
  thread that Janus's own MCP callbacks need, and proxies cut idle requests at ~100 s.
  Automations already run turns from Celery with `mcp_public: True`.
- MCP tokens (`PluginConfig['agent_mcp']['public_keys']`) record no owner, write no
  audit row on create/revoke/permission changes, and a new token has no scope keys, so
  it is a wildcard on MCP and GraphQL (`DEFAULT_SCOPES` is unused).
- The "Approved protected tools" checklist is always empty (`_approval_tools()` reads
  the legacy read-only list), and every permissions save writes `approved_tools=[]`.
- `POST /graphql/` refused every cookie-less Bearer request with Django's CSRF 403
  (live on every store). Fixed in v0.94.0 with `csrf_exempt_for_bearer`.

## Design

**One principle: Janus never does more for an external agent than its token could do
itself.** The token is the merchant's prior, explicit grant; nothing else is consent.

1. **Principal and keys.** An external conversation is keyed
   `ext:<token id>:chat:<hex>` and belongs to that token: only the same token can
   continue it or read its turns. `gates.is_external_key()` lives next to
   `is_automation_key()`. The turn runs as the shared `mcp-service` staff user in
   `general` mode; the turn token carries the token id as its principal (`'e'`).
2. **Gates (one copy, `core/assistant/gates.py`).** On an external key the consent
   kernel is never consulted, so no message can approve anything. A tool that needs
   consent is allowed only when the token could call it directly: its scopes are
   inside the token's MCP scopes (the edge passes `LINDA_SCOPES ∩ token scopes`) and,
   if it declares `requires_approval`, the merchant ticked it for that token
   (`approved_tools`). Anything else is refused with `external_needs_grant`.
3. **Edge.** `linda_turn._resolve` looks the token up fresh on every call by the
   principal id. A revoked token stops the turn's next tool call. The catalogue is
   Linda's, filtered to the token's scopes.
4. **Running.** `janus.ask` / `askJanus` queue the turn on Celery
   (`agent_mcp.janus_turn`, 420 s limit like automations) and wait up to
   `wait_seconds` (default 20, max 25) for the reply. When the turn is still running
   they return `status: running` and a `turn` id. `janus.reply` / `janusTurn` fetch
   it later (same wait). Turn state is a cache entry (24 h). The conversation itself
   is stored like every other in `AssistantConversation`.
5. **Access.** A new scope `janus.chat` ("Talk to Janus"). A token may talk to Janus
   only when its MCP scopes are explicitly set and include `janus.chat` or `*`. A
   legacy token whose scopes are absent (read as a wildcard elsewhere) does not
   silently gain Janus. Per token: 10 turns a minute and 2 running at once. The
   guardrails (kill switch, daily caps, spend cap) apply as for every turn, and each
   turn is an `AgentRun` (`metadata.via = 'api'`, the token label).
6. **Surfaces.** MCP tools `janus.ask {message, conversation?, wait_seconds?}` and
   `janus.reply {turn, wait_seconds?}` on `/mcp/admin/v1/`, built by agent_mcp and
   never registered in `agent_registry` (so neither Janus nor the Worker can call
   Janus). GraphQL `askJanus(input: {message, conversation, waitSeconds})` and
   `janusTurn(turn, waitSeconds)` via a `JanusMutationExtension` /
   `JanusQueryExtension` contributed by agent_mcp, gated by
   `mutation_scope_error`/`has_scope` on `janus.chat`.

## The API page (agent_mcp tokens page)

- **Create with a purpose**, never an implicit wildcard: *Janus: ask and read*,
  *Janus: ask, read and change*, *Read only*, *Full access*, *Custom*.
- **Connection details** for a token: one text block with everything the other
  party needs (store, MCP URL, GraphQL URL, the header, what the token may do, how to
  talk to Janus), plus ready snippets for Hermes Agent (`config.yaml`
  `mcp_servers`), OpenClaw (`openclaw mcp set`), Claude Code (`claude mcp add
  --transport http`), a generic `mcpServers` JSON (Cursor and others) and a curl
  smoke test. The secret is shown once, on creation or on **New secret** (rotation
  keeps label, scopes and grants). For an existing token the block carries a
  placeholder.
- The two example cards (curl JSON and bookstore GraphQL mutations) go.
- Tokens record who created them; create, rotate, revoke and permission changes write
  audit rows. The approval checklist lists every protected tool a token can reach
  (admin MCP and Janus) and a save keeps grants the form did not show.

## Checkpoints

1. gates + turn identity + edge → `core/assistant/tests`, `agent_mcp/tests/test_linda_turn.py`
   plus a new external-turn suite (consent never spent, grant allows, scope filters,
   revoked token stops).
2. door service + Celery task + MCP tools + GraphQL → tests with the engine mocked.
3. API page → render, presets, rotation, audit rows, connection details content.
4. Docs: `docs/MCP_SERVER.md`, `docs/MORPHEUS_API.md`, `docs/API_STABILITY.md`,
   `docs/AGENT_PROTOCOLS.md`, `/agents.md`, CLAUDE.md landmine, release notes.
