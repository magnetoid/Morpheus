# Universal Vibe Coding Principles (2026 Edition)

> These principles apply to **every** AI coding agent, every model, and every programming language.
> This is the foundation layer of the Vibe Agent Framework.
>
> **Companion files:** [workflow-guide.md](workflow-guide.md) (the loop these pillars feed),
> [spec-template.md](spec-template.md) (Pillar 1 in template form),
> [context-template.md](context-template.md) (Pillar 2 in template form),
> [../AGENTS.md](../AGENTS.md) (the protocols agents must follow).

---

## 🧠 The Mindset Shift

Vibe coding is not about "letting the AI do everything." It is a paradigm shift in the developer's role:

| Old Role | New Role |
|----------|----------|
| Syntax Writer | Architect & Strategist |
| Implementer | Delegator & Reviewer |
| Debugger | Auditor & Verifier |
| Documentation writer | Context Engineer |

The AI is your **high-velocity junior developer**. You are the **senior architect** responsible for every line that ships.

---

## 📐 Pillar 1: Architecture-First (Plan Before You Code)

**Rule:** Never open a chat and say "build me an app." That produces unmaintainable, over-engineered, or hallucinated code.

**The Process:**
1. Write a `docs/spec-template.md`. Define:
   - Product goals and user roles
   - Tech stack and library constraints  
   - Core data models / schemas
   - API surface and data flows
   - Non-functional requirements (security, performance, accessibility)
2. Share the spec with your agent *before* any code generation begins.
3. Keep an **Architectural Decisions Log** to track major choices and their rationale.

**The 70/30 Rule:** Dedicate 70% of AI effort to boilerplate, tests, and documentation. Reserve 30% human effort for architecture, complex business logic, and security reviews.

---

## 📦 Pillar 2: Context Engineering ("Context is King")

AI is only as smart as the exact context it holds. Poor context = poor output.

**Rules:**
- **Prevent Context Rot:** Long sessions cause models to lose focus and hallucinate. Start fresh sessions frequently. Pass a summarized `docs/context-template.md` at the start of each new session.
- **Feed Granular Context:** Don't dump your entire codebase. Provide only the specific files, schemas, or API docs relevant to the current task.
- **Use a Source of Truth:** Use `AGENTS.md` (for all agents) or IDE-specific files (`.cursorrules`, `.windsurfrules`, `.traerules`) to persist constraints across sessions without repeating yourself.
- **Prefer Existing Patterns:** Before asking the AI to create something new, search the codebase for how similar things are done (e.g., "Find an example of an existing API route in this repo before creating a new one").

---

## ⚛️ Pillar 3: Atomic Task Chunking (Small Steps = Quality Output)

**Rule:** One task. One prompt. One verification step.

**Bad prompt:** *"Build the entire user authentication system with login, registration, email verification, and password reset."*

**Good prompts (in sequence):**
1. *"Create the database schema for the `users` table in `schema.sql`."*
2. *"Write the registration endpoint in `routes/auth.ts`, using the schema from `schema.sql`."*
3. *"Write unit tests for the registration endpoint."*
4. *"Build the login endpoint with JWT generation."*

**Why it works:**
- Smaller context = less hallucination
- Each chunk is independently verifiable
- Easier to roll back a small chunk that goes wrong

---

## 🔍 Pillar 4: Zero-Trust Verification ("Never Trust, Always Verify")

**Rule:** Treat every line of AI-generated code as unreviewed code from a junior developer.

**The Review Checklist (run after every AI output):**
- [ ] Does it meet the requirement? (Compare against the spec)
- [ ] Is it secure? (SQL injection, XSS, insecure defaults, hardcoded secrets)
- [ ] Does it fit the architecture? (Follows existing patterns, not invented new ones)
- [ ] Is it readable? (Not over-engineered or unnecessarily complex)
- [ ] Is it tested? (Tests exist and actually verify behavior)
- [ ] Are imports and dependencies real? (AI hallucinates library methods)

---

## 🧪 Pillar 5: Test-Driven Development (TDD)

**Rule:** Write tests *before* the implementation when working with complex logic.

**The TDD Vibe Coding Loop:**
1. Ask the AI to write the unit tests for the *intended* behavior.
2. Review and approve the tests.
3. Ask the AI to write the implementation that passes those tests.
4. Run the tests. If they fail, share the error output with the AI and iterate.

**Why it matters:** This prevents the AI from writing code that "looks correct" but fails on edge cases. It also catches hallucinated method signatures before they reach production.

---

## 🔒 Pillar 6: Security Hygiene

