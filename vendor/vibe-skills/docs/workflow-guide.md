# The Vibe Coding Workflow Guide (2026)

> The canonical, end-to-end workflow that turns vibe coding from improv into engineering.
> Every other file in this framework feeds into the loop described here.
>
> **Companion files:** [universal-principles.md](universal-principles.md) (the *why*),
> [spec-template.md](spec-template.md) (the *what*),
> [context-template.md](context-template.md) (the *handoff*),
> [../AGENTS.md](../AGENTS.md) (the *agent contract*).

---

## The Six-Phase Loop

```
┌──────────┐    ┌─────────┐    ┌──────────┐    ┌────────┐    ┌────────┐    ┌─────────┐
│ 1 PLAN   │ →  │ 2 LOAD  │ →  │ 3 GEN    │ →  │ 4 VRFY │ →  │ 5 SAVE │ →  │ 6 HAND  │
│  Spec    │    │ Context │    │ One chunk│    │ Review │    │ Commit │    │  Off    │
└──────────┘    └─────────┘    └──────────┘    └────────┘    └────────┘    └─────────┘
                                       ▲                                          │
                                       └──────────────  loop  ────────────────────┘
```

You repeat phases 3 → 4 → 5 inside one session. You revisit phase 1 only when scope
changes. You only enter phase 6 when stopping.

---

## Phase 1 — Plan (write the spec)

**Goal:** A short, scannable spec that fits in one prompt window.

**Inputs:** product idea, constraints, deadline.
**Outputs:** filled-in [spec-template.md](spec-template.md).

**Do:**
- Pick the model best suited for spec drafting (typically Gemini for ingestion,
  Claude for refinement, GPT-4o for brainstorming variations).
- Write the spec yourself or co-write it; never *only* let the AI fill it in.
- Capture: goals, tech stack, data models, API surface, non-functional requirements,
  out-of-scope items.

**Don't:**
- Skip the spec because "it's a small change." A two-line spec still beats no spec.
- Write a spec longer than the implementation it describes.

**Exit criteria:** You can describe the feature's acceptance test in one sentence.

---

## Phase 2 — Load Context (prime the agent)

**Goal:** The agent sees only what it needs — nothing more.

**Inputs:** the spec, any prior `context-template.md`, the relevant rule files for
this LLM and language, links to existing patterns in the repo to mirror.

**Prompt template:**

```
Read these files in order:
1. docs/spec-template.md (the current task)
2. AGENTS.md (universal protocols)
3. llm-rules/<your-llm>.md (LLM-specific guidance)
4. language-rules/<your-language>.md (language-specific guidance)
5. <one or two existing files in the repo that match the style we want>

Confirm you have read them. Do not write code yet.
Reply with a 3-bullet plan of how you intend to implement the first task in the spec.
```

**Don't:**
- Dump the entire repo into context. Choose 1–3 representative files instead.
- Re-explain rules the agent already loaded; reference the file by path.

**Exit criteria:** The agent has produced a 3-bullet plan and you have approved or
edited it.

---

## Phase 3 — Generate (one atomic chunk)

**Goal:** One small, testable change. Pillar 3 of
[universal-principles.md](universal-principles.md) is the law here.

**Atomic chunk = one of:**
- One new function or class, ≤ 200 lines.
- One new file, ≤ 400 lines.
- One bug fix, scoped to a known root cause.
- One refactor, with no behavior change (separate from feature work).

**Prompt template:**

```
TASK: <one sentence describing the chunk>
CONTEXT: <which files this touches; what stays unchanged>
CONSTRAINTS: <from language-rules and AGENTS.md>
OUTPUT: Provide the complete file(s). No placeholders, no "// rest of code".
```

**Don't:**
- Bundle "build login + signup + password reset" into one prompt.
- Let the agent extend scope mid-prompt ("I'll also clean up X while I'm here…").
  Stop it and put X in the spec or a separate chunk.

**Exit criteria:** Code generated, complete (no truncations), files identified.

---

## Phase 4 — Verify (zero-trust review)

**Goal:** Catch hallucinations, security issues, and architectural drift *before* the
chunk lands on disk.

**Pillar 4 of [universal-principles.md](universal-principles.md) defines the
checklist. In practice, run all of these:**

