# Grok (xAI) — Vibe Coding Rules & Strategies

> **Role:** The Real-Time Intelligence & Large-Context Speed Demon
> **Best Models (2026):** Grok 5, Grok 4 Code, Grok Code Fast
>
> **See also:** [../docs/universal-principles.md](../docs/universal-principles.md) (the 9 pillars), [../docs/workflow-guide.md](../docs/workflow-guide.md) (the loop), [../AGENTS.md](../AGENTS.md) (the protocols).

---

## Model Personality Profile

Grok is uniquely powerful for **real-time ecosystem knowledge** and **large-context codebase analysis**. Its integration with live web data (no knowledge cutoff) and a 1M+ token context window make it the go-to model when you need current information about libraries, breaking changes, or CVEs — or when you need to analyze a large legacy codebase in a single pass.

**Strengths:**

- Real-time web access (no knowledge-cutoff failures)
- 1M+ token context window
- Grok Vision for multimodal debugging (screenshots, diagrams)
- Fast generation speed at large context
- Strong on current ecosystem trivia (new libraries, version migrations)

**Weaknesses:**

- Less precise than Claude for strict structured output (XML, JSON schemas)
- Style can drift toward casual unless you anchor it
- Output quality varies more between runs than Claude/Gemini

---

## ✅ Core Rules for Grok

### Rule 1: Exploit Real-Time Knowledge

Use Grok for questions about the current state of libraries, frameworks, and CVEs:

```text
Search the web for the official Next.js 16 migration guide and all breaking changes
from v15. Then analyze this codebase and list the changes I need to make.
```

```text
Check the npm registry for the most recent versions of @tanstack/react-query.
Are there any open critical CVEs in v5.x? If yes, suggest a safe pinned version.
```

### Rule 2: Large-Context Codebase Analysis

Grok's 1M+ context window is ideal for legacy systems:

```text
Analyze this entire codebase (attached). Identify:
1. All deprecated API usages
2. Files exceeding 500 lines (refactoring candidates)
3. All hardcoded configuration values
4. Any circular dependencies
Provide findings as a structured Markdown report with file:line references.
```

### Rule 3: Use Grok Vision for Visual Debugging

Upload screenshots alongside code for UI bug analysis:

```text
[Attach screenshot] This shows a layout bug on mobile.
The sidebar overlaps the main content at 375px.
Analyze the screenshot and the attached Tailwind classes; suggest a CSS fix.
```

### Rule 4: Validate Third-Party Dependencies in Real-Time

Pillar 9 (anti-hallucination) dovetails with Grok's web access:

```text
I am about to install these packages: [list].
For each, verify it exists on npm, when it was last published, whether it has known
CVEs in its current major version, and whether a more actively-maintained
alternative exists. Cite sources.
```

### Rule 5: Set Professional Mode for Coding

Grok defaults to a casual tone. Anchor it explicitly:

```text
Respond professionally and concisely. Focus only on the technical task.
No humor, no asides, no casual language in code-related responses.
Output code blocks first, prose only when asked.
```

### Rule 6: Pair with a Stricter Model for Final Output

Grok's strength is *finding* — its output style is not its strongest feature. Use the Strategic Stack:

1. **Grok** — research + analysis + current ecosystem knowledge.
2. **Claude or DeepSeek** — write the final code based on Grok's findings.

```text
[Grok prompt]
Research the current best-practice for rate-limiting in Hono v4. Cite the
official docs. Output: a 5-bullet implementation plan, no code.

[Claude prompt — fresh session]
Implement this rate-limiter in Hono v4 following this plan: <paste Grok output>.
Use TypeScript strict mode. Provide the complete file.
```

---

## 🧪 Grok-Specific Workflow: The "Real-Time Audit" Pattern

Ideal for an inherited codebase running on aging dependencies:

1. **Inventory:** *"List every dependency in package.json. For each, fetch its latest version and any open CVEs."*
2. **Triage:** *"Rank the dependencies by upgrade risk: critical CVE, major version drift, abandoned project, low-risk."*
3. **Plan:** *"For the top-3 upgrades, write the upgrade order and breaking-change checklist."*
4. **Execute** with a stricter model (Claude / DeepSeek) using Grok's plan as input.

---

## 🚫 Anti-Patterns for Grok

| Anti-pattern | Why it fails | Do this instead |
|---|---|---|
| Trusting first answer on version-specific questions | Grok occasionally over-trusts a single source | Ask it to cite 2+ sources and reconcile |
| Using Grok for strict XML/JSON-schema output | Style drift; not its strength | Use Claude for strictly-formatted output |
| Skipping the "professional mode" anchor | Casual tone bleeds into code comments | Anchor tone in the system/first message |
| Not verifying its real-time claims | "Latest" can mean different things | Spot-check the cited URL before acting |
| One mega-prompt for whole repo audit | Generates wide but shallow output | Audit by category in successive prompts |

---

## 🚫 Common Mistakes to Avoid

| Mistake | Instead |
|---|---|
| Not using real-time search for version questions | Ask Grok to search and cite sources |
| Using Grok for strict XML-structured output | Use Claude for strict formatting requirements |
| Ignoring Grok Vision for UI bugs | Upload screenshots for visual context |
| Letting it pick the dependency without verification | Always ask for CVE check + maintenance status |
| Treating Grok's plan as final code | Pair with Claude/DeepSeek for the actual implementation |
