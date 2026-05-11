# Skills catalog

Reusable workflows under [`.claude/skills/`](../.claude/skills/). Each
skill is a markdown file that Claude Code loads on demand when a
trigger phrase matches.

## What's defined

| Skill | Trigger | What it does |
|---|---|---|
| [`plugin-skeleton`](../.claude/skills/plugin-skeleton/SKILL.md) | "scaffold a new plugin called X" | Generates the 7-file plugin skeleton (apps.py, plugin.py, models.py, migrations stub, tests + boundary stubs). Registers in `MORPHEUS_DEFAULT_PLUGINS`. |
| [`permission-boundary-tests`](../.claude/skills/permission-boundary-tests/SKILL.md) | "boundary tests for view X" | Writes the three mandatory permission tests (anon / authed-no-scope / authed-with-scope) for any view that's not anonymous-only. Required by PLUGIN_DEVELOPMENT.md §13. |
| [`tetra-deploy`](../.claude/skills/tetra-deploy/SKILL.md) | "deploy to tetra", "ship to prod" | rsync → build → docker compose up → migrate → smoke. Targets the live dotbooks.store deployment. |

## What's enforced (not advisory)

The skills above are conveniences. The non-negotiables run as hooks
in [`.claude/settings.json`](../.claude/settings.json):

| Hook | Fires on | What it does |
|---|---|---|
| [`ruff_changed.sh`](../.claude/hooks/ruff_changed.sh) | PostToolUse Edit/Write `.py` | Runs ruff format + check; exits 2 on violation. |
| [`verify_deps.sh`](../.claude/hooks/verify_deps.sh) | PostToolUse Edit/Write `requirements.txt` | Checks each new package exists on PyPI *and* is imported somewhere. Slopsquatting countermeasure. |
| [`no_migration_writes.sh`](../.claude/hooks/no_migration_writes.sh) | PreToolUse Edit/Write `migrations/*.py` | Blocks. Generate via `makemigrations`. |

## When to write a new skill

Promote a workflow into a skill when:

- You've done the same multi-step sequence at least three times in
  different sessions.
- The sequence has clear inputs and outputs (not just "explore the
  codebase").
- It doesn't need privileged tools (use a subagent instead — see
  [`.claude/agents/`](../.claude/agents/)).

If the rule should *block* a bad action rather than guide a good one,
write a hook instead. Anthropic's 2026 rubric: start with a skill,
promote to hook when ignored ≥2×, escalate to subagent only for
context isolation.

## See also

- [`vendor/vibe-skills/AGENTS.md`](../vendor/vibe-skills/AGENTS.md) — universal cross-IDE rules
- [`vendor/vibe-skills/docs/universal-principles.md`](../vendor/vibe-skills/docs/universal-principles.md) — the 9 pillars
- [`vendor/vibe-skills/language-rules/python.md`](../vendor/vibe-skills/language-rules/python.md) — Python pitfalls cheat sheet
- [`.claude/agents/security-reviewer.md`](../.claude/agents/security-reviewer.md) — diff reviewer subagent
- [`.claude/agents/spec-writer.md`](../.claude/agents/spec-writer.md) — spec-first subagent
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — project orientation
- [`CLAUDE.md`](../CLAUDE.md) — house rules
