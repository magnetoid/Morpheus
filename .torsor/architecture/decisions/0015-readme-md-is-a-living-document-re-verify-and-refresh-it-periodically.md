---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-09T21:53:10'
updated: '2026-06-09T21:53:10'
rules:
- id: readme-living-doc
  pattern: MORPHEUS_DEFAULT_PLUGINS|plugins/installed/[a-z0-9_]+/plugin\.py
  message: 'Added/removed/renamed a plugin or changed the default set? README.md documents
    the plugin list, tool catalog, counts, and agent model and drifts fast - re-verify
    against MORPHEUS_DEFAULT_PLUGINS + get_default_tools and refresh. Point at the
    source of truth, do not hard-code counts. (ADR: README is a living document.)'
---

# ADR 0015: README.md is a living document — re-verify and refresh it periodically

## Context
The root README is the platform shop window AND its most drift-prone doc: it carries the plugin list, the assistant tool catalog + counts, capability tables, and the agent model — all of which rot as the platform evolves. A 2026-06 audit found concrete drift: "20 tools" (really 50+), fictional fs.*/logs.*/system.* tools get_default_tools no longer registers, a stale 4-specialist-agents table contradicting ADR 0011 (one generic Worker), an undocumented book_product plugin, and demo_data listed as default after being disabled. Complements CLAUDE.md's "Living document" rule — this one is specifically about the README and a PERIODIC sweep, not just same-commit updates.

## Decision
Treat README.md as a living document: occasionally re-verify it against the codebase and refresh. Sweep (a) periodically and (b) whenever plugins, agent tools, or capabilities change. Each sweep cross-checks the plugin set against MORPHEUS_DEFAULT_PLUGINS (every active plugin documented), the tool catalog against get_default_tools (no phantom tools), the agent model (ONE generic Worker + Skills per ADR 0011), and that referenced doc links exist. Prefer pointing at the source of truth over hard-coding volatile facts (write "see MORPHEUS_DEFAULT_PLUGINS / get_default_tools", never a bare count — the plugin count rotted to 47/49/54 while the real number was 61, now 65). The hero/story may be polished freely; the factual sections must match reality.

## Consequences
A small recurring maintenance task that keeps the README trustworthy as the public face. The drift-guard rule flags plugin-set / plugin-manifest changes as a prompt to re-check the README. The gitignored README.pdf can be rebuilt from the refreshed README via markdown to HTML to Chrome --headless --print-to-pdf when a shareable copy is needed.
