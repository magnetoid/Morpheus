# Mistral / Codestral — Vibe Coding Rules & Strategies

> **Role:** The Privacy-First European Powerhouse
> **Best Models (2026):** Mistral Large 3, Codestral 2.5, Mistral Medium 3
>
> **See also:** [../docs/universal-principles.md](../docs/universal-principles.md), [../docs/workflow-guide.md](../docs/workflow-guide.md), [../AGENTS.md](../AGENTS.md).

---

## Model Personality Profile

Mistral models are the top choice for **privacy-sensitive and regulated environments** (GDPR, HIPAA, EU data residency). Codestral 2.5 is Mistral's specialized coding model — optimized for completion, generation, and fill-in-the-middle (FIM). All Mistral models can be self-hosted via vLLM, Ollama, or Mistral's own inference servers, making them ideal for air-gapped enterprise environments.

**Strengths:**

- GDPR-compliant (EU-based training and hosting)
- Self-hostable on commodity hardware
- Excellent code completion + FIM (Codestral)
- Strong multilingual support (French, German, Spanish, Italian)
- Predictable cost when self-hosted (no per-token billing)

**Weaknesses:**

- Smaller training footprint than frontier US models
- May lag on the very latest framework releases (specify versions explicitly)
- Less reliable at strict XML/JSON output structure than Claude
- Reasoning depth lower than Claude Opus or DeepSeek R2 for hard problems

---

## ✅ Core Rules for Mistral / Codestral

### Rule 1: Use for Privacy-Sensitive Workloads

Mistral is the right choice when:

- Your codebase contains proprietary business logic that cannot leave your infrastructure
- You operate in a GDPR / HIPAA / SOC 2-regulated environment
- Company policy prohibits sending code to US-based cloud AI services
- You need an air-gapped local development environment

### Rule 2: Use Codestral for Fill-in-the-Middle

Codestral excels at FIM — completing code between existing blocks:

```python
def process_order(order_id: str, user_id: str) -> OrderResult:
    order = get_order(order_id)

    # [CODESTRAL: Fill in validation and processing logic here]

    return OrderResult(success=True, order=order)
```

This pattern is the highest-leverage use of Codestral. Long generative tasks should go to Mistral Large 3 instead.

### Rule 3: Provide Explicit Language/Framework Context

Because Mistral may have less exposure to cutting-edge framework updates, always specify versions:

```text
I am using Python 3.12, FastAPI 0.115, and SQLAlchemy 2.0 with async sessions.
Do NOT use deprecated SQLAlchemy 1.x patterns (no Query.filter_by, no session.query).
Use the modern SQLAlchemy 2.0 style: select() + async with AsyncSession() as session.
```

### Rule 4: Self-Hosting Configuration

For teams running Mistral locally via Ollama or vLLM, set a strict system prompt in your Modelfile or server config:

```text
You are a senior software engineer. Always write production-quality code.
Never truncate code or use placeholders. Always use the language version and
libraries specified by the user. If uncertain about a library API, state your
uncertainty explicitly rather than guessing.
```

### Rule 5: Use for Multilingual / International Projects

Mistral's European training data makes it strong for:

- Translating code comments and docs to/from French, German, Spanish, Italian
- Handling Unicode and locale-aware code (i18n, l10n)
- European-region compliance (GDPR notices, EU-style date/currency formatting)

### Rule 6: Pair with a Stronger Model for Reasoning-Heavy Tasks

Mistral is excellent at *generation*; for complex *reasoning* (architecture, hard debugging, deep refactoring), pair it with a stronger model and use Mistral as the executor:

1. **Claude / DeepSeek R2** — design + plan
2. **Codestral / Mistral** — generate the code from the plan, locally and privately

---

## 🧪 Mistral-Specific Workflow: The "Air-Gapped Loop"

Ideal when no code can leave the local machine:

1. **Spec on local Ollama:** Write the spec yourself; have local Mistral Large 3 critique it. *"Identify ambiguities or missing edge cases. Do not write code."*
2. **Generate with Codestral:** Atomic chunk generation via FIM or Codestral's completion endpoint.
3. **Verify locally:** type-check, lint, tests — all run on the dev machine.
4. **Commit:** standard git workflow, never leaves your network.
5. **Handoff:** `context-template.md` lives in the repo, not in any cloud.

---

## 🚫 Anti-Patterns for Mistral

| Anti-pattern | Why it fails | Do this instead |
| --- | --- | --- |
| Assuming current framework knowledge | Knowledge is older than frontier US models | Always specify exact library versions |
| Using Mistral when Claude is allowed | You're trading quality for privacy you don't need | Use the strongest model your policy permits |
| No system prompt on self-hosted Ollama | Output drifts toward casual / verbose | Set a strict system prompt in the Modelfile |
| Long generative tasks via Codestral | Codestral is tuned for completion, not generation | Use Mistral Large 3 for >100-line outputs |
| Treating local Mistral as equivalent to cloud Claude | Different model class, different reasoning depth | Use Mistral for generation, pair for reasoning |

---

## 🚫 Common Mistakes to Avoid

| Mistake | Instead |
| --- | --- |
| Assuming it knows the latest framework releases | Always specify exact library versions |
| Using Mistral for non-privacy-sensitive work where Claude excels | Use Mistral specifically when privacy is the constraint |
| Not configuring a system prompt for self-hosted instances | Always set a system prompt in Ollama / vLLM configs |
| Sending complex multi-step reasoning to Codestral | Use Mistral Large 3 for reasoning, Codestral for completion |