**Rules:**
- **Never include secrets in prompts.** Never paste API keys, database passwords, or tokens into an AI chat window. Ever.
- **Default to Secure Patterns.** Explicitly instruct the AI to use parameterized queries, sanitize user input, and use environment variables for configuration.
- **Scan AI Output.** Run generated code through a SAST (Static Application Security Testing) tool or linter before committing.
- **Validate Third-Party Dependencies.** AI sometimes suggests outdated, vulnerable, or non-existent libraries. Verify every `npm install` or `pip install` recommendation.
- **Assume OWASP Top 10.** AI-generated code is frequently vulnerable to SQL injection, XSS, and insecure direct object references. Verify these explicitly.

---

## 🔄 Pillar 7: Version Control as a Safety Net

**Rules:**
- **Commit After Every Successful Chunk.** Every verified AI-generated component becomes a save point. This lets you roll back instantly if the AI leads the codebase into an unmaintainable state.
- **Atomic Commits:** One feature, one fix, one commit. Keep the history clean and meaningful.
- **Never Merge Unreviewed AI Code.** Even if the code "works," it must pass the review checklist before entering the main branch.

---

## 🧬 Pillar 8: Anti-Hallucination Protocols

**Rules:**
- **When in Doubt, Ask for Clarification.** Explicitly instruct your agent: "If you are unsure about a library's API, state your uncertainty and ask for documentation rather than guessing."
- **Verify Library Methods.** AI frequently invents method names or parameters for libraries it doesn't fully know. Cross-reference against the official documentation.
- **Avoid AI Gaslighting.** AI models can confidently defend incorrect code. If the code isn't running, don't argue — provide the error trace and ask the AI to debug its *previous* output, not defend it.
- **Use a Second Model for Critique.** Feed the output of one model into a second model (or a different session) to perform a code review. "AI-on-AI" review catches many subtle errors.

---

## 🚨 Pillar 9: Anti-Pattern Awareness

These four failure modes account for the majority of bad vibe-coding sessions in 2026. Each one has a clear signal, a clear cause, and a clear fix. Train yourself to spot them in real time.

### A. Context Bleed

**Signal:** The agent suddenly starts using patterns from a *previous* feature in the current one — wrong file paths, stale variable names, references to a function you renamed two prompts ago.

**Why it happens:** Long sessions accumulate context from earlier turns. The agent doesn't know that "feature B" is unrelated to "feature A," so it reuses A's mental model.

**The fix:** End the session at every feature boundary. Save the relevant outcome to `context-template.md`. Open a fresh session for the next feature. Pillar 2 in action.

### B. Checkpoint Skipping

**Signal:** "It works on my machine" three commits ago, but you don't know which commit broke it.

**Why it happens:** You generated several chunks in a row without verifying any of them. Chunk 4 is built on chunk 3 which was built on a hallucinated method in chunk 2.

**The fix:** Pillar 4 + the Checkpoint Protocol in [../AGENTS.md](../AGENTS.md). Verify before generating the next chunk, every time. Commit verified chunks immediately so rollback is one command.

### C. Broad Prompts

**Signal:** "Build the authentication system." 800 lines come back. You skim it. You don't really know what's in there.

**Why it happens:** You skipped Pillar 3 (atomic chunking) because the spec felt small or you were impatient.

**The fix:** Re-decompose. Schema → registration → login → session → password reset → tests. Each is one prompt, one verification, one commit.

### D. AI Gaslighting

**Signal:** The error trace says one thing. The agent insists the code is correct and offers a confident "fix" that changes a different line. You apply it. New error. Repeat.

**Why it happens:** Some models will defend their previous output rather than read a new error trace as authoritative ground truth.

**The fix:** Treat your runtime as the only source of truth. Paste the *exact* error trace and say: *"The runtime says X. Your previous code is wrong. Find the cause in the trace and fix that line."* If it loops twice, switch models — fresh session, different LLM, same trace.

### E. Hallucinated Dependencies

**Signal:** `import { foo } from 'some-library'` — and `some-library` either doesn't exist, doesn't export `foo`, or is unmaintained with open CVEs.

**Why it happens:** The model interpolates a plausible-sounding library or method from training data that's incomplete, deprecated, or fabricated.

**The fix:** Pillar 8 + a verification step: before any new dependency lands, check that it (1) exists on the registry, (2) has a recent release, (3) has no critical CVEs, (4) actually exports the symbols the code uses. For methods on existing libraries, grep the project's `node_modules` / `site-packages` or read the library's published types.

---

## 🏁 The Ideal Vibe Coding Session Flow

```
1. PLAN     → Fill out spec-template.md. Define goals, tech stack, data models.
2. CONTEXT  → Feed spec + relevant files to your agent. Set language rules.
3. GENERATE → Request one atomic chunk at a time.
4. VERIFY   → Run the review checklist. Test the output.
5. COMMIT   → Git commit the verified chunk (atomic save point).
6. REPEAT   → Loops steps 3-5 until the feature is complete.
7. HANDOFF  → Update context-template.md for the next session.
```
