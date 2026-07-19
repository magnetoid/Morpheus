# Agent authorization hardening (core audit S1/S5 → C1+H1)

**Status:** in build (2026-07-19). Security-critical. Two independent surfaces.

## Decisions (user, 2026-07-19)
1. Kernel gate → **fail-closed with graceful pause**: an approval-required tool
   with no valid approval is NOT executed; record a pending approval + mark the
   run `awaiting_approval`, resume on human approve. (Uses the
   `AgentRun.awaiting_approval` state + `AgentApprovalRequest` model that already
   exist — completing the original design.)
2. Assistant mode (S5/H1) → **close the client-controlled escalation now, defer
   the full scope→has_perm map**: unknown/garbage mode no longer falls back to
   the `general` wildcard, and a client can't request a mode above the acting
   user's server-side ceiling.

## The two surfaces (from the flow map)
- **Kernel** `AgentRuntime` (`core/agents/runtime.py`): gate is
  `if (requires_approval) and self._approval_check` → fail-OPEN when
  `_approval_check is None`, which is EVERY prod construction site
  (`agent_core/services.py:192` run_agent, `core/assistant/tools/spawn.py:141`,
  `core/assistant/briefing.py:117`). 13 `requires_approval=True` tools
  (rbac.grant_role/revoke_role, gift_cards.issue, tax.set_rate, b2b.set_net_terms,
  metafields.set/delete, workflows.run, draft_orders.convert, crm.advance_deal,
  shipping.add_flat_rate, i18n.translate_product/set_translation) run unapproved.
- **Assistant** `Assistant` (`core/assistant/runtime.py:657`): client-controlled
  `mode`; `modes.get_mode` unknown→`general`=wildcard; no per-call scope check.

## Boundary constraint
`core/agents` is deliberately Django-free → cannot import `AgentApprovalRequest`
(lives in `agent_core`). Use a **registry seam** (mirrors
`provider_config_registry`): `core/agents/approval.py` holds an
`approval_registry`; `agent_core.ready()` registers the DB-backed resolver.
Default (no resolver) = **deny** (fail-closed).

## S1 implementation
1. `core/agents/approval.py` (NEW): `approval_registry` with
   `register(resolver)`, `reset()`, `check(tool_name, args, context)->bool`
   (deny on no-resolver / exception). Also a stable `args_fingerprint(tool_name,
   args)` helper (sha256 of sorted JSON).
2. `core/agents/runtime.py` `_dispatch_tool` gate → fail-closed:
   trigger on `tool.requires_approval or agent.requires_approval` regardless of
   `_approval_check`; explicit `_approval_check` honored (tests), else consult
   `approval_registry.check`. On deny: fire new `AgentEvents.APPROVAL_REQUIRED`
   (tool, args, run_id, context) and `_tool_back(error='approval_required')`,
   return (do NOT execute).
3. `core/agents/events.py`: add `APPROVAL_REQUIRED`.
4. `agent_core`: extend `AgentApprovalRequest` with `args_fingerprint` (indexed)
   + `consumed_at`; migration. Register resolver in `ready()`:
   approved+unconsumed+unexpired(5min) request matching (run, tool, fp) →
   consume→True, else False. Subscribe `APPROVAL_REQUIRED` →
   get_or_create pending request (idempotent on run+tool+fp) + set
   `AgentRun.state='awaiting_approval'`. Also fix the dead
   `AgentApprovalRequest.objects.create(agent_name=…, payload=…)` in
   `ecommerce_writes.py:113` (fields don't exist → silently swallowed).
5. Thread `conversation_id` into the runtime context at `services.py:208` +
   `spawn.py:148` so tokens/requests can reference it.

## S5 implementation
1. `core/assistant/modes.py`: `allowed_modes_for(user)` (superuser→all,
   staff→all-except-`dev`); resolve effective mode = requested if allowed else
   the user's safest allowed mode; unknown/garbage → safest, never wildcard.
2. `core/assistant/runtime.py` / `views.py`: resolve mode server-side from
   `context['user']`, treat client `mode` as a hint that can only narrow.

## Tests
- Kernel: requires_approval tool + no approval_check + no resolver → NOT executed
  + APPROVAL_REQUIRED fired (extend `test_runtime.py`). Existing
  approve=True/False tests still pass (explicit check honored).
- agent_core: resolver denies without approved request; approves+consumes with
  one; reuse → denied (consumed); expired → denied; injection fixture (malicious
  arg) can't self-approve.
- Assistant: client `mode=dev` as non-superuser → not dev; garbage mode → not
  wildcard; entitled mode honored.

## Staged-mode reconciliation (found during impl)
The fail-closed gate collided with the sanctioned **staged-writes routines**
(`docs/superpowers/specs/2026-07-05-staged-changes-routines-design.md`): a
routine runs with `context['staged']=True` so write tools record an
`OpsProposal` for human review instead of executing. Staged mode and the token
gate enforce the SAME invariant ("no write without human sign-off") via
different doors — the proposal review *is* the sign-off. So the gate is
**exempt when `context['staged']`** and applies only to DIRECT (non-staged)
execution — which is exactly where the S1 hole was (Linda workers, direct/agent
runs). Guarded by `test_runtime.py::test_approval_gate_exempt_in_staged_mode`
and the pre-existing `test_catalog_hygiene_routine`.

## Deferred (noted, not in this pass)
- `core/assistant/tools/ecommerce_writes.py:113` calls
  `AgentApprovalRequest.objects.create(agent_name=…, payload=…)` — fields that
  don't exist + a required non-null `run` FK, so it always raises and is
  swallowed by the surrounding `except: pass`. The promised assistant write-tool
  approval-audit row is never written. This is Assistant-side (in-band
  `hard_gate_ack`), separate from the kernel S1 flow and not a security hole
  (the hard-gate still enforces). Fix when reconciling the assistant write path.
- Full scope→`has_perm` map (H1 remainder) — deferred per the user decision.

## Blast radius (accepted per "graceful pause")
Scheduler + workflows engine + spawned Workers now PAUSE at approval tools
instead of silently executing — the intended fix; degrades to `awaiting_approval`,
not a crash. Verify `briefing.py` (`_read_only_worker`) excludes all 13 tools.
