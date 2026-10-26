---
type: decision
status: accepted
tags:
- adr
links:
- 0011-one-generic-agent-grow-it-via-tools-skills-scopes-never-add-a-second-agent
- 0027-agent-write-governance-requires-approval-enforced-at-the-mcp-edge-via-per-token-grants-every-tool-call-audited-per-token-rate-limits
- 0029-linda-and-the-agent-layer-are-permanent-core-never-a-plugin
created: '2026-10-10T00:00:00'
updated: '2026-10-10T00:00:00'
rules:
- rule_id: one-janus-one-gate-chain
  kind: forbid_pattern
  severity: error
  scope: plugins/**/*.py
  exclude: '**/tests/**'
  target: ^\s*def\s+(gate_reason|_gate_reason)\b|\bconsent\.consume\(
  message: Every door into Janus runs the one gate chain in core/assistant/gates.py; never a second copy
    (ADR 0039).
guidance:
- id: janus-is-the-brain
  statement: Janus is the brain of Morpheus. Every merchant capability is built so Janus can see it and
    use it, through a registered agent tool, in the same change that adds it.
  applies_to: plugins/installed/**, core/**
  guard: 'A new merchant action (a dashboard POST view, a settings write, a service a merchant can trigger,
    a report a merchant reads) ships with an agent tool (contribute_agent_tools() or a core tool): its
    scopes are in AVAILABLE_SCOPES and, for store work, inside gates.LINDA_SCOPES; a tool that writes
    declares requires_approval=True. When an agent must not have it (credentials, owner-only switches),
    the change says why.'
  severity: warn
  status: current; guarded by the scope-vocabulary and Linda catalogue tests
- id: one-janus-one-gate-chain
  statement: 'Every door into Janus (dashboard chat, the widget, automations, external agents over MCP
    and GraphQL) is the same engine behind the same gate chain, core/assistant/gates.py, and the same
    consent kernel. Consent only ever comes from the merchant: their own message in a chat, or a grant
    they made in advance on a token.'
  applies_to: core/assistant/**, plugins/installed/agent_mcp/**, api/**
  guard: No entry point re-implements a gate, widens Linda's scope profile for its caller, lets a message
    that is not the merchant's own (an automation's prompt, an external agent's message, anything Janus
    read) spend a pending consent, or lets Janus do more for an external agent than that agent's token
    could do itself.
  severity: error
  status: enforced by the machine rule of the same id
---

# ADR 0039: Janus is the brain of Morpheus — build every capability for it

## Context

Janus runs Linda's turns; Linda is the brand. ADR 0029 made the agent layer
permanent core and ADR 0011 keeps one generic agent. Since v0.63 Janus has its
own loop over the store's MCP server, learning kept in the database, chats,
automations on a schedule and a per-message model choice. The platform still
grows dashboard-first, though: a feature arrives as a page and a form, and an
agent tool follows later, if at all. A merchant then asks Janus to do something
the dashboard can do and Janus cannot, or explores until its turn times out.

On 2026-10-10 the owner set the direction: Janus should be as much as possible
the brain of Morpheus and the most powerful part of the platform, and external
agents such as Hermes Agent and OpenClaw should be able to talk to it over MCP
and GraphQL.

## Decision

1. **Every capability is built for Janus.** A merchant capability ships with the
   agent tool that lets Janus use it, in the same change: scopes in the
   vocabulary and, for store work, inside Linda's scope profile, and
   `requires_approval=True` on anything that writes. A capability Janus cannot
   reach is half-built. The only exceptions are things an agent must never hold
   (credentials, owner-only switches), and the change names them.
2. **Janus sees the whole store.** Its catalogue is every registered store tool
   (`agent_mcp/linda_turn.py:catalogue`), so a new domain joins the vocabulary
   and the profile when it is added. Prompts and skills name only tools in the
   catalogue.
3. **Janus is reachable from every surface.** The dashboard chat, the widget,
   automations and external agents over MCP and GraphQL are doors to one engine,
   one conversation store and one gate chain. A new surface is a new door to the
   same Janus, never a second agent (ADR 0011).
4. **Power never outruns consent.** A write needs the merchant's "yes": their
   own message in a chat, or a grant they made in advance on an API token. An
   external agent's message, like an automation's prompt, is never consent, so
   Janus does for an external agent exactly what that agent's token could do
   itself, and nothing more.
5. **Janus remembers and knows.** What it learns lives in the database, not on a
   container's disk. What happens in the store (events, errors, health, the daily
   briefing) is readable through tools, so Janus can explain it and act on it.

## Consequences

- Feature work includes its agent tool. A reviewer asks "can Janus do this?" the
  way they ask "does it disappear on disable?".
- The catalogue grows with the platform. The scope-vocabulary and catalogue
  tests keep the two in step.
- External agents can ask Janus for judgement, with its memory, skills and
  knowledge of the store, or call raw tools with a scoped token (ADR 0027).
- Gates live in one file. A door that copies a gate drifts, and the looser copy
  wins wherever it is read.
