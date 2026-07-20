"""
MorpheusAgent — the base class every agent inherits from.

A `MorpheusAgent` is metadata + a default tool list + a system prompt.
It is *not* a runtime — execution is the job of `AgentRuntime`. This
keeps agents trivial to write and trivial to test.

Post-pivot (2026-05-23): Morpheus ships exactly ONE agent subclass —
`core.agents.builtin.Worker`. Specialization happens at call time via
Skills + caller scopes, not via subclassing. Adding a new subclass is
blocked by the pre-commit hook in `.githooks/pre-commit` (override
with `SKIP_HOOK=1` only if you have a strong reason and have read
docs/plans/agent-core-into-core.md).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from core.agents.tools import Tool

logger = logging.getLogger('morpheus.agents')

_NAME_RE = re.compile(r'^[a-z][a-z0-9_]*$')


class AgentConfigurationError(TypeError):
    """Raised when an agent's metadata is invalid at class-definition time."""


class MorpheusAgent:
    """Base class for every Morpheus agent."""

    # ── Metadata (override in subclass) ────────────────────────────────────────
    name: str = ''
    label: str = ''
    description: str = ''
    version: str = '1.0.0'
    icon: str = 'sparkles'

    # Visibility — where the agent can be invoked from.
    audience: str = 'merchant'  # 'storefront' | 'merchant' | 'system' | 'any'

    # The capability scopes this agent's tools may declare.
    scopes: list[str] = []

    # System prompt — looked up by name in the prompt registry.
    prompt_name: str = ''
    prompt_version: int | None = None

    # LLM configuration.
    provider: str = ''  # '' = use platform default
    model: str = ''
    temperature: float = 0.3
    max_tokens: int = 1024

    # Runtime guards.
    max_steps: int = 8
    requires_approval: bool = False  # blanket approval gate (per-tool gates also exist)
    # Total-token cap for a single run (prompt + completion, summed across
    # steps). 0 = unlimited. When set, the runtime aborts the run with
    # error='budget_exceeded' before the provider call that would cross it.
    token_budget: int = 0

    # Tools — concrete tool list, populated by `get_tools()` at runtime.
    # Tuple, NOT list, so accidental .append() on the class default raises
    # rather than silently bleeding tools across sibling agent classes.
    default_tools: tuple[Tool, ...] = ()

    # Skill names this agent opts into. Each Skill contributes tools and
    # an optional system-prompt prelude. Resolved against `core.agents.skill_registry`.
    uses_skills: tuple[str, ...] = ()

    # ── Class-time validation ──────────────────────────────────────────────────

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.name:
            return  # intermediate base classes are allowed
        if not _NAME_RE.match(cls.name):
            raise AgentConfigurationError(
                f'{cls.__name__}.name must be snake_case. Got {cls.name!r}.'
            )
        if not cls.label:
            raise AgentConfigurationError(f'{cls.__name__}.label is required.')
        if cls.audience not in ('storefront', 'merchant', 'system', 'any'):
            raise AgentConfigurationError(
                f'{cls.__name__}.audience must be one of '
                "'storefront' | 'merchant' | 'system' | 'any'. "
                f'Got {cls.audience!r}.'
            )
        if not isinstance(cls.scopes, list):
            raise AgentConfigurationError(f'{cls.__name__}.scopes must be a list.')

    # ── Hooks for subclasses ───────────────────────────────────────────────────

    def get_system_prompt(self, context: dict[str, Any] | None = None) -> str:
        """Render the system prompt. Override for dynamic prompts.

        Each opted-in Skill prepends its `system_prompt_prelude` (if any)
        before the base prompt — so a Concierge that opts into the
        `storefront_concierge` skill picks up that skill's preamble for
        free. The merchant's brand voice (configured under
        `/dashboard/settings/ai/`) lands at the very top so every
        agent's writing matches the store's tone.
        """
        from core.agents.skills import skill_registry

        skills = skill_registry.resolve(self.uses_skills or ())
        preludes = [s.system_prompt_prelude for s in skills if s.system_prompt_prelude]

        if not self.prompt_name:
            base = self.description or f'You are the {self.label} agent.'
        else:
            from core.agents.prompts import prompt_registry

            try:
                prompt = prompt_registry.get(self.prompt_name, self.prompt_version)
                base = prompt.render(**(context or {}))
            except KeyError:
                base = self.description or f'You are the {self.label} agent.'

        chunks = [c for c in [*preludes, base] if c]
        prompt = '\n\n'.join(chunks).strip()
        # AGENT_SYSTEM_PROMPT filter — subscribers prepend their prefix (e.g.
        # ai_content's brand voice, which lands first so it frames everything
        # else). Replaces the old direct ai_content import: the bus isolates
        # handler errors and skips inactive owners, so a disabled/absent
        # ai_content just yields the plain prompt.
        from core.hooks import MorpheusEvents, hook_registry

        filtered = hook_registry.filter(MorpheusEvents.AGENT_SYSTEM_PROMPT, value=prompt)
        return filtered if isinstance(filtered, str) else prompt

    def get_tools(self) -> list[Tool]:
        """Return the tools this agent can call.

        Default: `default_tools` ∪ tools from every opted-in Skill ∪ any
        platform tool whose scopes are a subset of this agent's scopes.
        Override to filter further or to add per-instance tools.
        """
        from core.agents.registry import agent_registry
        from core.agents.skills import skill_registry

        out: list[Tool] = list(self.default_tools or [])
        seen_names = {t.name for t in out}

        for skill in skill_registry.resolve(self.uses_skills or ()):
            for tool in skill.tools:
                if tool.name in seen_names:
                    continue
                out.append(tool)
                seen_names.add(tool.name)

        for tool in agent_registry.platform_tools():
            if tool.name in seen_names:
                continue
            if tool.scopes and not set(tool.scopes).issubset(set(self.scopes)):
                continue
            out.append(tool)
            seen_names.add(tool.name)
        return out

    def on_run_start(self, *, run, context: dict[str, Any]) -> None:
        """Hook called when a run begins; override for custom prep."""

    def on_run_end(self, *, run, context: dict[str, Any], result) -> None:
        """Hook called when a run ends (success or failure)."""

    def __repr__(self) -> str:
        return f'<MorpheusAgent {self.name} v{self.version}>'
