# Linda agent quality — make her do the job, in time, visibly

Status: **planned 2026-09-15.** Step 1 → v0.67.0, Step 2 → v0.68.0. Update as steps land.

Owner request (2026-09-15): "check again this agentic ai … and improve".

## Baseline (live on prod v0.66.1, unpatched, 2026-09-15)

`scratchpad/prod_ai_eval.py` — 10 realistic read tasks + one declined price change.

| Task | Result |
|---|---|
| Orders + revenue last 7 days | 13s, correct |
| Top 5 products (30d) + follow-up stock | 19s / 11s, correct |
| Low / out of stock | **timeout 55s** — explored `platform.capabilities`, `db.*`, `run_python` |
| Top 3 customers | 42s, correct |
| SEO problems | **timeout** — spawned a background Worker (133k tokens, invisible) |
| Anything broken? | 39s, answered; `settings.list` crashed |
| Installed / disabled apps | **timeout** — `settings.list` + `plugins.describe` crashed |
| Sales mode weekly summary | **timeout** — sales mode lists 1 tool |
| Change a price | **timeout** — the price tool is not listed |
| Decline the change | 11s, price unchanged ✓ |

5 of 11 turns failed; the merchant saw "AI provider error" for each. No real merchant
conversations in the last 30 days, so this eval is the evidence.

## Root causes

1. **Catalogue**: Linda's scope profile (`gates.LINDA_SCOPES`) hides the commerce tools
   (inventory, SEO, catalog/orders writes) and her curated list exposes internals
   (`db.*`, `run_python`, `delegate.*`, `platform.capabilities`). Modes filter on scopes
   the read tools don't declare, so Sales/Support/Ops list one tool.
2. **Prompt**: the base prompt names tools that don't exist or are hidden, teaches a
   `confirmed=True` flow that contradicts the consent kernel, encourages Worker spawns,
   and tells her to cite tool names. Bundled skills reference missing tools.
3. **Engine**: DeepSeek reasoning at default "high" effort; ~70 irrelevant Janus
   bundled skills in every prompt with a "MUST load a skill" rule; history sent twice
   (`--resume` + replay) and the per-turn prompt breaks the prefix cache; sessions grow
   forever; max-iterations and empty replies leak junk lines as the answer.
4. **Visibility**: nothing on screen for up to 55s; no token/cost record for a turn.
5. **Bugs**: `tools/list` 500s when Redis is down; `settings.list` AttributeError;
   `plugins.describe` has no schema; consent fingerprint includes `confirmed`, so a
   yes-then-retry is refused again; legacy `/mcp/v1/` lost `csrf_exempt` in v0.64.0.

## Step 1 — v0.67.0: the right tools, the right prompt, no crashes

- Linda's catalogue at the MCP edge (`agent_mcp/linda_turn.py:catalogue`): every
  registered tool inside a merchant scope profile, minus shopper-session tools,
  duplicates and platform internals; internals only in Developer mode.
- **Every write needs the merchant's yes** at the edge (any write scope, plus
  `delegate.spawn_workers` and `meta.sync_audience`), not just `requires_approval`
  tools — the Worker's per-tool flags were never designed for a chat agent.
- Modes: Sales/Support/Ops also admit `system.read`, so their read tools list.
- Consent fingerprint ignores `confirmed` / `hard_gate_ack` / `echo`.
- Fix `settings.list`, `plugins.describe` schema (+ test: handler-required ⊆ schema),
  `tools/list` Redis-down crash, `/mcp/v1/` csrf_exempt, kill switch for write-scoped
  tools, tool-result size cap.
- Rewrite the base prompt and the four skills against the real catalogue; test that
  every tool a skill or the prompt names is in Linda's catalogue.

Verify: eval again on prod; every task answers or asks for approval.

## Step 2 — v0.68.0: faster, visible, bounded

- Janus config: `agent.reasoning_effort` (merchant setting, default `low`),
  `agent.api_max_retries: 1`, MCP `tools.resources/prompts: false`, parallel MCP calls.
- No Janus bundled skills (`.no-bundled-skills` marker) and Linda's own `SOUL.md`.
- History once: replay only when a fresh Janus session starts; rotate the session
  after idle time or length, so context stays bounded.
- Turn runs under `Popen`; the chat receives tool progress (from the tool rows the
  edge stores) and keepalives; the turn limit rises above 55s (gthread workers don't
  kill long requests; keepalives hold the proxies) — verify through the public URL.
- Record tokens and cost from Janus's `state.db` on the reply.
- Junk stdout (`Reached maximum iterations`, `(empty)`, empty stdout) is a failure;
  a timeout says "took too long", not "AI provider error".

Verify: eval again; compare latency and failures with the baseline above.
