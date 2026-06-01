# AGENTS.md — universal agent rules

This project's discipline layer is split across three files. Read the
relevant subset for the work at hand.

| Audience | File |
|---|---|
| **Any AI coding agent** (Cursor / Windsurf / Trae / Cline / Copilot / Claude) | [`vendor/vibe-skills/AGENTS.md`](vendor/vibe-skills/AGENTS.md) |
| **Claude-specific overrides** (this repo's house rules) | [`CLAUDE.md`](CLAUDE.md) |
| **Claude-specific best practices** (companion to CLAUDE.md) | [`vendor/vibe-skills/llm-rules/claude.md`](vendor/vibe-skills/llm-rules/claude.md) |
| **Language-specific pitfalls** (Python is canonical here) | [`vendor/vibe-skills/language-rules/python.md`](vendor/vibe-skills/language-rules/python.md) |
| **Spec-first workflow** (mandatory for any non-trivial change) | [`docs/spec-template.md`](docs/spec-template.md) |
| **Project orientation** (core/ vs plugins/, hook bus, agent layer) | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| **Skill catalog** (what's automated and how to invoke it) | [`docs/SKILLS.md`](docs/SKILLS.md) |

Enforcement (hooks + CI, not advisory) lives in
[`.claude/settings.json`](.claude/settings.json) and
[`.github/workflows/ci.yml`](.github/workflows/ci.yml).

**Docs track code.** Any change that alters structure, a convention, a
contract, or a count updates the relevant doc in the *same commit* — see
the doc-routing table in [`CLAUDE.md`](CLAUDE.md) § "Living document".

The vendored repo at `vendor/vibe-skills/` is a `git subtree` of
<https://github.com/magnetoid/ultimate-vibe-coding-skills>. Pull
upstream changes with:

```bash
git subtree pull --prefix=vendor/vibe-skills \
  https://github.com/magnetoid/ultimate-vibe-coding-skills.git main --squash
```
