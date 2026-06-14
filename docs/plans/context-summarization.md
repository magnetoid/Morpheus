# Context-window summarization (Phase 4)

## Context

Both agent loops feed a bounded slice of history to the LLM and then stop
thinking about size:

- `AgentRuntime.run()` (`core/agents/runtime.py`) appends `system + history +
  user`, then loops up to `max_steps`, appending an assistant turn + tool
  results each step. A long tool-heavy run grows `messages` unbounded.
- `Assistant.stream()` (`core/assistant/runtime.py:~273`) loads the last **30**
  `AssistantMessage`s per turn.

There is **no summarization** — `core/agents/memory.py` notes it's left to
plugins, and nothing implements it. A long conversation (or a tool run that
returns large payloads) eventually exceeds the provider's context window and
the call fails with a hard provider error (surfaced via
`_humanise_provider_error`). The new `token_budget` guard (commit b699665)
*aborts* such a run; this phase lets it *continue* by compacting instead.

## Goal

When accumulated message tokens approach a soft budget, replace the oldest
turns with a single rolling **summary** system message, preserving: the
original system prompt, the running summary, and the most recent N turns
verbatim. Bounded token growth; key facts retained.

## Approach

A small, provider-agnostic helper in `core/agents/` (kernel — both loops use
it), e.g. `core/agents/compaction.py`:

- `estimate_tokens(messages) -> int` — cheap heuristic (chars/4) so we never
  add an API call just to measure. No tokenizer dependency.
- `compact(messages, *, soft_limit, keep_recent, summarizer) -> list[LLMMessage]`:
  1. If `estimate_tokens(messages) <= soft_limit`, return unchanged (hot path —
     zero cost for short conversations).
  2. Split: `system` (kept) · `middle` (to summarize) · last `keep_recent`
     turns (kept verbatim).
  3. `summary = summarizer(middle, prior_summary)` — one cheap LLM call
     (low max_tokens, temperature 0) via the same provider; on failure, fall
     back to **truncation** (drop oldest) so a flaky summarizer never breaks
     the run.
  4. Return `[system, LLMMessage(role='system', content="Conversation so far: "+summary), *recent]`.
- Carry the rolling summary forward (store on the trace / conversation so the
  next compaction summarizes summary+new, not the whole history again).

### Wiring
- `AgentRuntime.run()`: call `compact(messages, …)` at the top of the loop,
  before the budget check. Summarizer = `self.provider.respond` with a terse
  "summarize the following agent transcript" system prompt.
- `Assistant.stream()`: apply the same helper to the assembled LLM messages
  before the provider call; persist the rolling summary on
  `AssistantConversation` (new nullable `summary` TextField → migration; keep
  it a plain column, mind the sqlite/Postgres landmine).

### Defaults
- `soft_limit`: provider-aware but conservative (e.g. 6000 tokens for the
  agent loop, 8000 for chat) — configurable via settings, not hard-coded in
  the loop.
- `keep_recent`: 6 turns.

## Reuse
`LLMMessage`/`LLMResponse` (`core/agents/llm.py`), `AgentTrace` token counters,
the provider abstraction (summarizer is just another `respond` call).

## Risks
- **Hot-loop cost** — the `estimate_tokens` short-circuit must make the
  common (short) case free. Measure before/after.
- **Summarizer failure** — must fall back to truncation, never raise.
- **Fact loss** — keep the original system prompt + recent turns verbatim;
  only the middle is lossy. Add a test asserting a known fact in an early turn
  survives into the summary.

## Verification
- Unit: short history → unchanged; long history → bounded token count + recent
  turns intact + summarizer called once; summarizer-raises → truncation
  fallback, run still completes.
- Integration: a 100-message synthetic conversation stays under the window.
- Migration tested on real Postgres (CI). `DATABASE_URL='sqlite:///:memory:'`
  for the unit tests.