| Check | How |
|---|---|
| Compiles / type-checks | `tsc --noEmit`, `mypy`, `cargo check`, equivalent |
| Linter clean | `eslint`, `ruff`, `clippy`, equivalent |
| Tests pass | Run the suite — *new* tests for new code, regression suite for the rest |
| Imports real | Search the codebase + package manifest for every import |
| No new deps | If a dep was added, verify it exists, is maintained, has no recent CVEs |
| Security scan | SAST or `npm audit` / `pip-audit` if dependencies changed |
| Spec match | Re-read the spec section; the chunk meets the acceptance criteria |
| Pattern match | The chunk follows the existing repo style (the file you referenced in phase 2) |

**The "AI-on-AI review" pattern (high leverage, ~5 minutes):**

```
[Open a fresh session with a different model]
Review the following code for: hallucinated APIs, security issues, missing edge cases,
deviation from <repo style>. Be specific about line numbers.
<paste the chunk + the relevant rule file>
```

If the second model finds something, fix in phase 3 and re-verify.

**Exit criteria:** All checks above pass. If any failed, you're back in phase 3.

---

## Phase 5 — Save (commit the chunk)

**Goal:** A clean, atomic git commit you can roll back to.

**Rules:**
- One feature → one commit. One fix → one commit. Never mix.
- Commit message format:
  ```
  <type>(<scope>): <imperative summary, ≤72 chars>

  <2–4 lines of why, not what — the diff shows what>
  ```
  Where `<type>` is one of: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.
- Don't squash AI-aided commits into oblivion at the end — the per-chunk history *is*
  the audit trail of which prompt produced which code.

**Spec-to-PR pattern (the 2026 default):**
1. Commit the chunk.
2. When the feature is complete (multiple chunks), open a PR.
3. The PR description = the spec section being delivered + the verification table
   above with checkboxes ticked.
4. Reviewers focus on **interfaces, failure handling, and security-sensitive paths**
   — not stylistic nits, which the rule files already enforced.

**Exit criteria:** Commit on a feature branch, working tree clean. (PR optional;
required only at end of feature.)

---

## Phase 6 — Handoff (close the session)

**Goal:** The next session — yours or a teammate's — starts from a known state, not
from re-reading the entire diff.

**Inputs:** what was done, what's open, what's next.
**Outputs:** updated [context-template.md](context-template.md).

**Always log:**
- What was completed (link to commits or PR).
- What's blocked (and why).
- Next 1–3 actions, in priority order.
- Any *decisions* made during the session that aren't visible in the code (e.g.
  "rejected approach X because of Y").

**Exit criteria:** Anyone (including future-you) can read `context-template.md` and
resume in <5 minutes without re-reading the chat history.

---

## When to Break the Loop

Skip phases only when the cost of the phase exceeds its value:

| Situation | OK to skip | Not OK to skip |
|---|---|---|
| Typo fix or comment edit | Phase 1, 4 (light verify only) | Phase 5 (still commit) |
| Spike / throwaway prototype | Phase 1, 6 | Phase 4 (still type-check + run) |
| Production bug fix | — | All phases. The spec is the bug repro. |
| Greenfield exploration | Phase 6 (per-session) | Phase 1 (write *some* spec) |

---

## The Three Failure Modes This Loop Prevents

1. **Context bleed** — phase 6 forces a clean handoff and phase 2 forces a fresh
   load each session, so cross-feature contamination doesn't accumulate.
2. **Quietly-broken-build cascade** — phase 4 runs *before* phase 5, so you never
   commit a chunk that rests on a broken predecessor.
3. **Architecture drift** — phase 1's spec + phase 2's pattern reference + phase 4's
   spec-match check together pin the implementation to the original design.

---

## Cross-References

- The 8 (now 9) pillars: [universal-principles.md](universal-principles.md).
- Per-LLM prompting deep-dives: `../llm-rules/<llm>.md`.
- Per-language rules and pitfall tables: `../language-rules/<lang>.md`.
- Universal agent protocols: [../AGENTS.md](../AGENTS.md).
- IDE-specific configs: `../.cursorrules`, `../.windsurfrules`, `../.traerules`.
